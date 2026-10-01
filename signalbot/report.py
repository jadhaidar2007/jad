"""Weekly performance report + CSV export of the trade book.

    python -m signalbot.report --print            # show this week's report
    python -m signalbot.report --post             # post it to the Telegram chats now
    python -m signalbot.report --csv trades.csv   # export every closed trade
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import logging
from datetime import datetime, timedelta, timezone

from signalbot import broadcast, config, trades
from signalbot.db import db
from signalbot.format import format_report

log = logging.getLogger(__name__)


def build_weekly_message(now: datetime) -> str:
    start = now - timedelta(days=7)
    title = f"Weekly report ({start:%d %b} – {now:%d %b})"
    return format_report(title, trades.stats(start.timestamp()), trades.stats())


def _due(now: datetime) -> bool:
    hh, mm = (int(x) for x in config.REPORT_TIME.split(":"))
    return (now.weekday(), now.hour, now.minute) >= (config.REPORT_WEEKDAY, hh, mm)


def maybe_post_weekly(now: datetime) -> bool:
    """Post the report once per ISO week, once the scheduled time has passed."""
    iso = now.isocalendar()
    week = f"{iso.year}-{iso.week}"
    with db() as c:
        row = c.execute("SELECT value FROM meta WHERE key = 'last_report_week'").fetchone()
    if (row and row["value"] == week) or not _due(now):
        return False
    if not broadcast.send(build_weekly_message(now)):
        return False  # retry on the next tick
    with db() as c:
        c.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('last_report_week', ?)", (week,))
    return True


async def report_loop() -> None:
    while True:
        try:
            await asyncio.to_thread(maybe_post_weekly, datetime.now(timezone.utc))
        except Exception:
            log.exception("weekly report failed")
        await asyncio.sleep(60)


def export_csv(path: str) -> int:
    rows = trades.closed_trades()
    fields = ["id", "symbol", "side", "entry", "sl", "exit_price", "points", "r", "outcome", "opened_ts", "closed_ts"]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return len(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--print", action="store_true", dest="show")
    ap.add_argument("--post", action="store_true")
    ap.add_argument("--csv")
    args = ap.parse_args()
    msg = build_weekly_message(datetime.now(timezone.utc))
    if args.show or not (args.post or args.csv):
        print(msg)
    if args.post:
        print("posted" if broadcast.send(msg) else "FAILED to post")
    if args.csv:
        print(f"wrote {export_csv(args.csv)} trades to {args.csv}")


if __name__ == "__main__":
    main()
