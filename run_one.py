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
    ap.add_argument("--post", action="store_true", help="actually upload (default is dry run)")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    problems = preflight(args.post)
    if problems:
        print("Fix these first:\n  - " + "\n  - ".join(problems))
        return 1

    from clipengine.pipeline import run_pipeline  # imported late so preflight runs without heavy deps

    result = run_pipeline(args.url, rulebook=args.rulebook, dry_run=not args.post)

    print(f"\n{result.video_title}: {len(result.clips)} clips in {result.elapsed_seconds:.0f}s")
    for c in result.clips:
        status = f"posted to {c.posted_to}" if c.posted_to else "not posted"
        print(f"  - {c.title}\n    {c.file_path}  ({status})")
        for platform, err in c.errors.items():
            print(f"    ! {platform}: {err}")
    if not args.post:
        print("\nDry run only. Review the clips, then re-run with --post to upload.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
