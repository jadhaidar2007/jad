"""Upload a clip to Instagram as a Reel via the Instagram Graph API.

Setup (one-time, per IG account):
  1. Convert the IG account to a Professional (Business/Creator) account and
     link it to a Facebook Page.
  2. Create a Meta developer app at developers.facebook.com, add the
     "Instagram Graph API" product.
  3. Generate a long-lived Page/IG access token with scopes
     instagram_content_publish + pages_show_list, and note the IG business
     account ID (IG_BUSINESS_ACCOUNT_ID). Meta requires an app review for
     instagram_content_publish beyond your own test accounts.
  4. Store IG_ACCESS_TOKEN / IG_BUSINESS_ACCOUNT_ID; tokens last ~60 days and
     should be refreshed by a scheduled job (not included here — add a cron
     hitting the token-refresh endpoint before expiry).

Docs: https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reels-publishing
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

import requests

from clipengine import config

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.facebook.com/v19.0"


def upload_reel(file_path: Path, caption: str) -> str:
    if not config.PUBLIC_CLIP_BASE_URL:
        raise RuntimeError(
            "PUBLIC_CLIP_BASE_URL not set — Instagram pulls the video by URL, "
            "it needs to be uploaded to public storage (S3/GCS) first."
        )
    video_url = f"{config.PUBLIC_CLIP_BASE_URL.rstrip('/')}/{file_path.name}"

    # 1. Create a media container
    create_resp = requests.post(
        f"{GRAPH_BASE}/{config.IG_BUSINESS_ACCOUNT_ID}/media",
        data={
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption[:2200],
            "access_token": config.IG_ACCESS_TOKEN,
        },
        timeout=30,
    )
    create_resp.raise_for_status()
    container_id = create_resp.json()["id"]

    # 2. Poll until the container finishes processing
    status_url = f"{GRAPH_BASE}/{container_id}"
    for _ in range(30):
        status_resp = requests.get(
            status_url,
            params={"fields": "status_code", "access_token": config.IG_ACCESS_TOKEN},
            timeout=30,
        )
        status_resp.raise_for_status()
        status_code = status_resp.json().get("status_code")
        if status_code == "FINISHED":
            break
        if status_code == "ERROR":
            raise RuntimeError(f"IG container {container_id} failed processing")
        time.sleep(10)
    else:
        raise TimeoutError(f"IG container {container_id} did not finish in time")

    # 3. Publish
    publish_resp = requests.post(
        f"{GRAPH_BASE}/{config.IG_BUSINESS_ACCOUNT_ID}/media_publish",
        data={"creation_id": container_id, "access_token": config.IG_ACCESS_TOKEN},
        timeout=30,
    )
    publish_resp.raise_for_status()
    media_id = publish_resp.json()["id"]
    logger.info("Published IG Reel: %s", media_id)
    return media_id
