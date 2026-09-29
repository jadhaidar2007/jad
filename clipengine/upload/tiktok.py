"""Upload a clip to TikTok via the Content Posting API.

Uses FILE_UPLOAD (direct chunked PUT of the local file) instead of
PULL_FROM_URL, so no public bucket/S3 hosting is needed — this keeps
TikTok posting at $0 infra cost beyond the API call itself.

Setup (one-time, per TikTok account):
  1. Register a developer app at developers.tiktok.com -> add the
     "Content Posting API" product.
  2. Unaudited apps can only post to accounts in "private/sandbox" mode with a
     30-day cap — to post publicly at scale you must submit the app for audit
     (describe it as an automated clipping/repurposing tool). This review is
     the one step nobody can automate for you.
  3. Complete the OAuth flow once per creator account to get an access_token +
     refresh_token (scope: video.publish). Store them as TIKTOK_ACCESS_TOKEN /
     TIKTOK_REFRESH_TOKEN; this module auto-refreshes after that.

Docs: https://developers.tiktok.com/doc/content-posting-api-get-started
"""
from __future__ import annotations

import logging
from pathlib import Path

import requests

from clipengine import config

logger = logging.getLogger(__name__)

TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
INIT_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"

CHUNK_SIZE = 10 * 1024 * 1024  # 10MB, TikTok's recommended chunk size


def _refresh_access_token() -> str:
    resp = requests.post(
        TOKEN_URL,
        data={
            "client_key": config.TIKTOK_CLIENT_KEY,
            "client_secret": config.TIKTOK_CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": config.TIKTOK_REFRESH_TOKEN,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def upload_video(file_path: Path, title: str) -> str:
    access_token = _refresh_access_token() if config.TIKTOK_REFRESH_TOKEN else config.TIKTOK_ACCESS_TOKEN
    video_size = file_path.stat().st_size
    total_chunk_count = max(1, (video_size + CHUNK_SIZE - 1) // CHUNK_SIZE)

    payload = {
        "post_info": {
            "title": title[:150],
            "privacy_level": "SELF_ONLY",  # flip to PUBLIC_TO_EVERYONE once the app is audited
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": video_size,
            "chunk_size": min(CHUNK_SIZE, video_size),
            "total_chunk_count": total_chunk_count,
        },
    }
    init_resp = requests.post(
        INIT_URL,
        json=payload,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        timeout=30,
    )
    init_resp.raise_for_status()
    init_data = init_resp.json()["data"]
    publish_id = init_data["publish_id"]
    upload_url = init_data["upload_url"]

    with open(file_path, "rb") as f:
        video_bytes = f.read()

    put_resp = requests.put(
        upload_url,
        data=video_bytes,
        headers={
            "Content-Type": "video/mp4",
            "Content-Range": f"bytes 0-{video_size - 1}/{video_size}",
        },
        timeout=120,
    )
    put_resp.raise_for_status()

    logger.info("TikTok publish initiated (FILE_UPLOAD): %s", publish_id)
    return publish_id
