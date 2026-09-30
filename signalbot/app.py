"""Webhook receiver: TradingView alert -> parsed signal -> Telegram group.

Run:
    uvicorn signalbot.app:app --host 0.0.0.0 --port 8080

Point the TradingView alert's Webhook URL at  https://<your-host>/webhook
"""
from __future__ import annotations

import hmac
import logging

from fastapi import FastAPI, HTTPException, Request

from signalbot import config, store, telegram
from signalbot.format import format_signal
from signalbot.parse import ParseError, extract_secret, parse_alert

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("signalbot")

app = FastAPI(title="SignalBot")


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/webhook")
async def webhook(request: Request):
    body = (await request.body()).decode("utf-8", errors="replace")

    if not config.WEBHOOK_SECRET:
        raise HTTPException(500, "WEBHOOK_SECRET is not configured")
    secret = extract_secret(body) or ""
    if not hmac.compare_digest(secret, config.WEBHOOK_SECRET):
        raise HTTPException(401, "bad secret")

    try:
        sig = parse_alert(body)
    except ParseError as e:
        log.warning("rejected alert: %s | body=%r", e, body[:300])
        raise HTTPException(422, str(e))

    if store.is_duplicate(sig):
        log.info("duplicate dropped: %s %s", sig.action, sig.symbol)
        return {"status": "duplicate"}

    delivered = telegram.send_message(format_signal(sig))
    store.log_signal(sig, delivered)
    if not delivered:
        # 502 makes the failure visible in TradingView's alert log.
        raise HTTPException(502, "telegram delivery failed")
    return {"status": "sent"}
