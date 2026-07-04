"""KICKLIPS Studio backend entry point."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import DATA_DIR
from .db import init_db
from .queue import queue
from .routers import clips, live, misc, sources
from .seed import seed
from .services import ai_clipper, downloader, export, montage
from .services.live_monitor import monitor
from .services.recorder import manager
from .ws import hub

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(name)s %(levelname)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed()
    downloader.register()
    ai_clipper.register()
    export.register()
    montage.register()
    await queue.start()
    await manager.recover_on_startup()
    monitor.start()
    yield
    await monitor.stop()
    await queue.stop()


app = FastAPI(title="KICKLIPS Studio", lifespan=lifespan)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])

app.include_router(live.router, prefix="/api")
app.include_router(sources.router, prefix="/api")
app.include_router(clips.router, prefix="/api")
app.include_router(misc.router, prefix="/api")


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await hub.connect(ws)
    try:
        while True:
            await ws.receive_text()  # keepalive pings from the client
    except WebSocketDisconnect:
        await hub.disconnect(ws)


# Serve media files (thumbnails, rendered clips) for the frontend player.
app.mount("/media", StaticFiles(directory=str(DATA_DIR)), name="media")

# Serve the built React app when it exists (production mode).
_frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="app")
