"""Step 2: transcribe the source video with word-level timestamps."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from faster_whisper import WhisperModel

from clipengine import config

logger = logging.getLogger(__name__)

_model: WhisperModel | None = None


def _get_model() -> WhisperModel:
    global _model
    if _model is None:
        _model = WhisperModel(
            config.WHISPER_MODEL_SIZE,
            device=config.WHISPER_DEVICE,
            compute_type=config.WHISPER_COMPUTE_TYPE,
            cpu_threads=config.WHISPER_THREADS,
        )
    return _model


@dataclass
class Word:
    start: float
    end: float
    text: str


@dataclass
class Segment:
    start: float
    end: float
    text: str
    words: list[Word] = field(default_factory=list)


@dataclass
class Transcript:
    segments: list[Segment]

    def as_prompt_text(self) -> str:
        """Flattened, timestamped transcript for the clip-selection LLM."""
        lines = []
        for seg in self.segments:
            lines.append(f"[{seg.start:.1f}-{seg.end:.1f}] {seg.text.strip()}")
        return "\n".join(lines)

    def to_json(self) -> dict:
        return {
            "segments": [
                {
                    "start": s.start,
                    "end": s.end,
                    "text": s.text,
                    "words": [{"start": w.start, "end": w.end, "text": w.text} for w in s.words],
                }
                for s in self.segments
            ]
        }


def transcribe(video_path: Path, cache_dir: Path) -> Transcript:
    cache_file = cache_dir / f"{video_path.stem}.transcript.json"
    if cache_file.exists():
        logger.info("Using cached transcript %s", cache_file)
        data = json.loads(cache_file.read_text())
        return Transcript(
            segments=[
                Segment(
                    start=s["start"],
                    end=s["end"],
                    text=s["text"],
                    words=[Word(**w) for w in s["words"]],
                )
                for s in data["segments"]
            ]
        )

    model = _get_model()
    segments_iter, _info = model.transcribe(str(video_path), word_timestamps=True)

    segments = []
    for seg in segments_iter:
        words = [Word(start=w.start, end=w.end, text=w.word) for w in (seg.words or [])]
        segments.append(Segment(start=seg.start, end=seg.end, text=seg.text, words=words))

    transcript = Transcript(segments=segments)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(transcript.to_json()))
    logger.info("Transcribed %s (%d segments)", video_path, len(segments))
    return transcript
