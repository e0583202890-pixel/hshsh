"""Kick live-status polling + auto-record on go-live."""
from __future__ import annotations

import asyncio
import logging

import httpx

from ..config import settings
from ..db import SessionLocal
from ..models import Streamer
from ..ws import hub
from .recorder import manager

log = logging.getLogger("live_monitor")

KICK_API = "https://kick.com/api/v2/channels/{handle}"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

# handle(lower) -> {"live": bool, "title": str, "viewers": int}
live_state: dict[str, dict] = {}


async def is_channel_live(handle: str) -> bool:
    state = await fetch_channel_status(handle)
    return bool(state and state.get("live"))


async def fetch_channel_status(handle: str) -> dict | None:
    """Poll Kick's public channel API; fall back to cloudscraper on 403."""
    url = KICK_API.format(handle=handle)
    try:
        async with httpx.AsyncClient(timeout=15, headers={"User-Agent": UA}) as client:
            resp = await client.get(url)
        if resp.status_code == 200:
            return _parse(resp.json())
        if resp.status_code == 403:
            return await _fetch_with_cloudscraper(url)
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("live status fetch failed for %s: %s", handle, exc)
    return None


async def _fetch_with_cloudscraper(url: str) -> dict | None:
    def _blocking() -> dict | None:
        try:
            import cloudscraper
            scraper = cloudscraper.create_scraper()
            resp = scraper.get(url, timeout=15)
            if resp.status_code == 200:
                return _parse(resp.json())
        except Exception as exc:  # noqa: BLE001 - degrade gracefully
            log.warning("cloudscraper fetch failed: %s", exc)
        return None
    return await asyncio.to_thread(_blocking)


def _parse(data: dict) -> dict:
    ls = data.get("livestream") or {}
    return {"live": bool(ls and ls.get("is_live", True)),
            "title": (ls.get("session_title") or "") if ls else "",
            "viewers": (ls.get("viewer_count") or 0) if ls else 0}


class LiveMonitor:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()

    async def _loop(self) -> None:
        while True:
            try:
                await self.poll_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - the monitor must never die
                log.warning("live monitor poll error: %s", exc)
            await asyncio.sleep(max(30, settings.live_poll_interval_sec))

    async def poll_once(self) -> None:
        with SessionLocal() as db:
            watched = db.query(Streamer).filter(Streamer.is_watched.is_(True)).all()
            streamers = [(s.id, s.handle, s.auto_record, s.auto_clip_on_end) for s in watched]
        for sid, handle, auto_record, auto_clip in streamers:
            state = await fetch_channel_status(handle)
            if state is None:
                continue
            prev = live_state.get(handle.lower(), {}).get("live")
            live_state[handle.lower()] = state
            if state["live"] != prev:
                await hub.broadcast({"kind": "live_status", "streamer_id": sid,
                                     "handle": handle, "live": state["live"],
                                     "title": state["title"], "viewers": state["viewers"]})
            if (state["live"] and auto_record
                    and not manager.is_recording_channel(handle)):
                try:
                    await manager.start(handle, streamer_id=sid, auto_clip_on_end=auto_clip)
                    log.info("auto-record started for %s", handle)
                except ValueError as exc:
                    log.warning("auto-record start failed for %s: %s", handle, exc)


monitor = LiveMonitor()
