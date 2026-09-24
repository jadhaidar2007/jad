# ClipEngine

Send it a YouTube link, it downloads the video, transcribes it, picks up to
10 of the best standalone moments with an LLM, cuts + reframes them to 9:16
with burned-in captions, and posts each one to YouTube Shorts, TikTok, and
Instagram Reels. Runs as a queue worker so the pipeline is unattended once
it's set up — you send a link, it posts on its own.

```
YouTube link -> download -> transcribe (Whisper) -> pick best moments (LLM)
             -> cut + reframe + captions (ffmpeg) -> upload to YT/TikTok/IG
```

## 1. One-time setup (can't be automated — do this once per account)

Platforms require you to register an app and authorize it against your own
accounts before any code can post on your behalf.

### YouTube
1. Google Cloud Console -> new project -> enable **YouTube Data API v3**.
2. OAuth consent screen -> add your channel's Google account as a test user.
3. Credentials -> **OAuth client ID** -> Desktop app -> download the JSON to
   `secrets/youtube_client_secret.json`.
4. Run once, interactively: `python -m clipengine.upload.youtube --auth`
   (opens a browser, mints a refresh token saved to `secrets/youtube_token.json`).
   After this, uploads are fully unattended.

### TikTok
1. Register an app at [developers.tiktok.com](https://developers.tiktok.com),
   add the **Content Posting API** product.
2. Complete the OAuth flow once per creator account (`video.publish` scope)
   to get an access + refresh token. Put them in `.env`.
3. Unaudited apps can only post privately with a 30-day cap. To post
   **publicly** at volume, submit the app for TikTok's audit — describe it as
   an automated content-repurposing/clipping tool. This review is the one
   step that genuinely cannot be skipped or automated.

### Instagram
1. Convert the IG account to a Professional account, link it to a Facebook Page.
2. Create a Meta app at developers.facebook.com, add **Instagram Graph API**.
3. Generate a long-lived access token (`instagram_content_publish` +
   `pages_show_list`) and note the IG business account ID. Meta also
   requires app review for this scope beyond your own test accounts.
4. Tokens last ~60 days — set up a periodic refresh job before they expire.

### Storage for TikTok/Instagram
Both platforms fetch the finished clip by URL rather than accepting a raw
upload, so clips need to land somewhere public first. Point `PUBLIC_CLIP_BASE_URL`
/ `CLIPENGINE_S3_BUCKET` at any S3-compatible bucket (AWS S3, Cloudflare R2,
Backblaze B2) with public-read objects.

### LLM for clip selection
Set `ANTHROPIC_API_KEY` — used to rank transcript segments into the best
standalone clips.

## 2. Run it

```bash
cp .env.example .env    # fill in the values from step 1
docker compose up --build --scale worker=3
```

Then:

```bash
curl -X POST localhost:8000/clip \
  -H 'Content-Type: application/json' \
  -d '{"youtube_url": "https://youtu.be/VIDEO_ID"}'
# -> {"job_id": "...", "status": "queued"}

curl localhost:8000/clip/<job_id>
# -> job status, and once done: which clips posted where, and any errors
```

Scale `worker` up (`--scale worker=N`) to process multiple source videos in
parallel and stay inside the 15-minute target when several links land at once.

## 3. Tuning

- `MAX_CLIPS_PER_VIDEO`, `MIN_CLIP_SECONDS`, `MAX_CLIP_SECONDS` — clip count/length.
- `WHISPER_MODEL_SIZE` — `small` is the CPU-friendly default; use `medium`/`large-v3`
  with `WHISPER_DEVICE=cuda` on a GPU box for better transcripts, still fast enough
  to hit the 15-minute budget.
- `ENABLED_PLATFORMS` — drop platforms you haven't authorized yet, e.g. `youtube` only.
- TikTok's `privacy_level` in `clipengine/upload/tiktok.py` defaults to
  `SELF_ONLY` — flip to `PUBLIC_TO_EVERYONE` only once your app has passed audit.

## 4. Legal/ToS note

Downloading and reposting *other people's* YouTube videos without permission
is a copyright and platform-ToS risk, and none of the platforms pay for
reposted content you don't have rights to. This engine is built to point at
content you have rights to clip: your own uploads, or videos from
creators/podcasts who've opted into a clipping arrangement with you.

## Architecture

```
clipengine/
  ingest/download.py       yt-dlp download
  transcribe/               faster-whisper, word-level timestamps
  select/select_clips.py    LLM picks best moments -> start/end/title/hook
  edit/clipper.py           ffmpeg cut + 9:16 crop + burned-in captions (ASS)
  upload/
    youtube.py               YouTube Data API (OAuth, resumable upload)
    tiktok.py                TikTok Content Posting API (pull-from-url)
    instagram.py             Instagram Graph API (Reels, pull-from-url)
    storage.py                pushes clips to S3-compatible public storage
  pipeline.py                orchestrates all 4 steps end to end
  api/server.py               FastAPI: POST /clip, GET /clip/{id}
  worker/tasks.py             RQ background task run by `rq worker`
```
