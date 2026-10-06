"""Step 2: transcribe the source video with word-level timestamps.

Two backends, chosen by WHISPER_BACKEND:
  mlx     - mlx-whisper, runs on the Apple Silicon GPU (fast and much cooler on a MacBook)
  faster  - faster-whisper on CPU (works anywhere)
  auto    - mlx on an Apple Silicon Mac when mlx-whisper is installed, otherwise faster
"""
from __future__ import annotations

import json
import logging
import platform
from dataclasses import dataclass, field
from pathlib import Path

from clipengine import config

logger = logging.getLogger(__name__)

_faster_model = None


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


def _mlx_available() -> bool:
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        return False
    try:
        import mlx_whisper  # noqa: F401
    except ImportError:
        return False
    return True


def _pick_backend() -> str:
    choice = config.WHISPER_BACKEND
    if choice == "mlx":
        if not _mlx_available():
            raise RuntimeError("WHISPER_BACKEND=mlx needs an Apple Silicon Mac and `pip install mlx-whisper`")
        return "mlx"
    if choice == "faster":
        return "faster"
    return "mlx" if _mlx_available() else "faster"


def _mlx_repo() -> str:
    if config.WHISPER_MLX_MODEL:
        return config.WHISPER_MLX_MODEL
    return f"mlx-community/whisper-{config.WHISPER_MODEL_SIZE}-mlx"


def _segments_from_mlx(result: dict) -> list[Segment]:
    segments = []
    for seg in result.get("segments", []):
        words = [
            Word(start=float(w["start"]), end=float(w["end"]), text=w["word"])
            for w in seg.get("words") or []
        ]
        segments.append(Segment(start=float(seg["start"]), end=float(seg["end"]), text=seg["text"], words=words))
    return segments


def _run_mlx(video_path: Path) -> list[Segment]:
    import mlx_whisper

    repo = _mlx_repo()
    logger.info("Transcribing with mlx-whisper (%s)", repo)
    result = mlx_whisper.transcribe(str(video_path), path_or_hf_repo=repo, word_timestamps=True)
    return _segments_from_mlx(result)


def _run_faster(video_path: Path) -> list[Segment]:
    global _faster_model
    from faster_whisper import WhisperModel

    if _faster_model is None:
        _faster_model = WhisperModel(
            config.WHISPER_MODEL_SIZE,
            device=config.WHISPER_DEVICE,
            compute_type=config.WHISPER_COMPUTE_TYPE,
            cpu_threads=config.WHISPER_THREADS,
        )
    logger.info("Transcribing with faster-whisper (%s)", config.WHISPER_MODEL_SIZE)
    segments_iter, _info = _faster_model.transcribe(str(video_path), word_timestamps=True)
    segments = []
    for seg in segments_iter:
        words = [Word(start=w.start, end=w.end, text=w.word) for w in (seg.words or [])]
        segments.append(Segment(start=seg.start, end=seg.end, text=seg.text, words=words))
    return segments


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

    backend = _pick_backend()
    segments = _run_mlx(video_path) if backend == "mlx" else _run_faster(video_path)

    transcript = Transcript(segments=segments)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(transcript.to_json()))
    logger.info("Transcribed %s (%d segments, backend=%s)", video_path, len(segments), backend)
    return transcript
