"""Telegram admin bot: post signals from your phone.

DM the bot (only user ids in ADMIN_TELEGRAM_IDS are obeyed):

    buy us30 39000 sl 38900 tp 39200
    sell nas100 18500 sl 18550 tp1 18400 | NFP in 1h
    close us30 39150

It replies with a preview and ✅ Post / ❌ Cancel buttons. Nothing is posted until you tap Post.

Run it anywhere (no public URL needed):   python -m signalbot.bot
or, if the web server is deployed, register the webhook:   python -m signalbot.setup_telegram https://<host>
"""
from __future__ import annotations

import argparse
import logging
import threading
import time
from datetime import datetime, timezone
from html import escape

from signalbot import broadcast, config, engine, members, report, store, telegram, trades
from signalbot.db import db
from signalbot.format import to_plain
from signalbot.parse import ParseError, Signal, check_levels, normalize_symbol, parse_alert

log = logging.getLogger("signalbot.bot")

CONFIRM_TTL_SECONDS = 600  # a preview stops working after 10 minutes: prices move

HELP = """Send a signal as plain text. I show a preview and ask before posting.

buy us30 39000 sl 38900 tp 39200
sell nas100 18500 sl 18550 tp1 18400 tp2 18300 | NFP in 1h
close us30 39150   (also: tp us30 / sl us30 / be us30)

/open  trades still open
/stats  this week's report (not posted)
/say text  post an announcement
/drop us30  forget a mistyped open trade (members are not told)
/id  show your Telegram user id"""


# --- pending confirmations ----------------------------------------------------------
def _create_pending(admin_id, kind: str, text: str, note: str = "") -> int:
    with db() as c:
        return c.execute(
            "INSERT INTO pending (admin_id, kind, text, note, created_ts) VALUES (?,?,?,?,?)",
            (str(admin_id), kind, text, note, time.time()),
        ).lastrowid


def _load_pending(pid: int) -> dict | None:
    with db() as c:
        row = c.execute("SELECT * FROM pending WHERE id = ?", (pid,)).fetchone()
    return dict(row) if row else None


def _claim(pid: int, status: str) -> bool:
    """Atomically take a pending action, so a double tap can never post twice."""
    with db() as c:
        claimed = c.execute("UPDATE pending SET status = ? WHERE id = ? AND status = 'pending'", (status, pid)).rowcount == 1
    return claimed


def _buttons(pid: int, force: bool = False) -> list:
    go = ("⚠️ Post anyway", f"force:{pid}") if force else ("✅ Post", f"post:{pid}")
    return [[{"text": go[0], "callback_data": go[1]}, {"text": "❌ Cancel", "callback_data": f"cancel:{pid}"}]]


def _is_admin(user_id) -> bool:
    return user_id is not None and str(user_id) in config.ADMIN_TELEGRAM_IDS


def _signal_of(row: dict) -> Signal:
    sig = parse_alert(row["text"])
    if row["note"]:
        sig.note = row["note"]
    return sig


# --- messages -------------------------------------------------------------------------------
def _propose_signal(chat_id, user_id, raw: str) -> None:
    body, _, note = raw.partition("|")
    try:
        sig = parse_alert(body)
    except ParseError as e:
        telegram.reply(chat_id, f"Couldn't read that: {e}\n\nExample: buy us30 39000 sl 38900 tp 39200")
        return
    if note.strip():
        sig.note = note.strip()
    preview = "\n\n".join(to_plain(m) for m in engine.build_messages(sig, commit=False))
    warnings = "".join(f"\n⚠️ {w}" for w in check_levels(sig))
    pid = _create_pending(user_id, "signal", body.strip(), note.strip())
    telegram.reply(chat_id, f"{preview}{warnings}\n\nPost to {' + '.join(broadcast.destinations())}?", _buttons(pid))


def _propose_say(chat_id, user_id, text: str) -> None:
    if not text:
        telegram.reply(chat_id, "Usage: /say your announcement")
        return
    pid = _create_pending(user_id, "say", text)
    telegram.reply(chat_id, f"{text}\n\nPost this announcement to {' + '.join(broadcast.destinations())}?", _buttons(pid))


def _show_open(chat_id) -> None:
    rows = trades.open_trades()
    lines = [f"{t['side'].upper()} {t['symbol']} @ {t['entry']:g}  SL {t['sl'] if t['sl'] is not None else '-'}" for t in rows]
    telegram.reply(chat_id, "\n".join(lines) or "No open trades.")


def _drop(chat_id, arg: str) -> None:
    try:
        symbol = normalize_symbol(arg)
    except ParseError as e:
        telegram.reply(chat_id, f"{e}\nUsage: /drop us30")
        return
    done = trades.drop_open_trade(symbol)
    telegram.reply(chat_id, f"Dropped the open {symbol} trade. (Messages already posted stay posted.)" if done else f"No open {symbol} trade.")


def _on_message(msg: dict) -> None:
    chat, user = msg.get("chat", {}), (msg.get("from") or {}).get("id")
    text = (msg.get("text") or "").strip()
    if chat.get("type") != "private" or user is None or not text:
        return  # never act on group messages
    parts = text.split(None, 1)
    cmd, arg = parts[0].lower().split("@")[0], parts[1].strip() if len(parts) > 1 else ""
    if cmd == "/id":
        telegram.reply(chat["id"], f"Your Telegram user id is {user}")
        return
    if not _is_admin(user):
        return  # strangers get no reply at all

    if cmd in ("/start", "/help"):
        telegram.reply(chat["id"], HELP)
    elif cmd == "/open":
        _show_open(chat["id"])
    elif cmd == "/stats":
        telegram.reply(chat["id"], to_plain(report.build_weekly_message(datetime.now(timezone.utc))))
    elif cmd == "/drop":
        _drop(chat["id"], arg)
    elif not broadcast.destinations():
        telegram.reply(chat["id"], "No destination configured: set TELEGRAM_CHAT_IDS and/or DISCORD_WEBHOOK_URLS.")
    elif cmd == "/say":
        _propose_say(chat["id"], user, arg)
    elif cmd == "/signal":
        _propose_signal(chat["id"], user, arg)
    elif cmd.startswith("/"):
        telegram.reply(chat["id"], HELP)
    else:
        _propose_signal(chat["id"], user, text)


# --- button taps ---------------------------------------------------------------------------
def _delivery_text(delivery: dict[str, bool]) -> str:
    return "\n".join(f"{'✓' if ok else '✗ FAILED'} {platform}" for platform, ok in delivery.items())


def _on_callback(cb: dict) -> None:
    msg = cb.get("message") or {}
    chat_id, message_id = msg.get("chat", {}).get("id"), msg.get("message_id")
    user = (cb.get("from") or {}).get("id")

    def done(text: str, keyboard: list | None = None) -> None:
        telegram.answer_callback(cb["id"])
        if chat_id is not None and message_id is not None:
            telegram.edit_message(chat_id, message_id, text, keyboard)

    if not _is_admin(user) or msg.get("chat", {}).get("type") != "private":
        telegram.answer_callback(cb["id"])
        return
    action, _, raw_id = (cb.get("data") or "").partition(":")
    row = _load_pending(int(raw_id)) if raw_id.isdigit() else None
    if action not in ("post", "force", "cancel") or row is None or row["admin_id"] != str(user):
        telegram.answer_callback(cb["id"], "Unknown request")
        return
    if row["status"] != "pending":
        telegram.answer_callback(cb["id"], "Already handled")
        return
    if time.time() - row["created_ts"] > CONFIRM_TTL_SECONDS:
        _claim(row["id"], "expired")
        done("⌛ Expired. Send it again.")
        return
    if action == "cancel":
        _claim(row["id"], "cancelled")
        done("Cancelled.")
        return

    sig = _signal_of(row) if row["kind"] == "signal" else None
    if action == "post" and sig and store.is_duplicate(sig):
        done("An identical signal was posted in the last minute.\nPost it again?", _buttons(row["id"], force=True))
        return
    if not _claim(row["id"], "done"):
        telegram.answer_callback(cb["id"], "Already handled")
        return

    if sig:
        outcome = engine.publish(sig, force=action == "force")
        delivery, ok = outcome.delivery, outcome.status == "sent"
    else:
        delivery = broadcast.send_detailed(escape(row["text"]))
        ok = bool(delivery) and all(delivery.values())
    head = "✅ Posted" if ok else "⚠️ Delivery problem. Fix it and repost if members need to see this."
    done(f"{head}\n{_delivery_text(delivery)}")


# --- entry points -----------------------------------------------------------------------------
def handle_update(update: dict) -> None:
    """Route one Telegram update. Used by both the webhook and the polling runner."""
    if "chat_member" in update:
        members.handle_telegram_update(update)
        return
    try:
        if "message" in update:
            _on_message(update["message"])
        elif "callback_query" in update:
            _on_callback(update["callback_query"])
    except Exception:
        log.exception("failed to handle update %s", update.get("update_id"))


def poll_once(offset: int | None) -> int | None:
    """Fetch and handle one batch of updates. Returns the next offset."""
    updates = telegram.get_updates(offset)
    if updates is None:
        time.sleep(5)
        return offset
    for u in updates:
        offset = u["update_id"] + 1
        try:
            handle_update(u)
        except Exception:
            log.exception("update %s failed", u.get("update_id"))
    return offset


def _report_thread() -> None:
    while True:
        try:
            report.maybe_post_weekly(datetime.now(timezone.utc))
        except Exception:
            log.exception("weekly report failed")
        time.sleep(60)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser(description="Run the Telegram admin bot by long polling (no public URL needed).")
    ap.add_argument("--delete-webhook", action="store_true", help="remove a webhook registered earlier (polling and webhooks are exclusive)")
    args = ap.parse_args()
    if not config.TELEGRAM_BOT_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set")
    if args.delete_webhook:
        telegram.delete_webhook()
    if not config.ADMIN_TELEGRAM_IDS:
        log.warning("ADMIN_TELEGRAM_IDS is empty: only /id works. DM the bot /id, set it, and restart.")
    if config.WEEKLY_REPORT:
        threading.Thread(target=_report_thread, daemon=True).start()
    log.info("bot running; admins=%s destinations=%s", config.ADMIN_TELEGRAM_IDS, broadcast.destinations())
    offset = None
    while True:
        offset = poll_once(offset)


if __name__ == "__main__":
    main()
