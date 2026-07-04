"""Audio pipeline: two-pass loudnorm, music + sidechain ducking,
silence detection for SmartCuts."""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

from ..config import settings

_SILENCE_START_RE = re.compile(r"silence_start:\s*(\d+(?:\.\d+)?)")
_SILENCE_END_RE = re.compile(r"silence_end:\s*(\d+(?:\.\d+)?)")


async def loudnorm_measure(path: str | Path, target: float = -14.0) -> dict | None:
    """Pass 1: measure. Returns the measured values for pass 2."""
    ffmpeg = settings.which("ffmpeg") or "ffmpeg"
    cmd = [ffmpeg, "-i", str(path), "-af",
           f"loudnorm=I={target}:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"]
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.DEVNULL,
                                                stderr=asyncio.subprocess.PIPE)
    _, err = await proc.communicate()
    text = err.decode("utf-8", errors="replace")
    start = text.rfind("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None


def loudnorm_filter(measured: dict | None, target: float = -14.0) -> str:
    """Pass 2 filter (or single-pass fallback if measurement failed)."""
    base = f"loudnorm=I={target}:TP=-1.5:LRA=11"
    if not measured:
        return base
    return (f"{base}:measured_I={measured.get('input_i')}"
            f":measured_TP={measured.get('input_tp')}"
            f":measured_LRA={measured.get('input_lra')}"
            f":measured_thresh={measured.get('input_thresh')}"
            f":offset={measured.get('target_offset')}:linear=true")


def music_ducking_graph(music_volume: float = 0.3) -> str:
    """[0:a] speech + [1:a] music -> ducked mix labelled [aout]."""
    return (f"[1:a]volume={music_volume}[m];"
            f"[0:a][m]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=300[aout]")


async def detect_silence(path: str | Path, noise_db: float = -30,
                         min_dur: float = 0.6) -> list[tuple[float, float]]:
    ffmpeg = settings.which("ffmpeg") or "ffmpeg"
    cmd = [ffmpeg, "-i", str(path), "-af",
           f"silencedetect=noise={noise_db}dB:d={min_dur}", "-f", "null", "-"]
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.DEVNULL,
                                                stderr=asyncio.subprocess.PIPE)
    _, err = await proc.communicate()
    text = err.decode("utf-8", errors="replace")
    starts = [float(m) for m in _SILENCE_START_RE.findall(text)]
    ends = [float(m) for m in _SILENCE_END_RE.findall(text)]
    return list(zip(starts, ends))


def keep_spans_from_silence(silences: list[tuple[float, float]],
                            duration: float, pad: float = 0.15) -> list[tuple[float, float]]:
    """Invert silence spans into keep spans (SmartCuts)."""
    keep = []
    cursor = 0.0
    for s, e in silences:
        if s - pad > cursor:
            keep.append((cursor, s + pad))
        cursor = max(cursor, e - pad)
    if cursor < duration:
        keep.append((cursor, duration))
    return keep


def bleep_filter(spans: list[tuple[float, float]]) -> str:
    """Mute profanity spans (auto-bleep)."""
    if not spans:
        return "anull"
    conds = "+".join(f"between(t,{s:.2f},{e:.2f})" for s, e in spans)
    return f"volume=enable='{conds}':volume=0"
