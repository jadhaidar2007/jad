"""Send messages through the Telegram Bot API."""
from __future__ import annotations

import logging
import time

import requests

from signalbot import config

log = logging.getLogger(__name__)


def send_message(text: str) -> bool:
    """Post to every configured chat. Returns True only if all deliveries succeeded."""
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_IDS:
        log.error("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_IDS not configured")
        return False
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    ok = True
    for chat_id in config.TELEGRAM_CHAT_IDS:
        for attempt in range(3):
            try:
                r = requests.post(
                    url,
                    json={"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True},
                    timeout=10,
                )
                if r.ok:
                    break
                log.warning("telegram %s for chat %s: %s", r.status_code, chat_id, r.text)
                if r.status_code < 500 and r.status_code != 429:
                    ok = False
                    break
            except requests.RequestException as e:
                log.warning("telegram request failed (attempt %d): %s", attempt + 1, e)
            time.sleep(2**attempt)
        else:
            ok = False
    return ok
