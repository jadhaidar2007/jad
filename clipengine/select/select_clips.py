"""Step 3: pick the moments most likely to go viral, within the creator's rulebook."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from clipengine import config, llm
from clipengine.rules import Rules
from clipengine.transcribe.whisper_transcribe import Transcript

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a short-form video editor picking the clips most likely to go VIRAL \
on TikTok, Instagram Reels and YouTube Shorts from a long-form video transcript.

Viral clips are STANDALONE (no outside context needed) and have:
- A hook in the first 3 seconds that puts the payoff or outcome up front (bold claim, surprising
  result, question) so viewers know what they get before deciding to swipe
- Ideal length 30-45 seconds unless the rulebook says otherwise
- A complete arc that pays off before the clip ends
- Strong emotion: controversy, humor, surprise, a valuable insight, or a story climax
- Clean start and end points at sentence boundaries

Skip intros, filler, sponsor reads, and anything that needs earlier context.

The creator's RULEBOOK is binding. Never pick a moment that breaks it. If a moment is great
but violates the rulebook, skip it.

Return STRICT JSON only:
{"clips": [{"start": <seconds float>, "end": <seconds float>,
            "title": "<punchy caption under 60 chars>",
            "hook": "<on-screen hook text for the first seconds>",
            "score": <0-100 virality estimate>}]}
Use the exact timestamps from the transcript."""


@dataclass
class ClipPick:
    start: float
    end: float
    title: str
    hook: str
    score: int


def _spoken_text(transcript: Transcript, start: float, end: float) -> str:
    return " ".join(
        seg.text.strip()
        for seg in transcript.segments
        if seg.end > start and seg.start < end
    )


def select_clips(
    transcript: Transcript,
    rules: Rules,
    video_duration_s: float,
    max_clips: int | None = None,
) -> list[ClipPick]:
    max_clips = rules.max_clips or max_clips or config.MAX_CLIPS_PER_VIDEO
    min_s = rules.min_seconds or config.MIN_CLIP_SECONDS
    max_s = rules.max_seconds or config.MAX_CLIP_SECONDS

    rulebook_block = (
        f"\n\nCREATOR RULEBOOK (binding):\n{rules.raw}\n" if rules.raw else "\n\nNo rulebook provided.\n"
    )
    user_prompt = (
        f"Pick up to {max_clips} clips, each between {min_s} and {max_s} seconds long, "
        f"non-overlapping. Ask for a few extra candidates if unsure — quality over quantity."
        f"{rulebook_block}\nTRANSCRIPT (timestamps in seconds):\n{transcript.as_prompt_text()}"
    )

    data = llm.chat_json(SYSTEM_PROMPT, user_prompt, max_tokens=4000)

    candidates: list[ClipPick] = []
    for c in data.get("clips", []):
        try:
            candidates.append(
                ClipPick(
                    start=max(0.0, float(c["start"])),
                    end=min(video_duration_s or float("inf"), float(c["end"])),
                    title=str(c["title"]),
                    hook=str(c.get("hook") or c["title"]),
                    score=int(c.get("score", 50)),
                )
            )
        except (KeyError, TypeError, ValueError):
            logger.warning("Skipping malformed clip entry: %s", c)

    picks: list[ClipPick] = []
    for pick in sorted(candidates, key=lambda p: p.score, reverse=True):
        length = pick.end - pick.start
        if length < min_s or length > max_s:
            logger.info("Dropping '%s': length %.1fs outside %d-%ds", pick.title, length, min_s, max_s)
            continue
        if any(pick.start < p.end and pick.end > p.start for p in picks):
            continue
        violated = rules.violates(_spoken_text(transcript, pick.start, pick.end))
        if violated:
            logger.info("Dropping '%s': contains banned term '%s'", pick.title, violated)
            continue
        picks.append(pick)
        if len(picks) >= max_clips:
            break

    logger.info("Selected %d clips (from %d candidates)", len(picks), len(candidates))
    return picks
