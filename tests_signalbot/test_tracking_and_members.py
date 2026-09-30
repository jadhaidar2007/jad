import hashlib
import hmac
import json
import time
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from signalbot import config, members, report, trades
from signalbot.db import db


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(config, "WEBHOOK_SECRET", "s3cret")
    monkeypatch.setattr(config, "MEMBERS_CHAT_ID", "-100")
    monkeypatch.setattr(config, "STRIPE_SECRET_KEY", "sk_test")
    monkeypatch.setattr(config, "STRIPE_WEBHOOK_SECRET", "whsec")
    monkeypatch.setattr(config, "TELEGRAM_WEBHOOK_SECRET", "tgsecret")
    monkeypatch.setattr(config, "STRIPE_PRICE_IDS", [])


@pytest.fixture
def client(monkeypatch):
    sent = []
    monkeypatch.setattr("signalbot.telegram.send_message", lambda text, chat_ids=None: sent.append(text) or True)
    from signalbot.app import app

    c = TestClient(app)
    c.sent = sent
    return c


def alert(client, **kw):
    return client.post("/webhook", content=json.dumps({"secret": "s3cret", **kw}))


# --- result tracking ---------------------------------------------------------
def test_win_loss_and_points(client):
    alert(client, action="buy", symbol="US30", entry=39000, sl=38900, tp=39200)
    alert(client, action="close", symbol="US30", entry=39150)  # +150 pts = +1.5R
    alert(client, action="sell", symbol="US100", entry=18500, sl=18550)
    alert(client, action="sl", symbol="US100")  # exits at SL: -50 pts = -1R
    assert "✅ <b>US30 BUY</b> closed @ 39,150\n+150 pts (+1.5R)" in client.sent[1]
    assert "❌ <b>US100 SELL</b> closed @ 18,550\n-50 pts (-1.0R)" in client.sent[3]
    s = trades.stats()
    assert (s["n"], s["wins"], s["losses"], s["points"], s["r"]) == (2, 1, 1, 100, 0.5)


def test_tp_action_uses_first_target(client):
    alert(client, action="buy", symbol="SPX500", entry=5000, sl=4990, tp=5020)
    alert(client, action="tp", symbol="SPX500")
    assert "+20 pts (+2.0R)" in client.sent[1]


def test_reversal_closes_old_trade_and_opens_new(client):
    alert(client, action="buy", symbol="US30", entry=39000, sl=38900)
    alert(client, action="sell", symbol="US30", entry=38950, sl=39050)
    assert "❌ <b>US30 BUY</b> closed @ 38,950" in client.sent[1]
    assert "SELL US30" in client.sent[2]
    assert trades.open_trade_for("US30")["side"] == "sell"


def test_exit_without_open_trade_still_posts(client):
    assert alert(client, action="close", symbol="US30").json() == {"status": "sent"}
    assert client.sent == ["⚪ CLOSE <b>US30</b>"]


def test_close_without_price_is_excluded_from_stats(client):
    alert(client, action="buy", symbol="US30", entry=39000)
    alert(client, action="close", symbol="US30")
    assert trades.stats()["n"] == 0


def test_weekly_report_posts_once_per_week(monkeypatch):
    sent = []
    monkeypatch.setattr("signalbot.telegram.send_message", lambda text, chat_ids=None: sent.append(text) or True)
    t = trades.open_trade(__import__("signalbot.parse", fromlist=["Signal"]).Signal("buy", "US30", 100, 90, [120]))
    trades.close_trade(t, 120)
    thursday = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)
    friday = datetime(2026, 9, 25, 22, 0, tzinfo=timezone.utc)
    assert report.maybe_post_weekly(thursday) is False  # not due yet
    assert report.maybe_post_weekly(friday) is True
    assert report.maybe_post_weekly(friday) is False  # already posted this week
    assert "Win rate: 100%" in sent[0] and "+20 pts" in sent[0] and "US30" in sent[0]


# --- membership ---------------------------------------------------------------
def stripe_headers(payload: bytes, secret="whsec", ts=None):
    ts = str(int(ts or time.time()))
    sig = hmac.new(secret.encode(), ts.encode() + b"." + payload, hashlib.sha256).hexdigest()
    return {"Stripe-Signature": f"t={ts},v1={sig}"}


def test_stripe_signature():
    p = b'{"a":1}'
    h = stripe_headers(p)["Stripe-Signature"]
    assert members.verify_stripe_signature(p, h, "whsec")
    assert not members.verify_stripe_signature(p + b" ", h, "whsec")  # tampered body
    assert not members.verify_stripe_signature(p, h, "other")
    old = stripe_headers(p, ts=time.time() - 3600)["Stripe-Signature"]
    assert not members.verify_stripe_signature(p, old, "whsec")  # replay


@pytest.fixture
def tg(monkeypatch):
    calls = {"kicked": [], "revoked": [], "links": 0}

    def create(chat_id, name, expire_ts):
        calls["links"] += 1
        return f"https://t.me/+link{calls['links']}"

    monkeypatch.setattr("signalbot.telegram.create_invite_link", create)
    monkeypatch.setattr("signalbot.telegram.revoke_invite_link", lambda chat, link: calls["revoked"].append(link) or True)
    monkeypatch.setattr("signalbot.telegram.kick_member", lambda chat, uid: calls["kicked"].append(uid) or True)
    return calls


def fake_stripe(monkeypatch, sub_status="active", payment="paid", price="price_1"):
    def get(path, params=None):
        if path.startswith("checkout/sessions/"):
            return {
                "mode": "subscription", "status": "complete", "payment_status": payment,
                "subscription": "sub_1", "customer": "cus_1", "customer_details": {"email": "a@b.co"},
                "line_items": {"data": [{"price": {"id": price}}]},
            }
        return {"status": sub_status}

    monkeypatch.setattr(members, "_stripe_get", get)


def test_full_membership_lifecycle(client, tg, monkeypatch):
    fake_stripe(monkeypatch)
    r = client.get("/join", params={"session_id": "cs_test_1"})
    assert r.status_code == 200 and "https://t.me/+link1" in r.text

    # Reloading before joining replaces the old link rather than minting extras.
    assert "https://t.me/+link2" in client.get("/join", params={"session_id": "cs_test_1"}).text
    assert tg["revoked"] == ["https://t.me/+link1"]

    update = {"chat_member": {"chat": {"id": -100}, "new_chat_member": {"status": "member", "user": {"id": 777}},
                              "invite_link": {"invite_link": "https://t.me/+link2", "name": "m1"}}}
    assert client.post("/telegram/webhook", json=update, headers={"X-Telegram-Bot-Api-Secret-Token": "tgsecret"}).status_code == 200
    with db() as c:
        row = dict(c.execute("SELECT * FROM members").fetchone())
    assert (row["status"], row["telegram_user_id"], row["email"]) == ("active", 777, "a@b.co")

    # The invite can't be reused once someone joined with it.
    assert client.get("/join", params={"session_id": "cs_test_1"}).status_code == 409

    payload = json.dumps({"type": "customer.subscription.deleted", "data": {"object": {"id": "sub_1"}}}).encode()
    assert client.post("/stripe/webhook", content=payload, headers=stripe_headers(payload)).json() == {"status": "revoked 1"}
    assert tg["kicked"] == [777]
    with db() as c:
        assert c.execute("SELECT status FROM members").fetchone()[0] == "revoked"


def test_unpaid_update_revokes_but_past_due_does_not(client, tg, monkeypatch):
    fake_stripe(monkeypatch)
    client.get("/join", params={"session_id": "cs_test_1"})
    for status, expected in (("past_due", "ignored"), ("unpaid", "revoked 1")):
        p = json.dumps({"type": "customer.subscription.updated", "data": {"object": {"id": "sub_1", "status": status}}}).encode()
        assert client.post("/stripe/webhook", content=p, headers=stripe_headers(p)).json() == {"status": expected}


def test_join_refuses_unpaid_inactive_or_wrong_product(client, tg, monkeypatch):
    fake_stripe(monkeypatch, payment="unpaid")
    assert client.get("/join", params={"session_id": "cs_x"}).status_code == 403
    fake_stripe(monkeypatch, sub_status="canceled")
    assert client.get("/join", params={"session_id": "cs_x"}).status_code == 403
    monkeypatch.setattr(config, "STRIPE_PRICE_IDS", ["price_signals"])
    fake_stripe(monkeypatch, price="price_other")
    assert client.get("/join", params={"session_id": "cs_x"}).status_code == 403
    assert client.get("/join", params={"session_id": "../etc"}).status_code == 400
    assert tg["links"] == 0


def test_webhook_auth(client):
    assert client.post("/stripe/webhook", content=b"{}", headers={"Stripe-Signature": "t=1,v1=bad"}).status_code == 400
    assert client.post("/telegram/webhook", json={}).status_code == 401
    assert client.post("/telegram/webhook", json={}, headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"}).status_code == 401


def test_kick_failure_returns_502_so_stripe_retries(client, tg, monkeypatch):
    fake_stripe(monkeypatch)
    client.get("/join", params={"session_id": "cs_test_1"})
    client.post("/telegram/webhook", headers={"X-Telegram-Bot-Api-Secret-Token": "tgsecret"}, json={
        "chat_member": {"chat": {"id": -100}, "new_chat_member": {"status": "member", "user": {"id": 5}}, "invite_link": {"invite_link": "https://t.me/+link1", "name": "m1"}}})
    monkeypatch.setattr("signalbot.telegram.kick_member", lambda chat, uid: False)
    p = json.dumps({"type": "customer.subscription.deleted", "data": {"object": {"id": "sub_1"}}}).encode()
    assert client.post("/stripe/webhook", content=p, headers=stripe_headers(p)).status_code == 502
    with db() as c:
        assert c.execute("SELECT status FROM members").fetchone()[0] == "active"  # still retryable
