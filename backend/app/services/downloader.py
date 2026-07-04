"""VOD/clip download via yt-dlp, with the Kick Cloudflare-403 cascade.

Cascade (stop at first success, report each step, never dead-end):
  1) yt-dlp --impersonate chrome            (needs curl_cffi)
  2) + --cookies-from-browser firefox|chrome|edge
  3) + --referer https://kick.com/ + UA
  4) --update-to nightly, retry once
  5) manual m3u8 fallback -> job status needs_input, operator pastes master.m3u8
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse

from ..config import DOWNLOADS_DIR, LOGS_DIR, settings
from ..db import SessionLocal
from ..models import Source
from ..queue import queue
from .probe import probe
from .util import slugify, stream_process

_PROGRESS_RE = re.compile(r"\[download\]\s+(\d+(?:\.\d+)?)%")
_DEST_RE = re.compile(r"Destination:\s+(.+)")
_MERGED_RE = re.compile(r'Merging formats into "(.+)"')

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def detect_platform(url: str) -> str:
    host = urlparse(url).netloc.lower()
    for key in ("kick", "twitch", "youtube", "youtu.be", "tiktok", "instagram", "x.com", "twitter"):
        if key in host:
            return {"youtu.be": "youtube", "x.com": "x", "twitter": "x"}.get(key, key)
    return "other"


def _base_cmd(url: str, quality: str, section: str | None, out_tmpl: str) -> list[str]:
    ytdlp = settings.which("yt-dlp") or "yt-dlp"
    cmd = [ytdlp, "--add-metadata", "--write-thumbnail", "--no-playlist",
           "--newline", "-o", out_tmpl]
    if quality and quality != "best":
        cmd += ["-f", quality]
    if section:
        cmd += ["--download-sections", f"*{section}", "--force-keyframes-at-cuts"]
    cmd.append(url)
    return cmd


def _kick_attempts(base: list[str]) -> list[tuple[str, list[str]]]:
    url = base[-1]
    pre = base[:-1]
    return [
        ("impersonate chrome", pre + ["--impersonate", "chrome", url]),
        ("impersonate + firefox cookies", pre + ["--impersonate", "chrome", "--cookies-from-browser", "firefox", url]),
        ("impersonate + chrome cookies", pre + ["--impersonate", "chrome", "--cookies-from-browser", "chrome", url]),
        ("impersonate + edge cookies", pre + ["--impersonate", "chrome", "--cookies-from-browser", "edge", url]),
        ("referer + user-agent", pre + ["--impersonate", "chrome", "--referer", "https://kick.com/",
                                        "--user-agent", UA, url]),
        ("yt-dlp nightly update + retry", pre + ["--update-to", "nightly", url]),
    ]


async def _run_ytdlp(job_id: int, cmd: list[str], log: Path) -> tuple[bool, str, str]:
    """Returns (ok, dest_path, last_line)."""
    dest = ""
    last = ""
    rc = 1
    async for line in stream_process(cmd, log):
        if line.startswith("__RC__"):
            rc = int(line[6:])
            break
        if not line:
            continue
        last = line
        m = _DEST_RE.search(line)
        if m:
            dest = m.group(1).strip()
        m = _MERGED_RE.search(line)
        if m:
            dest = m.group(1).strip()
        m = _PROGRESS_RE.search(line)
        if m:
            await queue.update(job_id, progress_pct=float(m.group(1)), message="Downloading")
    return rc == 0, dest, last


async def handle_download(job_id: int, params: dict) -> None:
    url: str = params["url"]
    quality: str = params.get("quality", "best")
    section: str | None = params.get("section")
    source_id: int = params["source_id"]
    manual_m3u8: str | None = params.get("m3u8_url")
    platform = detect_platform(url)
    log = LOGS_DIR / f"job_{job_id}.log"

    with SessionLocal() as db:
        src = db.get(Source, source_id)
        if src:
            src.status = "downloading"
            db.commit()

    name = slugify(f"{platform}_{Path(urlparse(url).path).name or 'video'}")
    out_tmpl = str(DOWNLOADS_DIR / f"{name}_%(id)s.%(ext)s")
    base = _base_cmd(url, quality, section, out_tmpl)

    ok, dest, last = False, "", ""
    if manual_m3u8:
        ytdlp = settings.which("yt-dlp") or "yt-dlp"
        cmd = [ytdlp, "--newline", "--referer", "https://kick.com/",
               "-o", out_tmpl, manual_m3u8]
        await queue.update(job_id, message="Manual m3u8 download")
        ok, dest, last = await _run_ytdlp(job_id, cmd, log)
    elif platform == "kick":
        for step_name, cmd in _kick_attempts(base):
            await queue.update(job_id, message=f"Kick cascade: {step_name}")
            ok, dest, last = await _run_ytdlp(job_id, cmd, log)
            if ok:
                break
        if not ok:
            # Never a dead end: ask the operator for the master.m3u8 URL.
            with SessionLocal() as db:
                src = db.get(Source, source_id)
                if src:
                    src.status = "needs_input"
                    src.error = ("Cloudflare blocked all automatic methods. Open the VOD in the "
                                 "browser, press F12 -> Network, filter 'm3u8', copy the "
                                 "master.m3u8 URL and paste it on the source card.")
                    db.commit()
            await queue.update(job_id, status="needs_input",
                               message="Action needed: paste master.m3u8 URL", error=last)
            return
    else:
        ok, dest, last = await _run_ytdlp(job_id, base, log)

    with SessionLocal() as db:
        src = db.get(Source, source_id)
        if not src:
            return
        if ok and dest and Path(dest).exists():
            src.file_path = dest
            src.status = "done"
            src.error = None
            thumb = Path(dest).with_suffix(".webp")
            if not thumb.exists():
                thumb = Path(dest).with_suffix(".jpg")
            if thumb.exists():
                src.thumb_path = str(thumb)
            db.commit()
        else:
            src.status = "failed"
            src.error = last or "Download failed"
            db.commit()
            raise RuntimeError(last or "Download failed")

    info = await probe(dest)
    with SessionLocal() as db:
        src = db.get(Source, source_id)
        if src:
            src.duration_sec = info.get("duration_sec")
            src.width = info.get("width")
            src.height = info.get("height")
            src.fps = info.get("fps")
            db.commit()
    await queue.update(job_id, status="done", progress_pct=100, message="Done")


def register() -> None:
    from ..queue import register_handler
    register_handler("download", handle_download)


def sanitize_meta(raw: str) -> str:
    """Strip non-JSON noise from metadata blobs before parsing."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?|```$", "", raw, flags=re.M)
    return raw


def parse_info_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
