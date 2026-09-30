"""Thin wrapper over the Telegram Bot API."""
from __future__ import annotations

import logging
import time

import requests

from signalbot import config

log = logging.getLogger(__name__)


def _call(method: str, payload: dict) -> tuple[bool, dict]:
    """POST to the Bot API, retrying network errors, 429 and 5xx. Returns (ok, result)."""
    if not config.TELEGRAM_BOT_TOKEN:
        log.error("TELEGRAM_BOT_TOKEN not configured")
        return False, {}
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/{method}"
    for attempt in range(3):
        try:
            r = requests.post(url, json=payload, timeout=10)
            if r.ok:
                return True, r.json().get("result") or {}
            log.warning("telegram %s -> %s: %s", method, r.status_code, r.text)
            if r.status_code < 500 and r.status_code != 429:
                return False, {}
        except requests.RequestException as e:
            log.warning("telegram %s failed (attempt %d): %s", method, attempt + 1, e)
        time.sleep(2**attempt)
    return False, {}


def send_message(text: str, chat_ids: list[str] | None = None) -> bool:
    """Post to every chat. Returns True only if all deliveries succeeded."""
    chat_ids = chat_ids if chat_ids is not None else config.TELEGRAM_CHAT_IDS
    if not chat_ids:
        log.error("TELEGRAM_CHAT_IDS not configured")
        return False
    results = [
        _call("sendMessage", {"chat_id": c, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True})[0]
        for c in chat_ids
    ]
    return all(results)


def create_invite_link(chat_id: str, name: str, expire_ts: int) -> str | None:
    """Single-use invite link that expires at expire_ts."""
    ok, res = _call(
        "createChatInviteLink", {"chat_id": chat_id, "name": name, "member_limit": 1, "expire_date": expire_ts}
    )
    return res.get("invite_link") if ok else None


def revoke_invite_link(chat_id: str, link: str) -> bool:
    return _call("revokeChatInviteLink", {"chat_id": chat_id, "invite_link": link})[0]


def kick_member(chat_id: str, user_id: int) -> bool:
    """Remove a user but let them rejoin later (ban, then unban)."""
    if not _call("banChatMember", {"chat_id": chat_id, "user_id": user_id})[0]:
        return False
    return _call("unbanChatMember", {"chat_id": chat_id, "user_id": user_id, "only_if_banned": True})[0]


def set_webhook(url: str, secret: str) -> bool:
    return _call("setWebhook", {"url": url, "secret_token": secret, "allowed_updates": ["chat_member"]})[0]
