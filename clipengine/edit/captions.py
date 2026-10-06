"""Burned-in captions: big word-by-word highlight captions plus a hook title at the top.

Layout notes for 1080x1920: TikTok/Reels cover the bottom ~20% and top ~12% with UI, so
captions sit in the lower-middle and the hook sits in the upper third.
"""
from __future__ import annotations

from pathlib import Path

from clipengine.transcribe.whisper_transcribe import Word

YELLOW = r"\c&H0000FFFF&"

ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,Arial Black,82,&H00FFFFFF,&H0000FFFF,&H00000000,&H96000000,-1,0,0,0,100,100,1,0,1,9,3,2,70,70,560,1
Style: Hook,Arial Black,58,&H0000FFFF,&H0000FFFF,&H00000000,&H96000000,-1,0,0,0,100,100,1,0,1,8,3,8,80,80,300,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

MAX_WORDS = 3
MAX_CHARS = 16
GAP_BREAK_S = 0.6


def _ts(seconds: float) -> str:
    seconds = max(0.0, seconds)
    return f"{int(seconds // 3600)}:{int(seconds % 3600 // 60):02d}:{seconds % 60:05.2f}"


def _clean(text: str) -> str:
    return text.strip().replace("{", "").replace("}", "").replace("\\", "").upper()


def _group_words(words: list[Word]) -> list[list[Word]]:
    groups: list[list[Word]] = []
    cur: list[Word] = []
    for w in words:
        if not _clean(w.text):
            continue
        too_long = cur and len(" ".join(_clean(x.text) for x in cur + [w])) > MAX_CHARS
        gap = cur and w.start - cur[-1].end > GAP_BREAK_S
        if cur and (len(cur) >= MAX_WORDS or too_long or gap):
            groups.append(cur)
            cur = []
        cur.append(w)
        if _clean(w.text)[-1] in ".!?,":
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
    return groups


def build_caption_ass(words: list[Word], hook: str, clip_start: float, duration: float, ass_path: Path) -> None:
    lines = [ASS_HEADER]

    hook = _clean(hook)[:70]
    if hook:
        lines.append(
            f"Dialogue: 1,{_ts(0)},{_ts(min(3.2, duration))},Hook,,0,0,0,,{{\\fad(0,250)}}{hook}"
        )

    groups = _group_words(words)
    for gi, group in enumerate(groups):
        next_start = groups[gi + 1][0].start if gi + 1 < len(groups) else None
        tokens = [_clean(w.text) for w in group]
        for i, w in enumerate(group):
            if i + 1 < len(group):
                end = group[i + 1].start
            else:
                end = w.end + 0.2
                if next_start is not None:
                    end = min(end, next_start)
            end = max(end, w.start + 0.08)
            text = " ".join(
                f"{{{YELLOW}\\fscx118\\fscy118\\t(0,90,\\fscx100\\fscy100)}}{t}{{\\r}}" if j == i else t
                for j, t in enumerate(tokens)
            )
            lines.append(
                f"Dialogue: 0,{_ts(w.start - clip_start)},{_ts(end - clip_start)},Caption,,0,0,0,,{text}"
            )

    ass_path.write_text("\n".join(lines))
