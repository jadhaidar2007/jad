"""Post queued clips at their scheduled times.

    python run_one.py "<url>" --rulebook-file rulebook.txt --schedule   # fills the queue
    python scheduler.py list                                            # see what is queued
    python scheduler.py run                                             # posts clips when due

`run` only posts while it is running, and your Mac has to be awake. US prime time is the
middle of the night in Germany, so keep it alive with:  caffeinate -i python scheduler.py run
"""
from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from clipengine import config, scheduling


def post_due() -> int:
    from clipengine.pipeline import ClipResult, post_everywhere  # heavy imports only when posting

    n = 0
    for item in scheduling.due():
        path = Path(item["file_path"])
        if not path.exists():
            scheduling.mark_failed(item["id"], f"file missing: {path}")
            continue
        result = ClipResult(title=item["title"], file_path=str(path))
        post_everywhere(path, item["title"], item["caption"], result)
        if result.posted_to:
            scheduling.mark_posted(item["id"], result.posted_to)
            logging.info("Posted #%s to %s", item["id"], result.posted_to)
            n += 1
        else:
            scheduling.mark_failed(item["id"], "; ".join(f"{k}: {v}" for k, v in result.errors.items()) or "no platform posted")
            logging.warning("Post #%s failed: %s", item["id"], result.errors)
    return n


def show() -> None:
    tz = ZoneInfo(config.POST_TIMEZONE)
    local = ZoneInfo("Europe/Berlin")
    items = scheduling.all_items()
    if not items:
        print("Queue is empty.")
    for r in items:
        when = datetime.fromisoformat(r["scheduled_utc"])
        print(
            f"#{r['id']:<3} {r['status']:<8} {when.astimezone(tz):%a %d %b %H:%M} ({config.POST_TIMEZONE})"
            f" = {when.astimezone(local):%H:%M} Berlin  {r['title'][:40]}" + (f"  ! {r['error']}" if r["error"] else "")
        )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["list", "run"])
    ap.add_argument("--once", action="store_true", help="with run: check once and exit")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.cmd == "list":
        show()
        return
    logging.info("Scheduler running. Ctrl+C to stop.")
    while True:
        post_due()
        if args.once:
            return
        time.sleep(30)


if __name__ == "__main__":
    main()
