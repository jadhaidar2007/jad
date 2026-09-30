"""Paid membership: Stripe subscription -> single-use Telegram invite; cancellation -> removal.

Flow
1. Customer pays via a Stripe Payment Link / Checkout whose success URL is
   https://<host>/join?session_id={CHECKOUT_SESSION_ID}
2. /join verifies the session with Stripe and returns a single-use, expiring Telegram invite link.
3. Telegram reports who joined with that link (chat_member update), which ties their Telegram
   user id to the subscription.
4. When Stripe says the subscription ended, the bot removes that Telegram user.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import re
import time

import requests

from signalbot import config, telegram
from signalbot.db import db

log = logging.getLogger(__name__)

STRIPE_TOLERANCE_SECONDS = 300
DEAD_STATUSES = {"canceled", "unpaid", "incomplete_expired"}


class MembershipError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


# --- Stripe ----------------------------------------------------------------
def verify_stripe_signature(payload: bytes, header: str, secret: str, now: float | None = None) -> bool:
    """Check a Stripe-Signature header ("t=...,v1=...") against the raw request body."""
    if not secret or not header:
        return False
    parts = [p.split("=", 1) for p in header.split(",") if "=" in p]
    timestamps = [v for k, v in parts if k == "t"]
    signatures = [v for k, v in parts if k == "v1"]
    if not timestamps or not signatures or not timestamps[0].isdigit():
        return False
    if abs((now if now is not None else time.time()) - int(timestamps[0])) > STRIPE_TOLERANCE_SECONDS:
        return False
    expected = hmac.new(secret.encode(), timestamps[0].encode() + b"." + payload, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, s) for s in signatures)


def _stripe_get(path: str, params: dict | None = None) -> dict:
    try:
        r = requests.get(f"https://api.stripe.com/v1/{path}", params=params, auth=(config.STRIPE_SECRET_KEY, ""), timeout=10)
    except requests.RequestException as e:
        log.warning("stripe request failed: %s", e)
        raise MembershipError("Could not reach the payment provider. Please retry in a minute.", 502)
    if r.status_code == 404:
        raise MembershipError("Checkout session not found.", 404)
    if not r.ok:
        log.warning("stripe %s -> %s: %s", path, r.status_code, r.text)
        raise MembershipError("Could not verify your payment. Please contact support.", 502)
    return r.json()


def create_member_invite(session_id: str) -> str:
    """Verify a paid Checkout session and return a single-use Telegram invite link."""
    if not re.fullmatch(r"cs_[A-Za-z0-9_]+", session_id):
        raise MembershipError("Invalid checkout session.", 400)
    if not (config.STRIPE_SECRET_KEY and config.MEMBERS_CHAT_ID):
        raise MembershipError("Membership is not configured.", 500)

    session = _stripe_get(f"checkout/sessions/{session_id}", {"expand[]": "line_items"})
    if session.get("mode") != "subscription" or session.get("status") != "complete" or session.get("payment_status") not in (
        "paid",
        "no_payment_required",
    ):
        raise MembershipError("Payment not completed.", 403)
    if config.STRIPE_PRICE_IDS:
        prices = {(i.get("price") or {}).get("id") for i in (session.get("line_items") or {}).get("data", [])}
        if not prices & set(config.STRIPE_PRICE_IDS):
            raise MembershipError("This purchase does not include group access.", 403)

    sub_id = session.get("subscription")
    sub_id = sub_id.get("id") if isinstance(sub_id, dict) else sub_id
    if not sub_id:
        raise MembershipError("No subscription on this checkout.", 403)
    # A cancellation webhook may have arrived before the customer opened this page.
    if _stripe_get(f"subscriptions/{sub_id}").get("status") not in ("active", "trialing"):
        raise MembershipError("This subscription is no longer active.", 403)

    with db() as c:
        row = c.execute("SELECT * FROM members WHERE stripe_session_id = ?", (session_id,)).fetchone()
        if row and row["status"] == "active":
            raise MembershipError("This invite was already used. Contact support if you need access again.", 409)
        if row and row["status"] == "revoked":
            raise MembershipError("This membership has ended.", 403)
        if row:
            member_id, old_link = row["id"], row["invite_link"]
        else:
            email = (session.get("customer_details") or {}).get("email") or session.get("customer_email")
            member_id = c.execute(
                "INSERT INTO members (stripe_session_id, stripe_subscription_id, stripe_customer_id, email, created_ts)"
                " VALUES (?,?,?,?,?)",
                (session_id, sub_id, session.get("customer"), email, time.time()),
            ).lastrowid
            old_link = None

    if old_link:
        telegram.revoke_invite_link(config.MEMBERS_CHAT_ID, old_link)
    link = telegram.create_invite_link(config.MEMBERS_CHAT_ID, f"m{member_id}", int(time.time()) + config.INVITE_TTL_SECONDS)
    if not link:
        raise MembershipError("Could not create your invite. Please retry in a minute.", 502)
    with db() as c:
        c.execute("UPDATE members SET invite_link = ? WHERE id = ?", (link, member_id))
    return link


def revoke_subscription(sub_id: str) -> str:
    """Remove everyone tied to this subscription from the group."""
    with db() as c:
        rows = c.execute(
            "SELECT * FROM members WHERE stripe_subscription_id = ? AND status != 'revoked'", (sub_id,)
        ).fetchall()
    for row in rows:
        if row["telegram_user_id"] and not telegram.kick_member(config.MEMBERS_CHAT_ID, row["telegram_user_id"]):
            # Non-2xx makes Stripe redeliver the event, so the removal is retried.
            raise MembershipError("Could not remove member from Telegram.", 502)
        if row["invite_link"] and not row["telegram_user_id"]:
            telegram.revoke_invite_link(config.MEMBERS_CHAT_ID, row["invite_link"])
        with db() as c:
            c.execute("UPDATE members SET status = 'revoked', revoked_ts = ? WHERE id = ?", (time.time(), row["id"]))
    return f"revoked {len(rows)}"


def handle_stripe_event(event: dict) -> str:
    etype, obj = event.get("type", ""), event.get("data", {}).get("object", {})
    if etype == "customer.subscription.deleted" or (
        etype == "customer.subscription.updated" and obj.get("status") in DEAD_STATUSES
    ):
        return revoke_subscription(obj["id"])
    return "ignored"


# --- Telegram --------------------------------------------------------------
def handle_telegram_update(update: dict) -> None:
    """Tie a joining Telegram user to the member row whose invite link they used."""
    cm = update.get("chat_member")
    if not cm or str(cm.get("chat", {}).get("id")) != str(config.MEMBERS_CHAT_ID):
        return
    new = cm.get("new_chat_member", {})
    if new.get("status") not in ("member", "restricted"):
        return
    link = cm.get("invite_link") or {}
    with db() as c:
        row = c.execute(
            "SELECT * FROM members WHERE status = 'pending' AND (invite_link = ? OR ('m' || id) = ?)",
            (link.get("invite_link"), link.get("name")),
        ).fetchone()
        if row:
            c.execute(
                "UPDATE members SET status = 'active', telegram_user_id = ?, joined_ts = ? WHERE id = ?",
                (new["user"]["id"], time.time(), row["id"]),
            )
