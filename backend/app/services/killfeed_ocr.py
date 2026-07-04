"""EXPERIMENTAL kill-feed OCR (off by default).

Crops the HUD/kill-feed region and OCRs for the streamer's name / kill
keywords to flag FPS multi-kills/clutches. FPS-only, may miss or mis-fire,
needs per-game tuning. Never blocks anything else.
"""
from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger("killfeed_ocr")

KILL_KEYWORDS = ["kill", "elimin", "knocked", "headshot", "ace", "clutch"]


async def detect_kill_events(video_path: str, region: dict, streamer_name: str,
                             sample_every_sec: float = 2.0) -> list[dict]:
    def _blocking() -> list[dict]:
        try:
            import cv2
            import pytesseract
        except ImportError:
            logger.warning("pytesseract/opencv missing - kill-feed OCR unavailable")
            return []
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        step = max(1, int(fps * sample_every_sec))
        x, y, w, h = (region[k] for k in ("x", "y", "w", "h"))
        name = streamer_name.lower()
        events: list[dict] = []
        idx = 0
        while True:
            ok = cap.grab()
            if not ok:
                break
            if idx % step == 0:
                ok, frame = cap.retrieve()
                if ok:
                    crop = frame[y:y + h, x:x + w]
                    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                    gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
                    text = pytesseract.image_to_string(gray).lower()
                    if name in text or any(k in text for k in KILL_KEYWORDS):
                        t = idx / fps
                        if not events or t - events[-1]["t"] > 4:
                            events.append({"t": t, "text": text.strip()[:120]})
            idx += 1
        cap.release()
        return events
    return await asyncio.to_thread(_blocking)
