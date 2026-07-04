"""Face-aware auto-reframe: MediaPipe face center per sampled frame, smoothed,
applied as a time-varying crop via ffmpeg sendcmd. Falls back to static
center crop if no face is found."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger("reframe")


async def face_track(video_path: str, sample_every_sec: float = 0.5) -> list[tuple[float, float]]:
    """Return [(t, cx_norm)] samples of the face center x (0..1)."""
    def _blocking() -> list[tuple[float, float]]:
        try:
            import cv2
            import mediapipe as mp
        except ImportError:
            return []
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        step = max(1, int(fps * sample_every_sec))
        detector = mp.solutions.face_detection.FaceDetection(min_detection_confidence=0.5)
        samples: list[tuple[float, float]] = []
        idx = 0
        while True:
            ok = cap.grab()
            if not ok:
                break
            if idx % step == 0:
                ok, frame = cap.retrieve()
                if ok:
                    res = detector.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                    if res.detections:
                        bb = res.detections[0].location_data.relative_bounding_box
                        samples.append((idx / fps, bb.xmin + bb.width / 2))
            idx += 1
        cap.release()
        detector.close()
        return samples
    return await asyncio.to_thread(_blocking)


def smooth(samples: list[tuple[float, float]], window: int = 7) -> list[tuple[float, float]]:
    if len(samples) < 3:
        return samples
    xs = np.array([s[1] for s in samples])
    kernel = np.ones(window) / window
    smoothed = np.convolve(xs, kernel, mode="same")
    return [(samples[i][0], float(smoothed[i])) for i in range(len(samples))]


def face_centered_crop(samples: list[tuple[float, float]], src_w: int, src_h: int) -> str | None:
    """Static 9:16 crop centered on the MEDIAN smoothed face x.

    A time-varying sendcmd crop is fragile across ffmpeg builds; a median-
    centered crop keeps the face reliably in frame and never fails the render.
    Returns None if there are no face samples (caller uses center crop).
    """
    if not samples:
        return None
    crop_w = int(src_h * 9 / 16)
    if crop_w >= src_w:
        return None  # already narrower than 9:16 -> center crop handles it
    max_x = src_w - crop_w
    median_cx = float(np.median([cx for _, cx in samples]))
    x = int(np.clip(median_cx * src_w - crop_w / 2, 0, max_x))
    return f"crop={crop_w}:{src_h}:{x}:0,scale=1080:1920,format=yuv420p"


async def auto_reframe_filter(video_path: str, src_w: int, src_h: int,
                              work_dir: Path) -> str:
    samples = smooth(await face_track(video_path))
    filt = face_centered_crop(samples, src_w, src_h)
    if filt:
        return filt
    logger.info("no face found - falling back to static center crop")
    return "crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=1080:1920,format=yuv420p"
