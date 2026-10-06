"""Run the whole pipeline on one video, locally, without Redis/Docker.

    python run_one.py "https://youtu.be/VIDEO_ID" "Clips 20-45s. No profanity. Add #ad"

By default this is a DRY RUN: it downloads, transcribes, picks clips, and renders
them to workdir/<run>/clips/ but does NOT upload anywhere. Watch the clips first,
then add --post to upload to the platforms in ENABLED_PLATFORMS.
"""
from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path

from clipengine import config


def preflight(post: bool) -> list[str]:
    problems = []
    if not shutil.which("ffmpeg"):
        problems.append("ffmpeg not found on PATH (install it: apt install ffmpeg / brew install ffmpeg)")
    if not config.DEEPSEEK_API_KEY:
        problems.append("DEEPSEEK_API_KEY not set in .env")
    if post:
        if "tiktok" in config.ENABLED_PLATFORMS and not (
            config.TIKTOK_ACCESS_TOKEN or config.TIKTOK_REFRESH_TOKEN
        ):
            problems.append("TikTok enabled but no TIKTOK_ACCESS_TOKEN / TIKTOK_REFRESH_TOKEN")
        if "instagram" in config.ENABLED_PLATFORMS and not (
            config.IG_ACCESS_TOKEN and config.PUBLIC_CLIP_BASE_URL
        ):
            problems.append("Instagram enabled but IG_ACCESS_TOKEN / PUBLIC_CLIP_BASE_URL missing")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("rulebook", nargs="?", default=None, help="creator's do/don't rules, as text")
    ap.add_argument("--rulebook-file", help="read the rulebook from a file (e.g. from analyze_campaign.py)")
    ap.add_argument("--post", action="store_true", help="upload immediately (default is dry run)")
    ap.add_argument("--schedule", action="store_true", help="queue clips for US prime-time slots; then run scheduler.py")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.post and args.schedule:
        print("Use either --post or --schedule, not both.")
        return 1
    problems = preflight(args.post or args.schedule)
    if problems:
        print("Fix these first:\n  - " + "\n  - ".join(problems))
        return 1

    from clipengine.pipeline import run_pipeline  # imported late so preflight runs without heavy deps

    rulebook = Path(args.rulebook_file).read_text() if args.rulebook_file else args.rulebook
    result = run_pipeline(args.url, rulebook=rulebook, dry_run=not (args.post or args.schedule), schedule=args.schedule)

    print(f"\n{result.video_title}: {len(result.clips)} clips in {result.elapsed_seconds:.0f}s")
    for c in result.clips:
        status = f"posted to {c.posted_to}" if c.posted_to else (f"scheduled for {c.scheduled_for}" if c.scheduled_for else "not posted")
        print(f"  - {c.title}\n    {c.file_path}  ({status})")
        for platform, err in c.errors.items():
            print(f"    ! {platform}: {err}")
    if args.schedule:
        print("\nQueued. Run `python scheduler.py list` to see times and `caffeinate -i python scheduler.py run` to start posting.")
    elif not args.post:
        print("\nDry run only. Review the clips, then re-run with --post to upload.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
