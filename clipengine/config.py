"""Central config loaded from environment variables (.env)."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
WORK_DIR = Path(os.getenv("CLIPENGINE_WORK_DIR", BASE_DIR / "workdir"))
WORK_DIR.mkdir(parents=True, exist_ok=True)

# LLM used to pick the best moments from the transcript
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")

# Whisper transcription
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "small")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")  # "cuda" if you have a GPU
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")

# Clip generation
MAX_CLIPS_PER_VIDEO = int(os.getenv("MAX_CLIPS_PER_VIDEO", "10"))
MIN_CLIP_SECONDS = int(os.getenv("MIN_CLIP_SECONDS", "25"))
MAX_CLIP_SECONDS = int(os.getenv("MAX_CLIP_SECONDS", "60"))
OUTPUT_ASPECT = os.getenv("OUTPUT_ASPECT", "9:16")

# YouTube Data API (upload as Shorts)
YOUTUBE_CLIENT_SECRETS_FILE = os.getenv("YOUTUBE_CLIENT_SECRETS_FILE", "")
YOUTUBE_TOKEN_FILE = os.getenv("YOUTUBE_TOKEN_FILE", str(BASE_DIR / "secrets" / "youtube_token.json"))

# TikTok Content Posting API
TIKTOK_CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY", "")
TIKTOK_CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET", "")
TIKTOK_ACCESS_TOKEN = os.getenv("TIKTOK_ACCESS_TOKEN", "")
TIKTOK_REFRESH_TOKEN = os.getenv("TIKTOK_REFRESH_TOKEN", "")

# Instagram Graph API (Reels)
IG_ACCESS_TOKEN = os.getenv("IG_ACCESS_TOKEN", "")
IG_BUSINESS_ACCOUNT_ID = os.getenv("IG_BUSINESS_ACCOUNT_ID", "")
IG_APP_ID = os.getenv("IG_APP_ID", "")
IG_APP_SECRET = os.getenv("IG_APP_SECRET", "")

# Only needed if "instagram" is in ENABLED_PLATFORMS — Instagram's Graph API
# requires clips to be pulled from a public URL. TikTok uploads the local
# file directly and does not need this. Cloudflare R2's free tier (10GB
# storage, no egress fee) keeps this at $0 for low clip volume.
PUBLIC_CLIP_BASE_URL = os.getenv("PUBLIC_CLIP_BASE_URL", "")

# Redis-backed job queue
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

ENABLED_PLATFORMS = [
    p.strip()
    for p in os.getenv("ENABLED_PLATFORMS", "tiktok,instagram").split(",")
    if p.strip()
]
