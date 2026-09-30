# Video montage service

Takes a talking-head video plus approximate word timings and returns a finished
vertical MP4: silences cut, image enhanced, background replaced, Arabic
word-by-word captions and brand logo pop-ups (TikTok, Telegram, Facebook, WhatsApp).

## API (header `X-API-Key: $RENDER_API_KEY` on every call except /health)
- `POST /jobs` multipart: `video` (file) or `video_url`, `words` (JSON `[{"w","s","e"}]`, seconds in the source video), `bg` = navy|black|green|orange
- `GET /jobs/{id}` -> `{status: queued|running|done|failed, step, info, error}`
- `GET /jobs/{id}/video` -> MP4 when done

## Run locally
    pip install -r requirements.txt && playwright install chromium
    RENDER_API_KEY=change-me uvicorn app:app --port 8000

## Deploy
Docker (`Dockerfile`). Set `RENDER_API_KEY` as an environment variable. Needs about 2 GB RAM;
a 25 s clip renders in roughly 2-3 minutes.
