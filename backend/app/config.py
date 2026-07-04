"""Application configuration. All paths are pathlib-based and Windows-safe."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
RECORDINGS_DIR = DATA_DIR / "recordings"
DOWNLOADS_DIR = DATA_DIR / "downloads"
WORK_DIR = DATA_DIR / "work"
OUTPUT_DIR = DATA_DIR / "output"
ASSETS_DIR = DATA_DIR / "assets"
LOGS_DIR = DATA_DIR / "logs"
DB_PATH = DATA_DIR / "kicklips.db"

for _d in (RECORDINGS_DIR, DOWNLOADS_DIR, WORK_DIR, OUTPUT_DIR, ASSETS_DIR, LOGS_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


class Settings:
    anthropic_api_key: str = _env("ANTHROPIC_API_KEY")
    anthropic_model: str = _env("ANTHROPIC_MODEL", "claude-sonnet-5")
    whisper_model: str = _env("WHISPER_MODEL", "small")
    whisper_device: str = _env("WHISPER_DEVICE", "auto")  # auto -> cuda then cpu
    whisper_compute_type: str = _env("WHISPER_COMPUTE_TYPE", "auto")
    live_poll_interval_sec: int = int(_env("LIVE_POLL_INTERVAL_SEC", "300"))
    disk_min_free_gb: float = float(_env("DISK_MIN_FREE_GB", "5"))
    queue_concurrency: int = int(_env("QUEUE_CONCURRENCY", "1"))
    segment_time_sec: int = int(_env("SEGMENT_TIME_SEC", "600"))
    ffmpeg_path: str = _env("FFMPEG_PATH", "ffmpeg")
    ffprobe_path: str = _env("FFPROBE_PATH", "ffprobe")
    ytdlp_path: str = _env("YTDLP_PATH", "yt-dlp")
    streamlink_path: str = _env("STREAMLINK_PATH", "streamlink")
    ui_language: str = _env("UI_LANGUAGE", "he")

    def which(self, tool: str) -> str | None:
        """Resolve a tool path: explicit override first, then PATH lookup."""
        override = getattr(self, f"{tool.replace('-', '')}_path", None) or tool
        return shutil.which(override) or (override if Path(override).exists() else None)


settings = Settings()
