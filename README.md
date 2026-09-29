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
Set `DEEPSEEK_API_KEY` — used to rank transcript segments into the best
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

## 3. Keeping this at ~$0 recurring cost

The whole pipeline is designed so the only real marginal cost is the LLM
call, and even that is fractions of a cent per video:

| Component | Cost | How |
|---|---|---|
| Download (yt-dlp), transcription (Whisper), editing (ffmpeg) | **$0** | All open-source, run on your own hardware/electricity |
| Clip selection + rulebook parsing LLM | **~fractions of a cent/video** | DeepSeek (`deepseek-chat`) via its OpenAI-compatible API — a few thousand tokens per video, so a $3 balance covers a very large number of videos (check DeepSeek's pricing page for current rates) |
| TikTok upload | **$0** | Uses TikTok's direct `FILE_UPLOAD` — your file goes straight to TikTok, no bucket/hosting required |
| Instagram upload | **$0 at low volume** | Instagram's API requires a public URL to pull from — point `PUBLIC_CLIP_BASE_URL` at a [Cloudflare R2](https://developers.cloudflare.com/r2/) bucket (10GB storage + unlimited free egress on the free tier) |
| Hosting | **$0** | Run `docker compose up` on your own PC instead of a cloud VM — Redis + the worker + the API all run fine locally; nothing here needs to be always-on unless you want jobs to run while your machine is off |
| Whisper compute | **$0** | `WHISPER_MODEL_SIZE=small` on CPU is free and fast enough for the 15-min target; only pay for a GPU box if you outgrow local hardware |

**If you're TikTok-only for now**, set `ENABLED_PLATFORMS=tiktok` in `.env` —
that drops the Instagram/R2 storage step entirely and the only cost left in
the whole system is the sub-cent DeepSeek calls per video.

**Rulebook (per video):** every job takes the creator's do/don't rules as
free text in the `rulebook` field. DeepSeek reads the rulebook twice:

1. **Parsed into hard constraints** and enforced in code: min/max clip length,
   max clips, required hashtags/@mentions (appended to every caption), and
   banned words/phrases (any clip whose spoken text contains one is dropped).
2. **Passed into the clip-picking prompt** so softer rules (tone, topics to
   avoid, content types) shape which moments get chosen.

```bash
curl -X POST localhost:8000/clip \
  -H 'Content-Type: application/json' \
  -d '{
    "youtube_url": "https://youtu.be/VIDEO_ID",
    "rulebook": "Clips 20-45s. Must include #ad and tag @creator. No profanity. No clips about politics. No sponsor segments."
  }'
```

## 4. Tuning

- `MAX_CLIPS_PER_VIDEO`, `MIN_CLIP_SECONDS`, `MAX_CLIP_SECONDS` — clip count/length.
- `WHISPER_MODEL_SIZE` — `small` is the CPU-friendly default; use `medium`/`large-v3`
  with `WHISPER_DEVICE=cuda` on a GPU box for better transcripts, still fast enough
  to hit the 15-minute budget.
- `ENABLED_PLATFORMS` — defaults to `tiktok,instagram`; set to `tiktok` alone while you're TikTok-only.
- TikTok's `privacy_level` in `clipengine/upload/tiktok.py` defaults to
  `SELF_ONLY` — flip to `PUBLIC_TO_EVERYONE` only once your app has passed audit.

## 5. What earns money (research notes, Sept 2026)

**What makes clips get views** (OpusClip's analysis of 13.5M clips, plus other 2026 guides):
- Length: viral median is ~41s; 30-45s is the sweet spot (defaults are now 25-60s).
- Hook: show the payoff/outcome in the first 3 seconds. Strong hooks keep 80-90% of viewers through 3s.
- Captions: ~80% of viral clips have burned-in captions, ~79% animate them; accurate captions lift retention ~12%.
- Pacing: change something on screen every 3-5s. **Built:** clips alternate between a wide and a 12% punched-in framing, with cuts landing on word starts (`PACING_ENABLED`, `PACING_ZOOM` in `.env`).

**What pays** (Whop listings, 2026): advertised $0.20-$6 per 1,000 views, but the *blended* average
payout is closer to $0.39/1k because of per-clip caps, minimum-watch-time filters, and bot filtering.
Rough CPM by niche: crypto/web3 $4-9, finance/trading $4-6, SaaS/B2B $3-6, gaming/streamers $1-4
(lowest pay but most open campaigns and easiest views).

**Implications:** volume across many campaigns matters more than any one clip; pick campaigns with
no or high per-clip caps; check whether views count only past a watch-time threshold (retention
matters more than raw reach); higher-CPM niches usually mean stricter rulebooks and more competition.

## 6. Legal/ToS note

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
