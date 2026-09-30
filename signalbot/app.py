"""Webhook receiver: TradingView alert -> parsed signal -> Telegram group, plus paid-membership hooks.

Run:
    uvicorn signalbot.app:app --host 0.0.0.0 --port 8080

Endpoints
    POST /webhook           TradingView alerts
    GET  /join              Stripe success page: hands out the Telegram invite
    POST /stripe/webhook    Stripe subscription events
    POST /telegram/webhook  Telegram chat_member updates
"""
from __future__ import annotations

import asyncio
import hmac
import json
import logging
from contextlib import asynccontextmanager
from html import escape

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from starlette.concurrency import run_in_threadpool

from signalbot import config, members, store, telegram, trades
from signalbot.format import format_result, format_signal
from signalbot.parse import EXIT_ACTIONS, ParseError, Signal, extract_secret, parse_alert
from signalbot.report import report_loop

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("signalbot")


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(report_loop()) if config.WEEKLY_REPORT else None
    yield
    if task:
        task.cancel()


app = FastAPI(title="SignalBot", lifespan=lifespan)


@app.get("/health")
def health():
    return {"ok": True}


# --- TradingView -----------------------------------------------------------
def _exit_price(sig: Signal, trade: dict) -> float | None:
    if sig.entry is not None:
        return sig.entry
    if sig.action == "tp":
        return trade["tps"][0] if trade["tps"] else None
    if sig.action == "sl":
        return trade["sl"]
    if sig.action == "be":
        return trade["entry"]
    return None


def track(sig: Signal) -> list[str]:
    """Update the trade book and return the messages to post, in order."""
    existing = trades.open_trade_for(sig.symbol)
    if sig.action in EXIT_ACTIONS:
        if existing is None:
            return [format_signal(sig)]
        return [format_result(trades.close_trade(existing["id"], _exit_price(sig, existing)))]

    msgs = []
    if existing and existing["side"] != sig.action and sig.entry is not None:
        # Reversal: the old trade ends where the new one starts.
        msgs.append(format_result(trades.close_trade(existing["id"], sig.entry)))
        existing = None
    if existing is None:
        trades.open_trade(sig)
    msgs.append(format_signal(sig))
    return msgs


def process_alert(body: str) -> dict:
    if not config.WEBHOOK_SECRET:
        raise HTTPException(500, "WEBHOOK_SECRET is not configured")
    if not hmac.compare_digest((extract_secret(body) or "").encode(), config.WEBHOOK_SECRET.encode()):
        raise HTTPException(401, "bad secret")

    try:
        sig = parse_alert(body)
    except ParseError as e:
        log.warning("rejected alert: %s | body=%r", e, body[:300])
        raise HTTPException(422, str(e))

    if store.is_duplicate(sig):
        log.info("duplicate dropped: %s %s", sig.action, sig.symbol)
        return {"status": "duplicate"}

    delivered = all([telegram.send_message(m) for m in track(sig)])
    store.log_signal(sig, delivered)
    if not delivered:
        # 502 makes the failure visible in TradingView's alert log.
        raise HTTPException(502, "telegram delivery failed")
    return {"status": "sent"}


@app.post("/webhook")
async def webhook(request: Request):
    body = (await request.body()).decode("utf-8", errors="replace")
    return await run_in_threadpool(process_alert, body)


# --- Membership ------------------------------------------------------------
def _page(message: str, status_code: int, link: str | None = None) -> HTMLResponse:
    button = f'<p><a href="{escape(link)}" style="font-size:1.2em">Join the Telegram group →</a></p>' if link else ""
    html = f"<!doctype html><meta name='viewport' content='width=device-width'><body style='font-family:sans-serif;max-width:32em;margin:3em auto;padding:0 1em'><h2>{escape(message)}</h2>{button}</body>"
    return HTMLResponse(html, status_code=status_code)


@app.get("/join")
def join(session_id: str = ""):
    try:
        link = members.create_member_invite(session_id)
    except members.MembershipError as e:
        return _page(e.message, e.status_code)
    return _page("Payment confirmed. Your personal invite (works once, expires in 24h):", 200, link)


@app.post("/stripe/webhook")
async def stripe_webhook(request: Request, stripe_signature: str = Header("")):
    payload = await request.body()
    if not members.verify_stripe_signature(payload, stripe_signature, config.STRIPE_WEBHOOK_SECRET):
        raise HTTPException(400, "bad signature")
    try:
        result = await run_in_threadpool(members.handle_stripe_event, json.loads(payload))
    except members.MembershipError as e:
        raise HTTPException(e.status_code, e.message)
    return {"status": result}


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request, x_telegram_bot_api_secret_token: str = Header("")):
    if not config.TELEGRAM_WEBHOOK_SECRET or not hmac.compare_digest(
        x_telegram_bot_api_secret_token.encode(), config.TELEGRAM_WEBHOOK_SECRET.encode()
    ):
        raise HTTPException(401, "bad secret")
    await run_in_threadpool(members.handle_telegram_update, await request.json())
    return {"ok": True}
