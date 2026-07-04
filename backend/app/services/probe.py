"""ffprobe wrapper: duration, resolution, fps."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from ..config import settings


async def probe(path: str | Path) -> dict:
    cmd = [settings.which("ffprobe") or "ffprobe", "-v", "quiet", "-print_format", "json",
           "-show_format", "-show_streams", str(path)]
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE,
                                                stderr=asyncio.subprocess.DEVNULL)
    out, _ = await proc.communicate()
    if proc.returncode != 0:
        return {}
    data = json.loads(out or b"{}")
    info: dict = {"duration_sec": None, "width": None, "height": None, "fps": None, "has_audio": False}
    fmt = data.get("format", {})
    if fmt.get("duration"):
        info["duration_sec"] = float(fmt["duration"])
    for s in data.get("streams", []):
        if s.get("codec_type") == "video" and info["width"] is None:
            info["width"] = s.get("width")
            info["height"] = s.get("height")
            rate = s.get("avg_frame_rate") or "0/1"
            try:
                num, den = rate.split("/")
                info["fps"] = round(float(num) / float(den), 2) if float(den) else None
            except (ValueError, ZeroDivisionError):
                pass
        if s.get("codec_type") == "audio":
            info["has_audio"] = True
    return info
