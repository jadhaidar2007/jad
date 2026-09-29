"""HTTP entry point: POST a YouTube link, get a job id; the RQ worker does the rest.

Run:
    uvicorn clipengine.api.server:app --host 0.0.0.0 --port 8000

Then:
    curl -X POST localhost:8000/clip -d '{"youtube_url": "https://youtu.be/..."}' \
         -H 'Content-Type: application/json'
"""
from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel
from redis import Redis
from rq import Queue
from rq.job import Job

from clipengine import config

app = FastAPI(title="ClipEngine")
redis_conn = Redis.from_url(config.REDIS_URL)
queue = Queue("clipengine", connection=redis_conn, default_timeout=1800)


class ClipRequest(BaseModel):
    youtube_url: str
    campaign_guidelines: str | None = None  # paste the Whop campaign brief here


@app.post("/clip")
def enqueue_clip_job(req: ClipRequest):
    job = queue.enqueue(
        "clipengine.worker.tasks.process_video", req.youtube_url, req.campaign_guidelines
    )
    return {"job_id": job.id, "status": job.get_status()}


@app.get("/clip/{job_id}")
def get_job_status(job_id: str):
    job = Job.fetch(job_id, connection=redis_conn)
    return {
        "job_id": job.id,
        "status": job.get_status(),
        "result": job.result,
        "error": str(job.exc_info) if job.exc_info else None,
    }


@app.get("/health")
def health():
    return {"status": "ok"}
