"""Settings, read from environment variables (see signalbot/.env.example)."""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def _list(name: str) -> list[str]:
    return [v.strip() for v in os.environ.get(name, "").split(",") if v.strip()]


# --- Signals ---------------------------------------------------------------
# Shared secret that TradingView must include in the alert body as "secret".
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
# Chat ids that receive signals: the paid group and (optionally) a free teaser channel.
TELEGRAM_CHAT_IDS = _list("TELEGRAM_CHAT_IDS")

# Discord channel webhook URLs (Channel settings -> Integrations -> Webhooks). Several allowed.
DISCORD_WEBHOOK_URLS = _list("DISCORD_WEBHOOK_URLS")

DB_PATH = os.environ.get("SIGNAL_DB_PATH", "signals.db")

# Identical signals inside this window are dropped (TradingView can fire twice).
DEDUPE_SECONDS = int(os.environ.get("DEDUPE_SECONDS", "60"))

# --- Weekly report ---------------------------------------------------------
WEEKLY_REPORT = os.environ.get("WEEKLY_REPORT", "1") == "1"
REPORT_WEEKDAY = int(os.environ.get("REPORT_WEEKDAY", "4"))  # 0=Mon ... 4=Fri
REPORT_TIME = os.environ.get("REPORT_TIME", "21:30")  # HH:MM, UTC

# --- Paid membership (Stripe -> Telegram) ----------------------------------
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
# Optional allow-list so other products in the same Stripe account can't unlock the group.
STRIPE_PRICE_IDS = _list("STRIPE_PRICE_IDS")
# The private group members are added to / removed from. Defaults to the first signal chat.
MEMBERS_CHAT_ID = os.environ.get("MEMBERS_CHAT_ID") or (TELEGRAM_CHAT_IDS[0] if TELEGRAM_CHAT_IDS else "")
# Sent back by Telegram in X-Telegram-Bot-Api-Secret-Token on every update.
TELEGRAM_WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
INVITE_TTL_SECONDS = int(os.environ.get("INVITE_TTL_SECONDS", "86400"))
