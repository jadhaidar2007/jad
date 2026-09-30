"""Register the Telegram webhook so the bot learns who joined through which invite link.

    python -m signalbot.setup_telegram https://your-host
"""
import sys

from signalbot import config, telegram

if __name__ == "__main__":
    if len(sys.argv) != 2 or not config.TELEGRAM_WEBHOOK_SECRET:
        sys.exit("usage: python -m signalbot.setup_telegram https://your-host  (needs TELEGRAM_WEBHOOK_SECRET)")
    ok = telegram.set_webhook(sys.argv[1].rstrip("/") + "/telegram/webhook", config.TELEGRAM_WEBHOOK_SECRET)
    print("webhook set" if ok else "FAILED")
