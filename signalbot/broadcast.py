"""Send one message to every configured destination (Telegram and/or Discord)."""
from __future__ import annotations

import logging

from signalbot import config, discord, telegram
from signalbot.format import to_discord

log = logging.getLogger(__name__)


def destinations() -> list[str]:
    names = []
    if config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_IDS:
        names.append("telegram")
    if config.DISCORD_WEBHOOK_URLS:
        names.append("discord")
    return names


def send_detailed(text: str) -> dict[str, bool]:
    """Post `text` (Telegram HTML) everywhere. Returns {platform: delivered}."""
    results: dict[str, bool] = {}
    if "telegram" in destinations():
        results["telegram"] = telegram.send_message(text)
    if "discord" in destinations():
        results["discord"] = discord.send_message(to_discord(text))
    if not results:
        log.error("No destination configured: set TELEGRAM_* and/or DISCORD_WEBHOOK_URLS")
    return results


def send(text: str) -> bool:
    results = send_detailed(text)
    return bool(results) and all(results.values())
