"""Post a signal by hand to Telegram and Discord, with trade tracking and the weekly report.

    python -m signalbot.post buy us30 39000 sl 38900 tp 39200
    python -m signalbot.post sell nas100 18500 sl 18550 tp1 18400 tp2 18300
    python -m signalbot.post close us30 39150      # exit at 39150 (or: tp us30 / sl us30 / be us30)
    python -m signalbot.post --open                # trades still open
    python -m signalbot.post --say "No more trades today"

It shows a preview and asks before posting. Add -y to skip the question, --dry-run to only preview.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from html import escape

from signalbot import broadcast, config, engine, trades
from signalbot.format import to_plain
from signalbot.parse import ParseError, check_levels, parse_alert


def _confirm(question: str, input_fn) -> bool:
    return input_fn(question).strip().lower() in ("y", "yes")


def _show_open() -> None:
    rows = trades.open_trades()
    if not rows:
        print("No open trades.")
    for t in rows:
        opened = datetime.fromtimestamp(t["opened_ts"], timezone.utc).strftime("%d %b %H:%M UTC")
        print(f"{t['side'].upper():4} {t['symbol']:7} entry {t['entry']:g}  sl {t['sl'] if t['sl'] is not None else '-'}  (opened {opened})")


def main(argv: list[str] | None = None, input_fn=input) -> int:
    ap = argparse.ArgumentParser(prog="python -m signalbot.post", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("signal", nargs="*", help="e.g. buy us30 39000 sl 38900 tp 39200")
    ap.add_argument("--note", default="", help="extra line shown under the signal")
    ap.add_argument("-y", "--yes", action="store_true", help="post without asking")
    ap.add_argument("--dry-run", action="store_true", help="preview only, change nothing")
    ap.add_argument("--force", action="store_true", help="post even if an identical signal was just sent")
    ap.add_argument("--open", action="store_true", dest="list_open", help="list open trades")
    ap.add_argument("--say", metavar="TEXT", help="post a plain announcement")
    args = ap.parse_args(argv)

    if args.list_open:
        _show_open()
        return 0

    dests = broadcast.destinations()
    if not dests and not args.dry_run:
        print("No destination configured: set TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_IDS and/or DISCORD_WEBHOOK_URLS.")
        return 2
    where = " + ".join(dests) or "nowhere (dry run)"

    if args.say:
        print(f"\n{args.say}\n")
        if args.dry_run or not (args.yes or _confirm(f"Post to {where}? [y/N] ", input_fn)):
            print("Not posted.")
            return 0 if args.dry_run else 1
        return 0 if broadcast.send(escape(args.say)) else 1

    if not args.signal:
        ap.print_help()
        return 2
    try:
        sig = parse_alert(" ".join(args.signal))
    except ParseError as e:
        print(f"Could not read that signal: {e}")
        return 2
    if args.note:
        sig.note = args.note

    print()
    for msg in engine.build_messages(sig, commit=False):
        print(to_plain(msg) + "\n")
    for w in check_levels(sig):
        print(f"⚠️  {w}")
    if args.dry_run:
        return 0
    if not (args.yes or _confirm(f"Post to {where}? [y/N] ", input_fn)):
        print("Cancelled.")
        return 1

    outcome = engine.publish(sig, force=args.force)
    if outcome.status == "duplicate":
        print(f"An identical signal was posted in the last {config.DEDUPE_SECONDS}s. Use --force to post it anyway.")
        return 1
    for platform, ok in outcome.delivery.items():
        print(f"{'✓' if ok else '✗ FAILED'} {platform}")
    return 0 if outcome.status == "sent" else 1


if __name__ == "__main__":
    sys.exit(main())
