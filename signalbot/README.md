# SignalBot

Posts **US30, SPX500, US100** signals to a Telegram group and/or a Discord server, either from TradingView alerts
or typed by hand with `python -m signalbot.post`. It tracks every trade's result, posts a weekly performance report, and can sell access automatically through Stripe.

```
TradingView ──► /webhook ─┐
                          ├──► engine ──► Telegram + Discord ──► results + weekly report
you, by hand ─► post CLI ─┘        └──► signals.db (signals, trades, members)

Stripe Checkout ──► /join ──► single-use Telegram invite
Stripe cancel   ──► /stripe/webhook ──► member removed
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

## Posting by hand (no server needed)

Until you automate, send signals yourself. One command posts to every configured destination, tracks the trade and
feeds the weekly report:

```
python -m signalbot.post buy us30 39000 sl 38900 tp 39200
python -m signalbot.post sell nas100 18500 sl 18550 tp1 18400 tp2 18300 --note "NFP in 1h"
python -m signalbot.post close us30 39150        # or: tp us30 | sl us30 | be us30
python -m signalbot.post --open                  # what's still open
python -m signalbot.post --say "No more trades today"
```

- The first unlabeled number is the entry (or the exit price for `close`).
- It shows a preview first, warns if SL/TP are on the wrong side of entry or the entry is missing, and asks `[y/N]`.
  `-y` skips the question, `--dry-run` previews only and changes nothing, `--force` re-posts an identical signal.
- If one platform fails you see which (`✓ telegram`, `✗ FAILED discord`) and the signal is still logged with `delivered=0`.
- You only need the `.env` values for Telegram and/or Discord. The web server, Stripe and TradingView parts are not needed.

## Discord setup

1. Server settings → create a read-only `#signals` channel (and `#results`, `#rules`).
2. Channel settings → **Integrations → Webhooks → New Webhook → Copy Webhook URL**.
3. Put it in `DISCORD_WEBHOOK_URLS` (comma-separate several, e.g. paid and free channels). Webhook messages never ping
   `@everyone` or roles, even if one appears in a note.

Telegram works as before (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_IDS`). Set either or both. Every signal, result and the
weekly report goes to every configured destination. Stripe-gated access is Telegram-only for now, so add Discord members by hand.

## TradingView alert setup

Alert → Notifications → **Webhook URL** = `https://<your-host>/webhook`. Message:

```json
{"secret": "YOUR_WEBHOOK_SECRET", "action": "buy", "symbol": "{{ticker}}", "entry": {{close}}, "sl": 38900, "tp": 39200}
```

- `action`: `buy` / `sell` (also `long` / `short`) to enter; `close`, `tp`, `sl`, `be` (breakeven) to exit.
- `symbol`: `{{ticker}}` works; `US30`, `DJI`, `SPX`, `US500`, `NAS100`, `NDX`, `USTEC` etc. are mapped to US30 / SPX500 / US100. Other symbols are rejected.
- `entry`, `sl`, `tp` (or `tp1`/`tp2`/`tp3`), `note` are optional. R:R is computed when entry, SL and TP are present.
- If your strategy computes SL/TP in Pine Script, use `{{plot("sl")}}`-style placeholders or build the JSON with `alert()` and `str.tostring()`.

Plain text also works: `secret=abc BUY US30 entry 39000 sl 38900 tp1 39200 tp2 39400`.

## Result tracking

Each `buy`/`sell` with an `entry` opens a trade; an exit alert closes it and posts the result:

```
✅ US30 BUY closed @ 39,150
+150 pts (+1.5R)
```

- `close` with `entry` = the exit price (send `{{close}}`). `tp` exits at the first TP, `sl` at the SL, `be` at entry, unless a price is sent.
- A `close` with no price still closes the trade but leaves it out of the statistics.
- An opposite-direction signal on the same symbol closes the open trade at the new entry first (reversal).
- A same-direction signal while a trade is open is posted but not tracked as a second trade.
- One open trade per symbol. R is points divided by the entry-to-SL distance (needs `sl`).

**Weekly report** posts automatically (default Friday 21:30 UTC; set `REPORT_WEEKDAY` / `REPORT_TIME`, or `WEEKLY_REPORT=0` to turn off). It is sent once per week, and sent late if the server was down at the time.

```
python -m signalbot.report --print            # preview
python -m signalbot.report --post             # post now
python -m signalbot.report --csv trades.csv   # full trade history for your sales page / verification
```

## Selling access (Stripe)

Members pay on Stripe and the bot adds and removes them from the private group.

1. **Stripe:** create a recurring Product/Price, then a **Payment Link**. Under *After payment* choose
   *Don't show confirmation page → redirect* to `https://<your-host>/join?session_id={CHECKOUT_SESSION_ID}`.
2. **Stripe webhook:** Developers → Webhooks → endpoint `https://<your-host>/stripe/webhook`, events
   `customer.subscription.deleted` and `customer.subscription.updated`. Copy the signing secret to `STRIPE_WEBHOOK_SECRET`.
   Set `STRIPE_SECRET_KEY` (a restricted key with read access to Checkout Sessions and Subscriptions is enough).
3. **Telegram:** make the bot an admin of the paid group with *Invite users* and *Ban users*. Set `MEMBERS_CHAT_ID`,
   `TELEGRAM_WEBHOOK_SECRET`, then register the webhook once:
   `python -m signalbot.setup_telegram https://<your-host>`
4. Optionally set `STRIPE_PRICE_IDS` so other products in your Stripe account can't unlock the group.

How it behaves:
- After paying, the customer lands on `/join`, which checks the payment and subscription with Stripe and shows a
  **single-use invite link that expires in 24h**. Reloading before joining swaps in a fresh link.
- When they join, Telegram tells the bot who used the link, which ties their Telegram account to the subscription.
- When the subscription ends (`canceled`, `unpaid`), the bot removes them. `past_due` keeps access while Stripe retries
  the card; tune that in Stripe's retry settings. If Telegram removal fails, the webhook returns 502 so Stripe retries.
- People you add by hand are never touched, only members who joined through a bot-issued link.
- Not automated: refunds and disputes. Cancel the subscription in Stripe and the bot removes the member.
- Stripe test mode works end to end. Use test keys first.

## Behaviour

- Wrong secret → 401. Unsupported symbol or malformed alert → 422 (visible in TradingView's alert log).
- Duplicate (same action, symbol, entry within `DEDUPE_SECONDS`) → dropped.
- Telegram failure → retried 3x, then 502 and logged with `delivered=0`.

## Tests

`pip install pytest httpx && python -m pytest tests_signalbot`
