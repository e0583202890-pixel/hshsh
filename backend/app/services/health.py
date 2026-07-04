"""Startup health checks: external tools, python deps, CUDA, API key."""
from __future__ import annotations

import asyncio
import importlib.util
import shutil

from ..config import settings


def _has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


async def _tool_version(cmd: list[str]) -> bool:
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        return (await proc.wait()) == 0
    except (OSError, FileNotFoundError):
        return False


async def health_report() -> dict:
    checks: dict[str, dict] = {}

    for tool, hint in (("ffmpeg", "Install ffmpeg and add it to PATH"),
                       ("ffprobe", "ffprobe ships with ffmpeg"),
                       ("yt-dlp", "pip install yt-dlp"),
                       ("streamlink", "pip install streamlink")):
        path = settings.which(tool) or shutil.which(tool)
        ok = bool(path) and await _tool_version([path, "--version"])
        checks[tool] = {"ok": ok, "path": path or "", "hint": "" if ok else hint}

    for mod, key, hint in (("curl_cffi", "curl_cffi", "pip install curl_cffi (Kick impersonation)"),
                           ("cloudscraper", "cloudscraper", "pip install cloudscraper (Kick live)"),
                           ("faster_whisper", "whisper", "pip install faster-whisper"),
                           ("mediapipe", "mediapipe", "pip install mediapipe"),
                           ("anthropic", "anthropic_sdk", "pip install anthropic")):
        ok = _has_module(mod)
        checks[key] = {"ok": ok, "hint": "" if ok else hint}

    cuda_ok = False
    try:
        import ctypes
        for lib in ("cudart64_12.dll", "cudart64_110.dll", "libcudart.so"):
            try:
                ctypes.CDLL(lib)
                cuda_ok = True
                break
            except OSError:
                continue
    except Exception:  # noqa: BLE001
        pass
    checks["cuda"] = {"ok": cuda_ok,
                      "hint": "" if cuda_ok else "Optional: NVIDIA CUDA for fast Whisper"}

    key_ok = bool(settings.anthropic_api_key)
    checks["anthropic_key"] = {"ok": key_ok,
                               "hint": "" if key_ok else "Set ANTHROPIC_API_KEY in .env"}
    return {"checks": checks, "all_ok": all(c["ok"] for k, c in checks.items()
                                            if k not in ("cuda",))}
