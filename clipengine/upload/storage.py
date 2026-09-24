"""Push a rendered clip to public storage so TikTok/Instagram can pull it by URL.

Uses any S3-compatible bucket (AWS S3, Cloudflare R2, Backblaze B2, etc).
Configure via standard AWS env vars (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY,
AWS_DEFAULT_REGION) plus CLIPENGINE_S3_BUCKET / CLIPENGINE_S3_ENDPOINT_URL.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import boto3

logger = logging.getLogger(__name__)

_BUCKET = os.getenv("CLIPENGINE_S3_BUCKET", "")
_ENDPOINT_URL = os.getenv("CLIPENGINE_S3_ENDPOINT_URL") or None


def publish_to_public_storage(file_path: Path) -> str:
    """Upload a clip and return its public URL (matches config.PUBLIC_CLIP_BASE_URL)."""
    if not _BUCKET:
        raise RuntimeError("CLIPENGINE_S3_BUCKET not set")

    s3 = boto3.client("s3", endpoint_url=_ENDPOINT_URL)
    key = file_path.name
    s3.upload_file(
        str(file_path),
        _BUCKET,
        key,
        ExtraArgs={"ContentType": "video/mp4", "ACL": "public-read"},
    )
    logger.info("Uploaded %s to s3://%s/%s", file_path.name, _BUCKET, key)
    from clipengine import config

    return f"{config.PUBLIC_CLIP_BASE_URL.rstrip('/')}/{key}"
