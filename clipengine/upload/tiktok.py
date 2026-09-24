"""Upload a clip to TikTok via the Content Posting API.

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
    if not config.PUBLIC_CLIP_BASE_URL:
        raise RuntimeError(
            "PUBLIC_CLIP_BASE_URL not set — TikTok pulls the video by URL, "
            "it needs to be uploaded to public storage (S3/GCS) first."
        )
    video_url = f"{config.PUBLIC_CLIP_BASE_URL.rstrip('/')}/{file_path.name}"
    access_token = _refresh_access_token() if config.TIKTOK_REFRESH_TOKEN else config.TIKTOK_ACCESS_TOKEN

    payload = {
        "post_info": {
            "title": title[:150],
            "privacy_level": "SELF_ONLY",  # flip to PUBLIC_TO_EVERYONE once the app is audited
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
        },
        "source_info": {
            "source": "PULL_FROM_URL",
            "video_url": video_url,
        },
    }
    resp = requests.post(
        INIT_URL,
        json=payload,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    publish_id = data["data"]["publish_id"]
    logger.info("TikTok publish initiated: %s", publish_id)
    return publish_id
