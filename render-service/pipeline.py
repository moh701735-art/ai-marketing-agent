"""Video montage pipeline: cut silences, enhance, replace background,
animate Arabic word-by-word captions and brand logo pop-ups, export MP4.

Input words are approximate ([{"w": str, "s": sec, "e": sec}], source timeline).
They are only used to assign each word to a detected speech segment; exact word
boundaries inside a segment are then found from the audio energy envelope.
"""
import asyncio
import json
import os
import re
import shutil
import subprocess
import tempfile
import wave

import cv2
import mediapipe as mp
import numpy as np
from playwright.async_api import async_playwright

from logos import LOGOS
from overlay_html import OVERLAY_HTML

W, H, FPS = 720, 1280, 30


def _ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


FFMPEG = _ffmpeg()


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(cmd[:4])} ... {r.stderr[-400:]}")
    return r


def duration_of(path: str) -> float:
    out = subprocess.run([FFMPEG, "-hide_banner", "-i", path], capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out)
    if not m:
        raise RuntimeError("cannot read video duration")
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])


def detect_segments(video: str, dur: float, noise="-35dB", min_sil=0.35, pad=0.10):
    err = subprocess.run(
        [FFMPEG, "-hide_banner", "-i", video, "-af", f"silencedetect=noise={noise}:d={min_sil}", "-f", "null", "-"],
        capture_output=True, text=True,
    ).stderr
    st = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", err)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", err)]
    segs, cur = [], 0.0
    for s, e in zip(st, en):
        if s - cur > 0.15:
            segs.append((cur, min(dur, s + pad)))
        cur = max(0.0, e - pad)
    if dur - cur > 0.15:
        segs.append((cur, dur))
    return segs or [(0.0, dur)]


def _norm(s: str) -> str:
    return re.sub(r"[ً-ْـ]", "", s)


def _weight(w: str) -> float:
    return max(2, len(re.sub(r"[^ء-ي0-9a-zA-Z]", "", w))) + 1.0


def _envelope(wav_path: str):
    with wave.open(wav_path) as w:
        sr = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    hop = int(0.02 * sr)
    n = len(x) // hop
    env = np.array([np.sqrt(np.mean(x[i * hop:(i + 1) * hop] ** 2) + 1e-9) for i in range(n)])
    env = 20 * np.log10(env + 1e-6)
    return np.convolve(env, np.ones(3) / 3, mode="same")


def _align(env, a, b, words):
    """Place word boundaries on energy valleys inside [a, b] (seconds)."""
    n = len(words)
    if n == 1:
        return [(a, b)]
    i0, i1 = int(a / 0.02), int(b / 0.02)
    wt = np.array([_weight(x) for x in words])
    cum = np.cumsum(wt) / wt.sum()
    exp = [i0 + (i1 - i0) * cum[j] for j in range(n - 1)]
    cand = list(range(i0 + 3, max(i0 + 4, i1 - 3)))
    if len(cand) < n:
        step = (b - a) / n
        return [(a + k * step, a + (k + 1) * step) for k in range(n)]
    valley = {}
    for f in cand:
        lo, hi = max(i0, f - 6), min(i1, f + 7)
        valley[f] = (env[lo:hi].max() - env[f]) / 20.0
    minw = 6
    best = [dict() for _ in range(n - 1)]
    for f in cand:
        best[0][f] = (valley[f] - ((f - exp[0]) / 15.0) ** 2, None)
    for j in range(1, n - 1):
        items = sorted(best[j - 1].items())
        for f in cand:
            bs = None
            for pf, (sc, _) in items:
                if pf + minw <= f and (bs is None or sc > bs[0]):
                    bs = (sc, pf)
            if bs:
                best[j][f] = (bs[0] + valley[f] - ((f - exp[j]) / 15.0) ** 2, bs[1])
    if not best[n - 2]:
        step = (b - a) / n
        return [(a + k * step, a + (k + 1) * step) for k in range(n)]
    f = max(best[n - 2], key=lambda q: best[n - 2][q][0])
    bnd = [f]
    for j in range(n - 2, 0, -1):
        f = best[j][f][1]
        bnd.append(f)
    edges = [i0] + bnd[::-1] + [i1]
    return [(edges[k] * 0.02, edges[k + 1] * 0.02) for k in range(n)]


LOGO_RULES = [
    ("tiktok", r"^(تيك|تكتوك|تيكتوك|تك|والتيك)$|tiktok"),
    ("telegram", r"تل[يىغكج]?رام|تلغرام|تليجرام|تلكرام|تلجرام|telegram"),
    ("facebook", r"^(فيسبوك|فيس|والفيسبوك|وفيسبوك)$|facebook"),
    ("whatsapp", r"واتس|وتساب|whatsapp"),
]


def build_timeline(segs, words_in, env):
    """Return (words, phrases, total_duration) on the cut timeline."""
    per_seg = [[] for _ in segs]
    for w in words_in:
        mid = (float(w["s"]) + float(w["e"])) / 2
        k = min(range(len(segs)), key=lambda i: 0 if segs[i][0] <= mid <= segs[i][1] else min(abs(mid - segs[i][0]), abs(mid - segs[i][1])))
        per_seg[k].append(str(w["w"]))
    words, phrases, off = [], [], 0.0
    for (a, b), ws in zip(segs, per_seg):
        if ws:
            idx = []
            for wd, (s, e) in zip(ws, _align(env, a, b, ws)):
                d = {"w": wd, "s": round(off + s - a, 3), "e": round(off + e - a, 3)}
                for name, pat in LOGO_RULES:
                    if re.search(pat, _norm(wd), re.I):
                        d["logo"] = name
                        break
                idx.append(len(words))
                words.append(d)
            for c in range(0, len(idx), 4):
                ch = idx[c:c + 4]
                phrases.append({"s": words[ch[0]]["s"], "e": words[ch[-1]]["e"], "idx": ch})
        off += b - a
    return words, phrases, off


def cut_and_enhance(video, segs, out):
    fc = ""
    for i, (a, b) in enumerate(segs):
        fc += f"[0:v]trim={a:.3f}:{b:.3f},setpts=PTS-STARTPTS[v{i}];[0:a]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS[a{i}];"
    fc += "".join(f"[v{i}][a{i}]" for i in range(len(segs))) + f"concat=n={len(segs)}:v=1:a=1[v0][a0];"
    fc += (f"[v0]fps={FPS},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
           "hqdn3d=2.5:2:4:3,eq=contrast=1.07:saturation=1.12:brightness=0.02:gamma=0.95,"
           "unsharp=5:5:0.7:5:5:0.0[v]")
    run([FFMPEG, "-v", "error", "-y", "-i", video, "-filter_complex", fc, "-map", "[v]", "-map", "[a0]",
         "-c:v", "libx264", "-crf", "16", "-preset", "fast", "-c:a", "aac", out])


def _background(style: str):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    palettes = {
        "navy": ([14, 22, 48], [38, 58, 120], [40, 55, 95]),
        "black": ([8, 8, 10], [28, 28, 34], [30, 30, 38]),
        "green": ([8, 40, 30], [20, 100, 70], [30, 70, 55]),
        "orange": ([50, 20, 8], [140, 70, 25], [90, 55, 30]),
    }
    top, bot, glow = (np.array(c, np.float32) for c in palettes.get(style, palettes["navy"]))
    t = yy / H
    bg = top[None, None, :] * (1 - t[..., None]) + bot[None, None, :] * t[..., None]
    g = np.exp(-(((xx - W * 0.5) / (W * 0.55)) ** 2 + ((yy - H * 0.42) / (H * 0.38)) ** 2))
    bg += g[..., None] * glow
    vig = 1 - 0.35 * (((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) * 0.6
    return np.clip(bg * vig[..., None], 0, 255)


def replace_background(src, out, style="navy"):
    bg = _background(style)
    seg = mp.solutions.selfie_segmentation.SelfieSegmentation(model_selection=0)
    dec = subprocess.Popen([FFMPEG, "-v", "error", "-i", src, "-vf", f"fps={FPS}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           stdout=subprocess.PIPE)
    enc = subprocess.Popen([FFMPEG, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                            "-i", "pipe:0", "-i", src, "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-crf", "18",
                            "-preset", "fast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", out], stdin=subprocess.PIPE)
    prev, size = None, W * H * 3
    while True:
        b = b""
        while len(b) < size:
            c = dec.stdout.read(size - len(b))
            if not c:
                break
            b += c
        if len(b) < size:
            break
        fr = np.frombuffer(b, np.uint8).reshape(H, W, 3)
        m = seg.process(fr).segmentation_mask.astype(np.float32)
        m = cv2.GaussianBlur(m, (0, 0), 3)
        m = np.clip((m - 0.40) / 0.20, 0, 1)
        m = m * m * (3 - 2 * m)
        if prev is not None:
            m = 0.55 * m + 0.45 * prev
        prev = m
        a = m[..., None]
        enc.stdin.write((fr.astype(np.float32) * a + bg * (1 - a)).astype(np.uint8).tobytes())
    enc.stdin.close()
    enc.wait()
    dec.wait()


async def _render_overlay(words, phrases, dur, frames_dir):
    html = (OVERLAY_HTML.replace("__LOGOS__", json.dumps(LOGOS))
            .replace("__WORDS__", json.dumps(words, ensure_ascii=False))
            .replace("__PHRASES__", json.dumps(phrases)))
    path = os.path.join(frames_dir, "overlay.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH") or None, args=["--no-sandbox"])
        page = await browser.new_page(viewport={"width": W, "height": H})
        await page.goto("file://" + path)
        for i in range(int(dur * FPS)):
            await page.evaluate(f"setT({i / FPS})")
            await page.screenshot(path=os.path.join(frames_dir, f"f{i:05d}.png"), omit_background=True)
        await browser.close()


def render_video(video_path: str, words: list, out_path: str, bg_style: str = "navy", final_width: int = 1080, progress=None):
    def note(msg):
        if progress:
            progress(msg)

    work = tempfile.mkdtemp(prefix="render_")
    try:
        dur = duration_of(video_path)
        note("analysing audio")
        wav = os.path.join(work, "a.wav")
        run([FFMPEG, "-v", "error", "-y", "-i", video_path, "-vn", "-ac", "1", "-ar", "16000", wav])
        env = _envelope(wav)
        segs = detect_segments(video_path, dur)
        note(f"cutting {len(segs)} speech segments")
        cut = os.path.join(work, "cut.mp4")
        cut_and_enhance(video_path, segs, cut)
        w_out, phrases, total = build_timeline(segs, words, env)
        note("replacing background")
        person = os.path.join(work, "person.mp4")
        replace_background(cut, person, bg_style)
        note("animating captions and logos")
        frames = os.path.join(work, "frames")
        os.makedirs(frames)
        asyncio.run(_render_overlay(w_out, phrases, duration_of(person), frames))
        note("exporting")
        fh = int(round(final_width * 16 / 9 / 2) * 2)
        run([FFMPEG, "-v", "error", "-y", "-i", person, "-framerate", str(FPS), "-i", os.path.join(frames, "f%05d.png"),
             "-filter_complex", f"[0:v][1:v]overlay=0:0:shortest=1,scale={final_width}:{fh}:flags=lanczos,format=yuv420p[v]",
             "-map", "[v]", "-map", "0:a", "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-c:a", "aac", "-shortest", out_path])
        return {"duration": total, "segments": len(segs), "words": len(w_out),
                "logos": [w["logo"] for w in w_out if "logo" in w]}
    finally:
        shutil.rmtree(work, ignore_errors=True)
