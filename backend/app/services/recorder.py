"""Live recording engine.

Each recording is a long-lived asyncio task (not a queue job) so several
streams can record at once. Streamlink writes N-minute .ts segments
(crash-safe); on stop we remux/concat to one MP4, create a Source row,
and optionally enqueue AI Auto-Clip.
"""
from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path

from ..config import LOGS_DIR, RECORDINGS_DIR, settings
from ..db import SessionLocal
from ..models import Clip, Recording, Source, Streamer
from ..queue import queue
from ..ws import hub
from .chat_capture import ChatCapture
from .probe import probe
from .util import disk_ok, free_gb, slugify

MAX_RECONNECTS = 5
RECONNECT_BACKOFF_SEC = [5, 10, 20, 40, 60]


class RecordingTask:
    def __init__(self, recording_id: int, channel: str, streamer_id: int | None,
                 auto_clip_on_end: bool) -> None:
        self.recording_id = recording_id
        self.channel = channel
        self.streamer_id = streamer_id
        self.auto_clip_on_end = auto_clip_on_end
        self.stop_requested = False
        self.proc: asyncio.subprocess.Process | None = None
        self.segments: list[Path] = []
        self.reconnects = 0
        self.started_mono = time.monotonic()
        self.chat = ChatCapture(channel)
        self._task: asyncio.Task | None = None

    # ---- lifecycle ----
    def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self.stop_requested = True
        if self.proc and self.proc.returncode is None:
            self.proc.terminate()

    def elapsed_sec(self) -> float:
        return time.monotonic() - self.started_mono

    def total_bytes(self) -> int:
        return sum(p.stat().st_size for p in self.segments if p.exists())

    async def _status(self, status: str, message: str = "") -> None:
        await hub.broadcast({"kind": "recording", "recording_id": self.recording_id,
                             "channel": self.channel, "status": status, "message": message,
                             "elapsed_sec": round(self.elapsed_sec()),
                             "reconnect_count": self.reconnects,
                             "size_bytes": self.total_bytes()})

    async def _run(self) -> None:
        log = LOGS_DIR / f"recording_{self.recording_id}.log"
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = slugify(f"{self.channel}_{stamp}")
        chat_path = RECORDINGS_DIR / f"{base}_chat.jsonl"
        self.chat.start(chat_path)
        try:
            attempt = 0
            while not self.stop_requested:
                if not disk_ok(RECORDINGS_DIR):
                    await self._fail(f"Stopped: free disk below {settings.disk_min_free_gb} GB "
                                     f"(free: {free_gb(RECORDINGS_DIR):.1f} GB)")
                    break
                seg = RECORDINGS_DIR / f"{base}_part{len(self.segments):03d}.ts"
                self.segments.append(seg)
                await self._update_db(segment_count=len(self.segments))
                await self._status("recording", f"Recording segment {len(self.segments)}")
                outcome = await self._record_segment(seg, log)
                if self.stop_requested:
                    break
                if outcome == "rotated":
                    # Normal N-minute rotation: continue immediately, reset the
                    # reconnect counter (the stream is healthy).
                    attempt = 0
                    continue
                # streamlink exited on its own: the stream likely dropped. Reconnect
                # if the channel is still live, otherwise treat it as a normal end.
                from .live_monitor import is_channel_live
                if not await is_channel_live(self.channel):
                    break  # channel went offline: normal end
                attempt += 1
                self.reconnects += 1
                if attempt > MAX_RECONNECTS:
                    await self._status("failed", "Too many reconnect attempts")
                    break
                backoff = RECONNECT_BACKOFF_SEC[min(attempt - 1, len(RECONNECT_BACKOFF_SEC) - 1)]
                await self._status("recording", f"Stream dropped, reconnecting in {backoff}s "
                                                f"(attempt {attempt}/{MAX_RECONNECTS})")
                await asyncio.sleep(backoff)
        finally:
            await self.chat.stop()
            await self._finish(chat_path)

    async def _record_segment(self, seg: Path, log: Path) -> str:
        """Record one segment. Returns 'rotated' (hit segment_time, healthy) or
        'exited' (streamlink ended on its own -> possible drop)."""
        streamlink = settings.which("streamlink") or "streamlink"
        cmd = [streamlink, f"kick.com/{self.channel}", "best",
               "--stream-segment-timeout", "30", "--retry-streams", "5",
               "-o", str(seg)]
        with open(log, "a", encoding="utf-8") as f:
            self.proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=f, stderr=asyncio.subprocess.STDOUT)
        # Rotate into a new segment every segment_time_sec by restarting streamlink.
        try:
            await asyncio.wait_for(self.proc.wait(), timeout=settings.segment_time_sec)
        except asyncio.TimeoutError:
            self.proc.terminate()
            await self.proc.wait()
            return "rotated"
        return "exited"

    async def _update_db(self, **fields) -> None:
        with SessionLocal() as db:
            rec = db.get(Recording, self.recording_id)
            if rec:
                for k, v in fields.items():
                    setattr(rec, k, v)
                rec.reconnect_count = self.reconnects
                rec.segments_json = json.dumps([str(p) for p in self.segments])
                db.commit()

    async def _fail(self, message: str) -> None:
        await self._update_db(status="failed", error=message, ended_at=datetime.utcnow())
        await self._status("failed", message)

    async def _finish(self, chat_path: Path) -> None:
        manager.pop(self.recording_id)
        existing = [p for p in self.segments if p.exists() and p.stat().st_size > 0]
        if not existing:
            await self._fail("No video data was captured")
            return
        await self._update_db(status="remuxing")
        await self._status("remuxing", "Remuxing segments to MP4")
        final = existing[0].with_suffix("").with_name(existing[0].stem.rsplit("_part", 1)[0] + ".mp4")
        ok = await self._remux(existing, final)
        info = await probe(final) if ok else {}
        had_chat = chat_path.exists() and chat_path.stat().st_size > 0
        with SessionLocal() as db:
            rec = db.get(Recording, self.recording_id)
            if rec:
                rec.status = "done" if ok else "failed"
                rec.ended_at = datetime.utcnow()
                rec.file_path = str(final) if ok else None
                rec.duration_sec = info.get("duration_sec")
                rec.had_chat = had_chat
                rec.chat_log_path = str(chat_path) if had_chat else None
                if not ok:
                    rec.error = "Remux failed - raw .ts segments kept"
                db.commit()
            source_id = None
            if ok:
                src = Source(origin="live_recording", platform="kick",
                             url=f"https://kick.com/{self.channel}",
                             title=f"{self.channel} live {datetime.now():%Y-%m-%d %H:%M}",
                             streamer_id=self.streamer_id, file_path=str(final),
                             chat_log_path=str(chat_path) if had_chat else None,
                             duration_sec=info.get("duration_sec"), width=info.get("width"),
                             height=info.get("height"), fps=info.get("fps"), status="done")
                db.add(src)
                db.commit()
                source_id = src.id
                # Turn "clip last N seconds" live marks into draft clips on the source.
                marks = json.loads(rec.clip_marks_json or "[]") if rec else []
                for mark in marks:
                    start = max(0.0, float(mark.get("t", 0)))
                    end = min(info.get("duration_sec") or start + mark.get("seconds", 60),
                              start + mark.get("seconds", 60))
                    if end > start:
                        db.add(Clip(source_id=source_id, title="", start_sec=start,
                                    end_sec=end, duration_sec=end - start,
                                    vertical_mode="facecam_stack", status="draft"))
                db.commit()
        await self._status("done" if ok else "failed", "Recording finished")
        if ok and source_id and self.auto_clip_on_end:
            await queue.enqueue("autoclip", {"source_id": source_id, "n": 10}, source_id=source_id)

    async def _remux(self, segments: list[Path], out: Path) -> bool:
        ffmpeg = settings.which("ffmpeg") or "ffmpeg"
        list_file = out.with_suffix(".txt")
        list_file.write_text(
            "".join(f"file '{p.as_posix()}'\n" for p in segments), encoding="utf-8")
        cmd = [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
               "-c", "copy", str(out)]
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.DEVNULL,
                                                    stderr=asyncio.subprocess.DEVNULL)
        rc = await proc.wait()
        list_file.unlink(missing_ok=True)
        return rc == 0 and out.exists()


class RecordingManager:
    def __init__(self) -> None:
        self.active: dict[int, RecordingTask] = {}

    def is_recording_channel(self, channel: str) -> bool:
        return any(t.channel.lower() == channel.lower() for t in self.active.values())

    async def start(self, channel: str, streamer_id: int | None = None,
                    auto_clip_on_end: bool = False) -> int:
        if self.is_recording_channel(channel):
            raise ValueError(f"Already recording channel '{channel}'")
        if not disk_ok(RECORDINGS_DIR):
            raise ValueError(f"Not enough free disk space "
                             f"(minimum {settings.disk_min_free_gb} GB required)")
        with SessionLocal() as db:
            rec = Recording(streamer_id=streamer_id, status="recording")
            db.add(rec)
            db.commit()
            rec_id = rec.id
        task = RecordingTask(rec_id, channel, streamer_id, auto_clip_on_end)
        self.active[rec_id] = task
        task.start()
        await hub.broadcast({"kind": "recording", "recording_id": rec_id,
                             "channel": channel, "status": "recording", "message": "Started"})
        return rec_id

    async def stop(self, recording_id: int) -> None:
        task = self.active.get(recording_id)
        if task:
            await task.stop()

    def pop(self, recording_id: int) -> None:
        self.active.pop(recording_id, None)

    def mark_clip_last(self, recording_id: int, seconds: int) -> dict:
        """Mark 'clip the last N seconds' while a recording is running."""
        task = self.active.get(recording_id)
        if not task:
            raise ValueError("Recording is not active")
        t_end = task.elapsed_sec()
        mark = {"t": max(0.0, t_end - seconds), "seconds": seconds, "marked_at": t_end}
        with SessionLocal() as db:
            rec = db.get(Recording, recording_id)
            marks = json.loads(rec.clip_marks_json or "[]") if rec else []
            marks.append(mark)
            if rec:
                rec.clip_marks_json = json.dumps(marks)
                db.commit()
        return mark

    async def recover_on_startup(self) -> None:
        """Recordings interrupted by an app restart: mark ended, remux what exists."""
        with SessionLocal() as db:
            stale = db.query(Recording).filter(Recording.status.in_(["recording", "remuxing"])).all()
            for rec in stale:
                rec.status = "failed"
                rec.ended_at = rec.ended_at or datetime.utcnow()
                rec.error = "Interrupted by app restart - segments kept on disk"
            db.commit()


manager = RecordingManager()


async def get_streamer_for_start(streamer_id: int | None, url: str | None) -> tuple[str, int | None, bool]:
    """Resolve (channel_handle, streamer_id, auto_clip_on_end) for a start request."""
    if streamer_id:
        with SessionLocal() as db:
            s = db.get(Streamer, streamer_id)
            if not s:
                raise ValueError("Streamer not found")
            return s.handle, s.id, s.auto_clip_on_end
    if url:
        handle = url.rstrip("/").split("/")[-1]
        return handle, None, False
    raise ValueError("Provide streamer_id or url")
