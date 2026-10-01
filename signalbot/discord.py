"""Post to Discord channels through webhooks."""
from __future__ import annotations

import logging
import time

import requests

from signalbot import config

log = logging.getLogger(__name__)

MAX_LEN = 2000  # Discord's message limit


def _post(url: str, text: str) -> bool:
    # allowed_mentions: a stray @everyone in a note must never ping the server.
    payload = {"content": text[:MAX_LEN], "allowed_mentions": {"parse": []}}
    for attempt in range(3):
        try:
            r = requests.post(url, json=payload, timeout=10)
            if r.ok:
                return True
            log.warning("discord -> %s: %s", r.status_code, r.text[:200])
            if r.status_code == 429:
                time.sleep(min(float(r.json().get("retry_after", 1)), 10))
                continue
            if r.status_code < 500:
                return False
        except (requests.RequestException, ValueError) as e:
            log.warning("discord request failed (attempt %d): %s", attempt + 1, e)
        time.sleep(2**attempt)
    return False


def send_message(text: str, urls: list[str] | None = None) -> bool:
    """Post to every webhook. Returns True only if all deliveries succeeded."""
    urls = urls if urls is not None else config.DISCORD_WEBHOOK_URLS
    if not urls:
        log.error("DISCORD_WEBHOOK_URLS not configured")
        return False
    return all([_post(u, text) for u in urls])
