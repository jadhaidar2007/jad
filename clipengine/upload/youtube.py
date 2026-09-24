"""Upload a clip to YouTube as a Short.

Setup (one-time, per YouTube channel):
  1. Google Cloud Console -> new project -> enable "YouTube Data API v3".
  2. OAuth consent screen -> External -> add your channel's Google account as a test user
     (or publish the app once verified).
  3. Credentials -> Create OAuth client ID -> Desktop app -> download the JSON,
     save it as the path in YOUTUBE_CLIENT_SECRETS_FILE.
  4. Run `python -m clipengine.upload.youtube --auth` once, interactively, to mint
     a refresh token saved at YOUTUBE_TOKEN_FILE. After that, uploads are fully
     unattended (token auto-refreshes).
"""
from __future__ import annotations

import logging
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from clipengine import config

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _get_credentials() -> Credentials:
    token_path = Path(config.YOUTUBE_TOKEN_FILE)
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not config.YOUTUBE_CLIENT_SECRETS_FILE:
                raise RuntimeError(
                    "No YouTube token found and YOUTUBE_CLIENT_SECRETS_FILE not set. "
                    "Run the one-time interactive auth first (see module docstring)."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                config.YOUTUBE_CLIENT_SECRETS_FILE, SCOPES
            )
            creds = flow.run_local_server(port=0)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json())

    return creds


def upload_short(file_path: Path, title: str, description: str, tags: list[str] | None = None) -> str:
    creds = _get_credentials()
    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": title[:100],
            "description": f"{description}\n\n#shorts",
            "tags": tags or [],
            "categoryId": "22",
        },
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
    }
    media = MediaFileUpload(str(file_path), chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            logger.info("YouTube upload progress: %d%%", int(status.progress() * 100))

    video_id = response["id"]
    logger.info("Uploaded YouTube Short: https://youtube.com/shorts/%s", video_id)
    return video_id


if __name__ == "__main__":
    import sys

    if "--auth" in sys.argv:
        _get_credentials()
        print("YouTube auth complete, token saved.")
