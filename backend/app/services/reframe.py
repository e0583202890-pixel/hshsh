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


def build_sendcmd(samples: list[tuple[float, float]], src_w: int, src_h: int,
                  out_path: Path) -> tuple[str, str] | None:
    """Write a sendcmd file driving the crop x over time.

    Returns (filter_str, sendcmd_path) or None if no samples (caller falls
    back to static center crop).
    """
    if not samples:
        return None
    crop_w = int(src_h * 9 / 16)
    max_x = max(0, src_w - crop_w)
    lines = []
    for t, cx in samples:
        x = int(np.clip(cx * src_w - crop_w / 2, 0, max_x))
        lines.append(f"{t:.2f} crop x {x};")
    out_path.write_text("\n".join(lines), encoding="utf-8")
    filt = (f"sendcmd=f='{out_path.as_posix()}',"
            f"crop=w={crop_w}:h={src_h}:x={max_x // 2}:y=0,"
            f"scale=1080:1920,format=yuv420p")
    return filt, str(out_path)


async def auto_reframe_filter(video_path: str, src_w: int, src_h: int,
                              work_dir: Path) -> str:
    samples = smooth(await face_track(video_path))
    result = build_sendcmd(samples, src_w, src_h, work_dir / "reframe_cmd.txt")
    if result:
        return result[0]
    logger.info("no face found - falling back to static center crop")
    return "crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=1080:1920,format=yuv420p"
