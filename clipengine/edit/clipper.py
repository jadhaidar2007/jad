"""Step 4: cut, reframe to 9:16, and burn captions onto each selected clip."""
from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from clipengine import config
from clipengine.edit.pacing import compute_cut_times, zoom_filter
from clipengine.select.select_clips import ClipPick
from clipengine.transcribe.whisper_transcribe import Transcript, Word

logger = logging.getLogger(__name__)

ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,Arial Black,72,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,6,0,2,60,60,220,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


@dataclass
class RenderedClip:
    pick: ClipPick
    file_path: Path


def _ass_timestamp(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def _words_in_range(transcript: Transcript, start: float, end: float) -> list[Word]:
    words = []
    for seg in transcript.segments:
        if seg.end < start or seg.start > end:
            continue
        for w in seg.words:
            if start <= w.start <= end:
                words.append(w)
    return words


def _build_caption_ass(transcript: Transcript, pick: ClipPick, ass_path: Path) -> None:
    """Word-by-word 'karaoke' style captions, timestamps re-based to clip start."""
    words = _words_in_range(transcript, pick.start, pick.end)
    lines = [ASS_HEADER]

    if pick.hook:
        lines.append(
            f"Dialogue: 0,{_ass_timestamp(0)},{_ass_timestamp(min(2.5, pick.end - pick.start))},"
            f"Caption,,0,0,0,,{{\\b1}}{pick.hook.upper()}"
        )

    group: list[Word] = []
    GROUP_SIZE = 3
    for w in words:
        group.append(w)
        if len(group) >= GROUP_SIZE:
            _flush_group(lines, group, pick.start)
            group = []
    if group:
        _flush_group(lines, group, pick.start)

    ass_path.write_text("\n".join(lines))


def _flush_group(lines: list[str], group: list[Word], clip_start: float) -> None:
    text = " ".join(w.text.strip() for w in group).upper()
    start = group[0].start - clip_start
    end = group[-1].end - clip_start
    lines.append(
        f"Dialogue: 0,{_ass_timestamp(start)},{_ass_timestamp(end)},Caption,,0,0,0,,{text}"
    )


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

    _build_caption_ass(transcript, pick, ass_path)

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
