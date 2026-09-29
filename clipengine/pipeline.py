"""End-to-end orchestrator: YouTube link in -> clips posted everywhere, out.

Target: under 15 minutes wall-clock for a typical <30min source video on a
machine with a decent CPU (faster with a GPU for the Whisper step).
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from clipengine import config
from clipengine.edit.clipper import render_clip
from clipengine.ingest.download import download_video
from clipengine.rules import parse_rulebook
from clipengine.select.select_clips import select_clips
from clipengine.transcribe.whisper_transcribe import transcribe
from clipengine.upload import instagram, storage, tiktok, youtube

logger = logging.getLogger(__name__)


@dataclass
class ClipResult:
    title: str
    file_path: str
    posted_to: list[str] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)


@dataclass
class PipelineResult:
    video_id: str
    video_title: str
    clips: list[ClipResult]
    elapsed_seconds: float


def run_pipeline(youtube_url: str, rulebook: str | None = None) -> PipelineResult:
    t0 = time.monotonic()
    rules = parse_rulebook(rulebook)
    run_dir = config.WORK_DIR / str(int(t0))
    run_dir.mkdir(parents=True, exist_ok=True)

    logger.info("[1/4] Downloading %s", youtube_url)
    source = download_video(youtube_url, run_dir)

    logger.info("[2/4] Transcribing %s", source.file_path.name)
    transcript = transcribe(source.file_path, run_dir)

    logger.info("[3/4] Selecting best moments")
    picks = select_clips(transcript, rules, source.duration_s)
    if not picks:
        logger.warning("No clips selected for %s", youtube_url)
        return PipelineResult(source.video_id, source.title, [], time.monotonic() - t0)

    logger.info("[4/4] Rendering + posting %d clips", len(picks))
    clips_dir = run_dir / "clips"
    results: list[ClipResult] = []

    for pick in picks:
        try:
            rendered = render_clip(source.file_path, transcript, pick, clips_dir, config.OUTPUT_ASPECT)
        except Exception:
            logger.exception("Render failed for clip %s", pick.title)
            continue

        result = ClipResult(title=pick.title, file_path=str(rendered.file_path))
        suffix = rules.caption_suffix()
        title = f"{pick.title} {suffix}".strip()
        caption = f"{pick.hook}\n\n{pick.title}\n\n{suffix}".strip()
        _post_everywhere(rendered.file_path, title, caption, result)
        results.append(result)

    elapsed = time.monotonic() - t0
    logger.info("Pipeline finished in %.1fs for %s", elapsed, source.title)
    return PipelineResult(source.video_id, source.title, results, elapsed)


def _post_everywhere(file_path, title: str, caption: str, result: ClipResult) -> None:
    # TikTok uploads the local file directly (FILE_UPLOAD) — no public
    # storage needed. Only Instagram's Graph API requires a public URL.
    public_url_ready = False
    if "instagram" in config.ENABLED_PLATFORMS:
        try:
            storage.publish_to_public_storage(file_path)
            public_url_ready = True
        except Exception as e:
            logger.exception("Failed to publish clip to public storage")
            result.errors["instagram"] = f"storage upload failed: {e}"

    if "youtube" in config.ENABLED_PLATFORMS:
        try:
            youtube.upload_short(file_path, title, caption)
            result.posted_to.append("youtube")
        except Exception as e:
            logger.exception("YouTube upload failed")
            result.errors["youtube"] = str(e)

    if "tiktok" in config.ENABLED_PLATFORMS:
        try:
            tiktok.upload_video(file_path, title)
            result.posted_to.append("tiktok")
        except Exception as e:
            logger.exception("TikTok upload failed")
            result.errors["tiktok"] = str(e)

    if "instagram" in config.ENABLED_PLATFORMS and public_url_ready:
        try:
            instagram.upload_reel(file_path, caption)
            result.posted_to.append("instagram")
        except Exception as e:
            logger.exception("Instagram upload failed")
            result.errors["instagram"] = str(e)
