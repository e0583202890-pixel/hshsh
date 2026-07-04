"""Per-streamer layout + context profiles, and MediaPipe facecam-box suggestion."""
from __future__ import annotations

import asyncio
import json
import logging

from ..db import SessionLocal
from ..models import Streamer

log = logging.getLogger("profiles")


def get_layout(streamer_id: int | None) -> dict | None:
    if not streamer_id:
        return None
    with SessionLocal() as db:
        s = db.get(Streamer, streamer_id)
        if not s or not s.facecam_rect_json:
            return None
        return {"facecam_rect": json.loads(s.facecam_rect_json),
                "gameplay_rect": json.loads(s.gameplay_rect_json) if s.gameplay_rect_json else None,
                "split_ratio": s.split_ratio}


def save_layout(streamer_id: int, facecam_rect: dict | None,
                gameplay_rect: dict | None, split_ratio: float | None) -> None:
    with SessionLocal() as db:
        s = db.get(Streamer, streamer_id)
        if not s:
            raise ValueError("Streamer not found")
        if facecam_rect is not None:
            s.facecam_rect_json = json.dumps(facecam_rect)
        if gameplay_rect is not None:
            s.gameplay_rect_json = json.dumps(gameplay_rect)
        if split_ratio is not None:
            s.split_ratio = split_ratio
        db.commit()


async def suggest_facecam_rect(video_path: str, sample_frames: int = 12) -> dict | None:
    """MediaPipe face detection over sampled frames -> suggested facecam box."""
    def _blocking() -> dict | None:
        try:
            import cv2
            import mediapipe as mp
        except ImportError:
            return None
        cap = cv2.VideoCapture(video_path)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if total <= 0:
            cap.release()
            return None
        detector = mp.solutions.face_detection.FaceDetection(min_detection_confidence=0.5)
        boxes = []
        for i in range(sample_frames):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(total * (i + 0.5) / sample_frames))
            ok, frame = cap.read()
            if not ok:
                continue
            h, w = frame.shape[:2]
            res = detector.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            if res.detections:
                bb = res.detections[0].location_data.relative_bounding_box
                boxes.append((bb.xmin * w, bb.ymin * h, bb.width * w, bb.height * h))
        cap.release()
        detector.close()
        if not boxes:
            return None
        import numpy as np
        arr = np.array(boxes)
        x, y, bw, bh = arr.mean(axis=0)
        # Expand the face box to an approximate facecam-overlay box.
        pad_x, pad_y = bw * 0.8, bh * 1.0
        return {"x": max(0, int(x - pad_x)), "y": max(0, int(y - pad_y)),
                "w": int(bw + 2 * pad_x), "h": int(bh + 2 * pad_y)}
    return await asyncio.to_thread(_blocking)
