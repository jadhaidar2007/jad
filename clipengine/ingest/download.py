"""Step 1: pull the source video down from YouTube."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import yt_dlp

logger = logging.getLogger(__name__)


@dataclass
class SourceVideo:
    video_id: str
    title: str
    duration_s: float
    file_path: Path


def download_video(youtube_url: str, out_dir: Path) -> SourceVideo:
    """Download the best available mp4 + info for a YouTube URL."""
    out_dir.mkdir(parents=True, exist_ok=True)
    ydl_opts = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": str(out_dir / "%(id)s.%(ext)s"),
        "merge_output_format": "mp4",
        "quiet": True,
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(youtube_url, download=True)
        file_path = Path(ydl.prepare_filename(info))
        if file_path.suffix != ".mp4":
            file_path = file_path.with_suffix(".mp4")

    logger.info("Downloaded %s -> %s", youtube_url, file_path)
    return SourceVideo(
        video_id=info["id"],
        title=info.get("title", info["id"]),
        duration_s=float(info.get("duration") or 0),
        file_path=file_path,
    )
