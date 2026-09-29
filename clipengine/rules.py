"""Turn a creator's free-text rulebook into enforceable constraints."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from clipengine import llm

logger = logging.getLogger(__name__)

PARSE_PROMPT = """You extract hard constraints from a content creator's clipping rulebook.
Return STRICT JSON with exactly these keys (use null / [] when the rulebook says nothing):
{"min_seconds": int|null, "max_seconds": int|null, "max_clips": int|null,
 "required_hashtags": ["#tag", ...], "required_mentions": ["@handle", ...],
 "banned_terms": ["word or short phrase that must NOT appear in the clip's spoken content", ...]}
Only include banned_terms for things that can be detected in spoken words (profanity, names,
brands, topics expressed as keywords). Do not invent constraints that are not in the text."""


@dataclass
class Rules:
    raw: str = ""
    min_seconds: int | None = None
    max_seconds: int | None = None
    max_clips: int | None = None
    required_hashtags: list[str] = field(default_factory=list)
    required_mentions: list[str] = field(default_factory=list)
    banned_terms: list[str] = field(default_factory=list)

    def caption_suffix(self) -> str:
        return " ".join(self.required_mentions + self.required_hashtags)

    def violates(self, spoken_text: str) -> str | None:
        lowered = spoken_text.lower()
        for term in self.banned_terms:
            if re.search(rf"\b{re.escape(term.lower())}\b", lowered):
                return term
        return None


def parse_rulebook(rulebook: str | None) -> Rules:
    if not rulebook or not rulebook.strip():
        return Rules()
    data = llm.chat_json(PARSE_PROMPT, rulebook.strip(), max_tokens=800)
    rules = Rules(
        raw=rulebook.strip(),
        min_seconds=_int_or_none(data.get("min_seconds")),
        max_seconds=_int_or_none(data.get("max_seconds")),
        max_clips=_int_or_none(data.get("max_clips")),
        required_hashtags=[str(h) for h in data.get("required_hashtags") or []],
        required_mentions=[str(m) for m in data.get("required_mentions") or []],
        banned_terms=[str(t) for t in data.get("banned_terms") or []],
    )
    logger.info("Parsed rulebook: %s", rules)
    return rules


def _int_or_none(v) -> int | None:
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None
