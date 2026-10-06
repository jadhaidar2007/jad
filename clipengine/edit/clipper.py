"""Step 4: cut, reframe to 9:16, and burn captions onto each selected clip."""
from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from clipengine import config
from clipengine.edit.captions import build_caption_ass
from clipengine.edit.pacing import compute_cut_times, zoom_filter
from clipengine.select.select_clips import ClipPick
from clipengine.transcribe.whisper_transcribe import Transcript, Word

logger = logging.getLogger(__name__)

@dataclass
class RenderedClip:
    pick: ClipPick
    file_path: Path


def _words_in_range(transcript: Transcript, start: float, end: float) -> list[Word]:
    words = []
    for seg in transcript.segments:
        if seg.end < start or seg.start > end:
            continue
        for w in seg.words:
            if start <= w.start <= end:
                words.append(w)
    return words


def render_clip(
    source_video: Path,
    transcript: Transcript,
    pick: ClipPick,
    out_dir: Path,
    aspect: str = "9:16",
) -> RenderedClip:
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = pick.title.lower().replace(" ", "-")[:40]
    slug = "".join(c for c in slug if c.isalnum() or c == "-")
    out_path = out_dir / f"{pick.start:.0f}_{slug}.mp4"
    ass_path = out_dir / f"{pick.start:.0f}_{slug}.ass"

    build_caption_ass(
        _words_in_range(transcript, pick.start, pick.end), pick.hook, pick.start, pick.end - pick.start, ass_path
    )

    # 9:16 crop-to-fill: scale so the shorter dimension covers the target,
    # crop the rest centered. Assumes 16:9 or similar landscape source.
    duration = pick.end - pick.start
    if aspect == "9:16":
        parts = ["scale=1080:1920:force_original_aspect_ratio=increase", "crop=1080:1920"]
        if config.PACING_ENABLED:
            words = _words_in_range(transcript, pick.start, pick.end)
            cuts = compute_cut_times(words, pick.start, duration)
            zoom = zoom_filter(cuts, config.PACING_ZOOM)
            if zoom:
                parts.append(zoom)
        parts += ["setsar=1", f"ass={_ffmpeg_escape(str(ass_path))}"]
        vf = ",".join(parts)
    else:
        vf = f"ass={_ffmpeg_escape(str(ass_path))}"

    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{pick.start:.2f}",
        "-i", str(source_video),
        "-t", f"{duration:.2f}",
        "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "160k",
        str(out_path),
    ]
    logger.info("Rendering clip %s (%.1fs-%.1fs)", out_path.name, pick.start, pick.end)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed for {out_path.name}: {proc.stderr[-800:]}")
    return RenderedClip(pick=pick, file_path=out_path)


def _ffmpeg_escape(path: str) -> str:
    # ffmpeg filtergraph needs escaped colons/backslashes on the ass= path
    return path.replace("\\", "/").replace(":", r"\:")
