"""Shared helpers: ASCII slugify, subprocess runner with progress, disk guard."""
from __future__ import annotations

import asyncio
import re
import shutil
import unicodedata
from pathlib import Path
from typing import AsyncIterator

from ..config import settings

_slug_re = re.compile(r"[^A-Za-z0-9._-]+")


def slugify(text: str, max_len: int = 80) -> str:
    """ASCII-only filename-safe slug (console cannot render Hebrew)."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = _slug_re.sub("_", text).strip("_.")
    return (text or "untitled")[:max_len]


def free_gb(path: Path) -> float:
    usage = shutil.disk_usage(path)
    return usage.free / (1024 ** 3)


def disk_ok(path: Path) -> bool:
    return free_gb(path) >= settings.disk_min_free_gb


async def run_process(cmd: list[str], log_path: Path | None = None) -> tuple[int, str]:
    """Run a subprocess, capture combined output, return (rc, last_meaningful_line)."""
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    lines: list[str] = []
    log_f = open(log_path, "a", encoding="utf-8", errors="replace") if log_path else None
    try:
        assert proc.stdout is not None
        async for raw in proc.stdout:
            line = raw.decode("utf-8", errors="replace").rstrip()
            if line:
                lines.append(line)
                if log_f:
                    log_f.write(line + "\n")
    finally:
        if log_f:
            log_f.close()
    rc = await proc.wait()
    last = ""
    for line in reversed(lines):
        low = line.lower()
        if "error" in low or "warning" in low or not last:
            last = line
            if "error" in low:
                break
    return rc, last


async def stream_process(cmd: list[str], log_path: Path | None = None) -> AsyncIterator[str]:
    """Yield output lines as they arrive (for progress parsing)."""
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    log_f = open(log_path, "a", encoding="utf-8", errors="replace") if log_path else None
    try:
        assert proc.stdout is not None
        async for raw in proc.stdout:
            line = raw.decode("utf-8", errors="replace").rstrip()
            if log_f and line:
                log_f.write(line + "\n")
            yield line
        await proc.wait()
        yield f"__RC__{proc.returncode}"
    finally:
        if log_f:
            log_f.close()
