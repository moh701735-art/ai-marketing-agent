"""HTTP API for the video montage pipeline (used by n8n).

POST /jobs          multipart: video (file) or video_url, words (JSON), bg (navy|black|green|orange)
GET  /jobs/{id}     status
GET  /jobs/{id}/video   final MP4 when status == done
Auth: header X-API-Key must equal env RENDER_API_KEY.
"""
import json
import os
import shutil
import tempfile
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import httpx
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse

from pipeline import render_video

API_KEY = os.environ.get("RENDER_API_KEY", "")
DATA = os.environ.get("RENDER_DATA_DIR", tempfile.gettempdir())
app = FastAPI(title="Video montage service")
pool = ThreadPoolExecutor(max_workers=1)
jobs: dict = {}
lock = threading.Lock()


def auth(x_api_key: str = Header(default="")):
    if not API_KEY or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="invalid api key")


@app.get("/health")
def health():
    return {"ok": True}


def _work(job_id: str, video_path: str, words: list, bg: str):
    def progress(msg):
        with lock:
            jobs[job_id]["step"] = msg

    out = os.path.join(DATA, f"{job_id}.mp4")
    try:
        with lock:
            jobs[job_id]["status"] = "running"
        info = render_video(video_path, words, out, bg_style=bg, progress=progress)
        with lock:
            jobs[job_id].update(status="done", info=info, file=out)
    except Exception as e:  # noqa: BLE001 - report any failure to the caller
        with lock:
            jobs[job_id].update(status="failed", error=str(e)[:500])
    finally:
        try:
            os.remove(video_path)
        except OSError:
            pass


@app.post("/jobs", dependencies=[Depends(auth)])
async def create_job(video: UploadFile = File(None), video_url: str = Form(""), words: str = Form("[]"), bg: str = Form("navy")):
    try:
        word_list = json.loads(words)
        assert isinstance(word_list, list)
    except Exception:
        raise HTTPException(status_code=400, detail="words must be a JSON list of {w,s,e}")
    job_id = uuid.uuid4().hex[:12]
    src = os.path.join(DATA, f"{job_id}_in.mp4")
    if video is not None:
        with open(src, "wb") as f:
            shutil.copyfileobj(video.file, f)
    elif video_url:
        async with httpx.AsyncClient(follow_redirects=True, timeout=300) as c:
            r = await c.get(video_url)
            if r.status_code != 200:
                raise HTTPException(status_code=400, detail=f"could not download video ({r.status_code})")
            with open(src, "wb") as f:
                f.write(r.content)
    else:
        raise HTTPException(status_code=400, detail="send video or video_url")
    with lock:
        jobs[job_id] = {"status": "queued", "step": "queued"}
    pool.submit(_work, job_id, src, word_list, bg)
    return {"job_id": job_id}


@app.get("/jobs/{job_id}", dependencies=[Depends(auth)])
def job_status(job_id: str):
    with lock:
        j = jobs.get(job_id)
    if not j:
        raise HTTPException(status_code=404, detail="unknown job")
    return {k: v for k, v in j.items() if k != "file"}


@app.get("/jobs/{job_id}/video", dependencies=[Depends(auth)])
def job_video(job_id: str):
    with lock:
        j = jobs.get(job_id)
    if not j or j.get("status") != "done":
        raise HTTPException(status_code=409, detail="not ready")
    return FileResponse(j["file"], media_type="video/mp4", filename=f"{job_id}.mp4")
