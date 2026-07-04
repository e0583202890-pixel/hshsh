"""Non-text highlight signals: audio-hype, chat-spike, scene-change,
face-reaction. Fused with the LLM ranking in ai_clipper.py."""
from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path

import numpy as np

from ..config import WORK_DIR, settings
from ..db import SessionLocal
from ..models import Source

log = logging.getLogger("signals")

_SCENE_RE = re.compile(r"pts_time:(\d+(?:\.\d+)?)")


async def audio_hype(path: str) -> list[dict]:
    """1s-window RMS z-score peaks -> hype windows."""
    ffmpeg = settings.which("ffmpeg") or "ffmpeg"
    cmd = [ffmpeg, "-v", "quiet", "-i", path, "-vn", "-ac", "1", "-ar", "8000",
           "-f", "s16le", "-"]
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE,
                                                stderr=asyncio.subprocess.DEVNULL)
    pcm, _ = await proc.communicate()
    if not pcm:
        return []
    samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
    sr = 8000
    n_windows = len(samples) // sr
    if n_windows < 10:
        return []
    rms = np.array([np.sqrt(np.mean(samples[i * sr:(i + 1) * sr] ** 2))
                    for i in range(n_windows)])
    mean, std = rms.mean(), rms.std() or 1.0
    z = (rms - mean) / std
    peaks = []
    for i, zv in enumerate(z):
        if zv > 2.0:
            peaks.append({"t": float(i), "score": round(float(zv), 2)})
    return _merge_windows(peaks, gap=5)


def chat_spikes(chat_log_path: str | None, window: int = 10) -> list[dict]:
    """Messages-per-window z-score spikes from the captured chat log."""
    if not chat_log_path or not Path(chat_log_path).exists():
        return []
    counts: dict[int, int] = {}
    try:
        with open(chat_log_path, encoding="utf-8") as f:
            for line in f:
                try:
                    t = float(json.loads(line).get("t_offset_sec", 0))
                    counts[int(t // window)] = counts.get(int(t // window), 0) + 1
                except (json.JSONDecodeError, ValueError):
                    continue
    except OSError:
        return []
    if len(counts) < 5:
        return []
    vals = np.array(list(counts.values()), dtype=np.float32)
    mean, std = vals.mean(), vals.std() or 1.0
    spikes = [{"t": float(k * window), "score": round(float((v - mean) / std), 2)}
              for k, v in counts.items() if (v - mean) / std > 2.0]
    return sorted(spikes, key=lambda s: s["t"])


async def scene_changes(path: str) -> list[dict]:
    ffmpeg = settings.which("ffmpeg") or "ffmpeg"
    cmd = [ffmpeg, "-i", path, "-filter:v", "select='gt(scene,0.4)',showinfo",
           "-f", "null", "-"]
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.DEVNULL,
                                                stderr=asyncio.subprocess.PIPE)
    _, err = await proc.communicate()
    times = _SCENE_RE.findall(err.decode("utf-8", errors="replace"))
    return [{"t": float(t)} for t in times]


async def face_reactions(path: str, facecam_rect: dict | None,
                         sample_every_sec: float = 2.0) -> list[dict]:
    """MediaPipe landmark deltas in the facecam region -> big-reaction candidates."""
    def _blocking() -> list[dict]:
        try:
            import cv2
            import mediapipe as mp
        except ImportError:
            log.warning("opencv/mediapipe missing - face-reaction signal disabled")
            return []
        cap = cv2.VideoCapture(path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        step = max(1, int(fps * sample_every_sec))
        detector = mp.solutions.face_mesh.FaceMesh(static_image_mode=True, max_num_faces=1)
        prev = None
        reactions = []
        frame_idx = 0
        while True:
            ok = cap.grab()
            if not ok:
                break
            if frame_idx % step == 0:
                ok, frame = cap.retrieve()
                if ok:
                    if facecam_rect:
                        x, y, w, h = (facecam_rect[k] for k in ("x", "y", "w", "h"))
                        frame = frame[y:y + h, x:x + w]
                    res = detector.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                    if res.multi_face_landmarks:
                        lm = res.multi_face_landmarks[0].landmark
                        vec = np.array([(p.x, p.y) for p in lm], dtype=np.float32)
                        if prev is not None and len(prev) == len(vec):
                            delta = float(np.abs(vec - prev).mean())
                            if delta > 0.015:
                                reactions.append({"t": frame_idx / fps,
                                                  "score": round(delta * 100, 2)})
                        prev = vec
            frame_idx += 1
        cap.release()
        detector.close()
        return _merge_windows(reactions, gap=6)
    return await asyncio.to_thread(_blocking)


def _merge_windows(points: list[dict], gap: float) -> list[dict]:
    if not points:
        return []
    points = sorted(points, key=lambda p: p["t"])
    merged = [dict(points[0])]
    for p in points[1:]:
        if p["t"] - merged[-1]["t"] <= gap:
            merged[-1]["score"] = max(merged[-1].get("score", 0), p.get("score", 0))
        else:
            merged.append(dict(p))
    return merged


async def analyze_source(source_id: int, force: bool = False) -> dict:
    with SessionLocal() as db:
        src = db.get(Source, source_id)
        if not src or not src.file_path:
            raise ValueError("Source has no file")
        if src.signals_json and not force:
            return json.loads(src.signals_json)
        path = src.file_path
        chat_path = src.chat_log_path
        facecam = None
        if src.streamer_id:
            from ..models import Streamer
            s = db.get(Streamer, src.streamer_id)
            if s and s.facecam_rect_json:
                facecam = json.loads(s.facecam_rect_json)
    hype, scenes, faces = await asyncio.gather(
        audio_hype(path), scene_changes(path), face_reactions(path, facecam))
    result = {"audio_hype_windows": hype,
              "chat_spike_windows": chat_spikes(chat_path),
              "scene_changes": scenes,
              "face_reactions": faces}
    with SessionLocal() as db:
        src = db.get(Source, source_id)
        if src:
            src.signals_json = json.dumps(result)
            db.commit()
    return result


def signals_near(signals: dict, start: float, end: float, margin: float = 5.0) -> list[str]:
    """Which signal types fired inside [start-margin, end+margin]."""
    fired = []
    names = {"audio_hype_windows": "audio_hype", "chat_spike_windows": "chat_spike",
             "scene_changes": "scene_change", "face_reactions": "face_reaction"}
    for key, label in names.items():
        for p in signals.get(key, []):
            if start - margin <= p["t"] <= end + margin:
                fired.append(label)
                break
    return fired
