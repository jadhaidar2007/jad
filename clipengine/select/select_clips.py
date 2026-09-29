"""Step 3: ask an LLM to pick the best standalone moments from the transcript."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import anthropic

from clipengine import config
from clipengine.transcribe.whisper_transcribe import Transcript

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You select the best short-form clips from a long-form video transcript \
for a clipping business that posts to TikTok, YouTube Shorts, and Instagram Reels.

Pick moments that work as STANDALONE clips with no context from the rest of the video:
- A strong hook in the first 2-3 seconds (a bold claim, question, or punchline setup)
- A complete thought/story/argument that resolves within the clip
- High emotional charge, controversy, humor, a surprising fact, or a clear payoff
- Natural start/end points that don't cut off mid-sentence

Avoid: rambling intros, filler, moments that require earlier context to make sense.

Return STRICT JSON only, no prose, matching this schema:
{"clips": [{"start": <seconds float>, "end": <seconds float>, "title": "<short punchy caption, <60 chars>", "hook": "<the on-screen hook text for the first line of the clip>", "score": <0-100 int, virality estimate>}]}
"""


@dataclass
class ClipPick:
    start: float
    end: float
    title: str
    hook: str
    score: int


def select_clips(
    transcript: Transcript,
    max_clips: int = None,
    campaign_guidelines: str | None = None,
) -> list[ClipPick]:
    """campaign_guidelines: paste-in text from a Whop (or any) clipping
    campaign brief — required clip themes, banned topics, required
    hashtags/mentions, tone, min/max length overrides, etc. Injected
    directly into the selection prompt so the engine follows that specific
    campaign's rules instead of generic "best moments" picking.
    """
    max_clips = max_clips or config.MAX_CLIPS_PER_VIDEO
    if not config.ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not set — required for clip selection")

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    guidelines_block = (
        f"\n\nCAMPAIGN GUIDELINES (follow these exactly — they override the "
        f"general rules above where they conflict):\n{campaign_guidelines.strip()}\n"
        if campaign_guidelines and campaign_guidelines.strip()
        else ""
    )

    user_prompt = (
        f"Pick up to {max_clips} clips. Each clip must be between "
        f"{config.MIN_CLIP_SECONDS} and {config.MAX_CLIP_SECONDS} seconds long. "
        f"Clips must not overlap."
        f"{guidelines_block}"
        f"\n\nTRANSCRIPT (timestamps in seconds):\n"
        f"{transcript.as_prompt_text()}"
    )

    resp = client.messages.create(
        model=config.CLIP_SELECTION_MODEL,
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw_text = "".join(block.text for block in resp.content if block.type == "text")
    raw_text = raw_text.strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        raw_text = raw_text.split("\n", 1)[1] if "\n" in raw_text else raw_text

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        logger.error("Clip-selection LLM returned non-JSON: %s", raw_text[:500])
        raise

    picks = [
        ClipPick(
            start=float(c["start"]),
            end=float(c["end"]),
            title=c["title"],
            hook=c.get("hook", c["title"]),
            score=int(c.get("score", 50)),
        )
        for c in data["clips"]
    ]
    picks.sort(key=lambda c: c.score, reverse=True)
    logger.info("Selected %d clips", len(picks))
    return picks[:max_clips]
