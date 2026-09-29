"""Pacing: alternate between a wide and a punched-in framing every few seconds.

Viral-clip guidance is to change something on screen every 3-5 seconds. Cuts land
on word starts so the change feels like an editor's jump cut, not a random glitch.
"""
from __future__ import annotations

from clipengine.transcribe.whisper_transcribe import Word


def compute_cut_times(
    words: list[Word], clip_start: float, duration: float, min_gap: float = 3.0, max_gap: float = 5.0
) -> list[float]:
    """Cut times in seconds relative to clip start, spaced min_gap..max_gap apart."""
    starts = [w.start - clip_start for w in words if 0 <= w.start - clip_start < duration]
    cuts: list[float] = []
    last = 0.0
    while True:
        nxt = next((s for s in starts if s >= last + min_gap), None)
        if nxt is None or nxt > last + max_gap:
            nxt = last + (min_gap + max_gap) / 2
        # keep the final cut from landing in the last moments of the clip
        if nxt > duration - min_gap:
            break
        cuts.append(round(nxt, 2))
        last = nxt
    return cuts


def zoom_expression(cuts: list[float], zoom: float) -> str:
    """ffmpeg expression for the zoom factor at time t (1.0, then 1+zoom, alternating)."""
    if not cuts:
        return "1"
    passed = "+".join(f"gte(t,{c})" for c in cuts)
    return f"(1+{zoom}*mod({passed},2))"


def zoom_filter(cuts: list[float], zoom: float, width: int = 1080, height: int = 1920) -> str:
    """Filter chain fragment: scale up per-frame by the zoom expression, crop back to size."""
    if not cuts:
        return ""
    z = zoom_expression(cuts, zoom)
    return f"scale=w='{width}*{z}':h='{height}*{z}':eval=frame,crop={width}:{height}"
