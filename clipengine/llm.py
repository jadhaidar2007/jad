"""Thin DeepSeek client (OpenAI-compatible API) that returns parsed JSON."""
from __future__ import annotations

import json
import logging

from openai import OpenAI

from clipengine import config

logger = logging.getLogger(__name__)

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        if not config.DEEPSEEK_API_KEY:
            raise RuntimeError("DEEPSEEK_API_KEY not set")
        _client = OpenAI(
            api_key=config.DEEPSEEK_API_KEY,
            base_url=config.DEEPSEEK_BASE_URL,
            max_retries=3,
            timeout=120,
        )
    return _client


def chat_json(system: str, user: str, max_tokens: int = 4000) -> dict:
    resp = _get_client().chat.completions.create(
        model=config.LLM_MODEL,
        max_tokens=max_tokens,
        temperature=0.3,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    raw = (resp.choices[0].message.content or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.error("LLM returned non-JSON: %s", raw[:500])
        raise
