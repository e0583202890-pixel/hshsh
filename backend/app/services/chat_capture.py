"""Kick chat capture: connect the channel's chat websocket during a recording
and log timestamped messages -> powers real chat-spike detection.

Degrades gracefully: if the chatroom id or websocket endpoint cannot be
reached, recording continues without chat.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path

import httpx

log = logging.getLogger("chat_capture")

# Kick chat rides on Pusher; this app key is public in the Kick web client.
PUSHER_URL = ("wss://ws-us2.pusher.com/app/32cbd69e4b950bf97679"
              "?protocol=7&client=js&version=8.4.0-rc2&flash=false")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


class ChatCapture:
    def __init__(self, channel: str) -> None:
        self.channel = channel
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._t0 = time.monotonic()

    def start(self, out_path: Path) -> None:
        self._t0 = time.monotonic()
        self._task = asyncio.create_task(self._run(out_path))

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass

    async def _chatroom_id(self) -> int | None:
        try:
            async with httpx.AsyncClient(timeout=15, headers={"User-Agent": UA}) as client:
                resp = await client.get(f"https://kick.com/api/v2/channels/{self.channel}")
            if resp.status_code == 200:
                return (resp.json().get("chatroom") or {}).get("id")
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("chatroom id fetch failed: %s", exc)
        return None

    async def _run(self, out_path: Path) -> None:
        chatroom_id = await self._chatroom_id()
        if not chatroom_id:
            log.warning("chat capture unavailable for %s (no chatroom id)", self.channel)
            return
        try:
            import websockets
        except ImportError:
            log.warning("websockets package missing - chat capture disabled")
            return
        while not self._stop.is_set():
            try:
                async with websockets.connect(PUSHER_URL, user_agent_header=UA) as ws:
                    await ws.send(json.dumps({
                        "event": "pusher:subscribe",
                        "data": {"auth": "", "channel": f"chatrooms.{chatroom_id}.v2"}}))
                    with open(out_path, "a", encoding="utf-8") as f:
                        async for raw in ws:
                            if self._stop.is_set():
                                return
                            self._handle(raw, f)
            except asyncio.CancelledError:
                return
            except Exception as exc:  # noqa: BLE001 - reconnect, never crash the recording
                log.warning("chat ws dropped (%s), reconnecting in 10s", exc)
                await asyncio.sleep(10)

    def _handle(self, raw: str | bytes, f) -> None:
        try:
            msg = json.loads(raw)
            if "ChatMessageEvent" not in str(msg.get("event", "")):
                return
            data = json.loads(msg.get("data") or "{}")
            entry = {"t_offset_sec": round(time.monotonic() - self._t0, 2),
                     "user": (data.get("sender") or {}).get("username", ""),
                     "message": data.get("content", "")}
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            f.flush()
        except (json.JSONDecodeError, TypeError):
            pass
