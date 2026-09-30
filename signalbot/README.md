# SignalBot

Captures TradingView alerts for **US30, SPX500, US100** and posts them as formatted signals to a Telegram group.
Every signal is also logged to SQLite (`signals.db`) for a verifiable track record.

```
TradingView alert ──webhook──► SignalBot (/webhook) ──► Telegram group
                                      └──► signals.db
```

## Setup

1. **Telegram bot:** message @BotFather → `/newbot` → copy the token.
2. **Group:** create your group, add the bot, make it admin. Get the chat id (add @RawDataBot or call
   `https://api.telegram.org/bot<TOKEN>/getUpdates` after sending a message; group ids look like `-100123...`).
3. **Configure:** `cp signalbot/.env.example .env` and fill in `WEBHOOK_SECRET`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_IDS`.
4. **Run:**
   ```
   pip install -r signalbot/requirements.txt
   uvicorn signalbot.app:app --host 0.0.0.0 --port 8080
   ```
   or `docker build -f signalbot/Dockerfile -t signalbot . && docker run --env-file .env -p 8080:8080 -v $PWD/data:/data -e SIGNAL_DB_PATH=/data/signals.db signalbot`
5. **Host it publicly over HTTPS** (TradingView needs a reachable URL): Railway, Render, Fly.io, or a VPS with Caddy/nginx.
   Webhooks need a paid TradingView plan (Essential or higher) and 2FA enabled.

## TradingView alert setup

Alert → Notifications → **Webhook URL** = `https://<your-host>/webhook`. Message:

```json
{"secret": "YOUR_WEBHOOK_SECRET", "action": "buy", "symbol": "{{ticker}}", "entry": {{close}}, "sl": 38900, "tp": 39200}
```

- `action`: `buy` / `sell` / `close` (also `long` / `short` / `exit`).
- `symbol`: `{{ticker}}` works; `US30`, `DJI`, `SPX`, `US500`, `NAS100`, `NDX`, `USTEC` etc. are mapped to US30 / SPX500 / US100. Other symbols are rejected.
- `entry`, `sl`, `tp` (or `tp1`/`tp2`/`tp3`), `note` are optional. R:R is computed when entry, SL and TP are present.
- If your strategy computes SL/TP in Pine Script, use `{{plot("sl")}}`-style placeholders or build the JSON with `alert()` and `str.tostring()`.

Plain text also works: `secret=abc BUY US30 entry 39000 sl 38900 tp1 39200 tp2 39400`.

## Behaviour

- Wrong secret → 401. Unsupported symbol or malformed alert → 422 (visible in TradingView's alert log).
- Duplicate (same action, symbol, entry within `DEDUPE_SECONDS`) → dropped.
- Telegram failure → retried 3x, then 502 and logged with `delivered=0`.

## Tests

`python -m pytest tests_signalbot`
