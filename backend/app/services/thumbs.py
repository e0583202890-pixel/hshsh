"""Thumbnails: frame grabs and auto Shorts thumbnails (face-centered + Hebrew text)."""
from __future__ import annotations

import asyncio
from pathlib import Path

from ..config import settings


async def grab_frame(video: str | Path, t: float, out: Path) -> bool:
    ffmpeg = settings.which("ffmpeg") or "ffmpeg"
    cmd = [ffmpeg, "-y", "-ss", f"{t:.2f}", "-i", str(video),
           "-frames:v", "1", "-q:v", "2", str(out)]
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.DEVNULL,
                                                stderr=asyncio.subprocess.DEVNULL)
    return await proc.wait() == 0 and out.exists()


async def auto_thumbnail(video: str | Path, t: float, out: Path,
                         title_text: str = "", logo_path: str | None = None) -> bool:
    """Grab a strong frame, center the face if found, overlay title + logo."""
    frame = out.with_suffix(".frame.jpg")
    if not await grab_frame(video, t, frame):
        return False

    def _blocking() -> bool:
        try:
            import cv2
            import numpy as np
        except ImportError:
            frame.rename(out)
            return True
        img = cv2.imread(str(frame))
        if img is None:
            return False
        h, w = img.shape[:2]
        # Face-centered crop to 9:16 when a face is detectable.
        cx = w // 2
        try:
            import mediapipe as mp
            det = mp.solutions.face_detection.FaceDetection(min_detection_confidence=0.5)
            res = det.process(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
            det.close()
            if res.detections:
                bb = res.detections[0].location_data.relative_bounding_box
                cx = int((bb.xmin + bb.width / 2) * w)
        except Exception:  # noqa: BLE001 - fall back to center
            pass
        crop_w = int(h * 9 / 16)
        x0 = int(np.clip(cx - crop_w // 2, 0, max(0, w - crop_w)))
        img = img[:, x0:x0 + crop_w]
        img = cv2.resize(img, (1080, 1920))
        if logo_path and Path(logo_path).exists():
            logo = cv2.imread(logo_path, cv2.IMREAD_UNCHANGED)
            if logo is not None:
                lw = 260
                lh = int(logo.shape[0] * lw / logo.shape[1])
                logo = cv2.resize(logo, (lw, lh))
                y0, x1 = 40, 1080 - lw - 40
                roi = img[y0:y0 + lh, x1:x1 + lw]
                if logo.shape[2] == 4:
                    alpha = logo[:, :, 3:] / 255.0
                    roi[:] = (1 - alpha) * roi + alpha * logo[:, :, :3]
                else:
                    roi[:] = logo
        cv2.imwrite(str(out), img, [cv2.IMWRITE_JPEG_QUALITY, 92])
        return True

    ok = await asyncio.to_thread(_blocking)
    frame.unlink(missing_ok=True)
    # Note: big Hebrew title overlay is added in the frontend thumbnail editor
    # (canvas), because correct RTL text shaping is far better in the browser.
    return ok
