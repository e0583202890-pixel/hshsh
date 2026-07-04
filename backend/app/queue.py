"""In-process async job queue backed by the persistent jobs table.

Live recordings do NOT run here — they are long-lived tasks (see recorder.py)
so multiple recordings can run concurrently, independent of render concurrency.
"""
from __future__ import annotations

import asyncio
import json
import traceback
from datetime import datetime
from typing import Any, Awaitable, Callable

from .config import LOGS_DIR, settings
from .db import SessionLocal
from .models import Job
from .ws import hub

JobHandler = Callable[[int, dict[str, Any]], Awaitable[None]]

_handlers: dict[str, JobHandler] = {}


def register_handler(job_type: str, handler: JobHandler) -> None:
    _handlers[job_type] = handler


class JobQueue:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[int] = asyncio.Queue()
        self._workers: list[asyncio.Task] = []
        self._cancelled: set[int] = set()

    async def start(self) -> None:
        # Jobs interrupted by an app restart -> failed + retryable.
        with SessionLocal() as db:
            for job in db.query(Job).filter(Job.status.in_(["running", "queued"])).all():
                job.status = "failed"
                job.error = "Interrupted by app restart. Retry to run again."
            db.commit()
        n = max(1, min(3, settings.queue_concurrency))
        self._workers = [asyncio.create_task(self._worker(i)) for i in range(n)]

    async def stop(self) -> None:
        for w in self._workers:
            w.cancel()

    async def enqueue(self, job_type: str, params: dict[str, Any] | None = None,
                      source_id: int | None = None, clip_id: int | None = None) -> int:
        with SessionLocal() as db:
            job = Job(type=job_type, params_json=json.dumps(params or {}),
                      source_id=source_id, clip_id=clip_id)
            db.add(job)
            db.commit()
            job_id = job.id
            job.log_path = str(LOGS_DIR / f"job_{job_id}.log")
            db.commit()
        await self._queue.put(job_id)
        await self.update(job_id, status="queued", progress_pct=0, message="Queued")
        return job_id

    async def retry(self, job_id: int) -> None:
        with SessionLocal() as db:
            job = db.get(Job, job_id)
            if not job:
                return
            job.status = "queued"
            job.error = None
            job.progress_pct = 0
            db.commit()
        self._cancelled.discard(job_id)
        await self._queue.put(job_id)

    def cancel(self, job_id: int) -> None:
        self._cancelled.add(job_id)

    async def update(self, job_id: int, *, status: str | None = None,
                     progress_pct: float | None = None, message: str | None = None,
                     error: str | None = None) -> None:
        with SessionLocal() as db:
            job = db.get(Job, job_id)
            if not job:
                return
            if status is not None:
                job.status = status
                if status == "running" and not job.started_at:
                    job.started_at = datetime.utcnow()
                if status in ("done", "failed", "cancelled"):
                    job.finished_at = datetime.utcnow()
            if progress_pct is not None:
                job.progress_pct = float(progress_pct)
            if message is not None:
                job.message = message
            if error is not None:
                job.error = error
            db.commit()
            payload = {"kind": "job", "job_id": job.id, "type": job.type,
                       "status": job.status, "progress_pct": job.progress_pct,
                       "message": job.message, "error": job.error,
                       "source_id": job.source_id, "clip_id": job.clip_id}
        await hub.broadcast(payload)

    async def _worker(self, idx: int) -> None:
        while True:
            job_id = await self._queue.get()
            if job_id in self._cancelled:
                await self.update(job_id, status="cancelled", message="Cancelled")
                continue
            with SessionLocal() as db:
                job = db.get(Job, job_id)
                if not job:
                    continue
                job_type = job.type
                params = json.loads(job.params_json or "{}")
                log_path = job.log_path
            handler = _handlers.get(job_type)
            if handler is None:
                await self.update(job_id, status="failed", error=f"No handler for job type '{job_type}'")
                continue
            await self.update(job_id, status="running", message="Running")
            try:
                await handler(job_id, params)
                with SessionLocal() as db:
                    job = db.get(Job, job_id)
                    still = job.status if job else "done"
                if still == "running":
                    await self.update(job_id, status="done", progress_pct=100, message="Done")
            except asyncio.CancelledError:
                await self.update(job_id, status="cancelled", message="Cancelled")
                raise
            except Exception as exc:  # surface last meaningful line, keep full trace in log
                if log_path:
                    try:
                        with open(log_path, "a", encoding="utf-8") as f:
                            f.write(traceback.format_exc())
                    except OSError:
                        pass
                await self.update(job_id, status="failed", error=str(exc) or exc.__class__.__name__)


queue = JobQueue()
