"""Settings, read from environment variables (see signalbot/.env.example)."""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

# Shared secret that TradingView must include in the alert body as "secret".
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
# Comma-separated chat ids: the paid group and (optionally) a free teaser channel.
TELEGRAM_CHAT_IDS = [c.strip() for c in os.environ.get("TELEGRAM_CHAT_IDS", "").split(",") if c.strip()]

DB_PATH = os.environ.get("SIGNAL_DB_PATH", "signals.db")

# Identical signals inside this window are dropped (TradingView can fire twice).
DEDUPE_SECONDS = int(os.environ.get("DEDUPE_SECONDS", "60"))
