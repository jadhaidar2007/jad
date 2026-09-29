"""RQ task run by the background worker process."""
from __future__ import annotations

import logging

from clipengine.pipeline import run_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def process_video(youtube_url: str, rulebook: str | None = None) -> dict:
    result = run_pipeline(youtube_url, rulebook=rulebook)
    return {
        "video_id": result.video_id,
        "video_title": result.video_title,
        "elapsed_seconds": result.elapsed_seconds,
        "clips": [
            {
                "title": c.title,
                "file_path": c.file_path,
                "posted_to": c.posted_to,
                "errors": c.errors,
            }
            for c in result.clips
        ],
    }
