"""Live/watchlist/recordings endpoints."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Recording, Streamer
from ..schemas import ClipLastIn, RecordingOut, RecordingStartIn, StreamerIn
from ..services.live_monitor import live_state, monitor
from ..services.recorder import get_streamer_for_start, manager

router = APIRouter()


@router.get("/live/status")
async def live_status(db: Session = Depends(get_db)):
    watched = db.query(Streamer).filter(Streamer.is_watched.is_(True)).all()
    out = []
    for s in watched:
        state = live_state.get(s.handle.lower(), {})
        rec_id = next((rid for rid, t in manager.active.items()
                       if t.channel.lower() == s.handle.lower()), None)
        out.append({"streamer_id": s.id, "handle": s.handle,
                    "display_name": s.display_name or s.handle,
                    "live": bool(state.get("live")), "title": state.get("title", ""),
                    "viewers": state.get("viewers", 0),
                    "auto_record": s.auto_record, "auto_clip_on_end": s.auto_clip_on_end,
                    "recording_id": rec_id})
    return {"streamers": out,
            "active_recordings": [
                {"recording_id": rid, "channel": t.channel,
                 "elapsed_sec": round(t.elapsed_sec()), "size_bytes": t.total_bytes(),
                 "reconnect_count": t.reconnects}
                for rid, t in manager.active.items()]}


@router.post("/live/poll-now")
async def poll_now():
    await monitor.poll_once()
    return {"ok": True}


@router.post("/watchlist")
def add_to_watchlist(body: StreamerIn, db: Session = Depends(get_db)):
    handle = body.handle.rstrip("/").split("/")[-1]
    existing = db.query(Streamer).filter(Streamer.handle.ilike(handle)).first()
    if existing:
        existing.is_watched = True
        db.commit()
        return {"streamer_id": existing.id}
    s = Streamer(platform=body.platform, handle=handle,
                 display_name=body.display_name or handle, is_watched=True,
                 context_notes=body.context_notes, auto_record=body.auto_record,
                 auto_clip_on_end=body.auto_clip_on_end)
    db.add(s)
    db.commit()
    return {"streamer_id": s.id}


@router.delete("/watchlist/{streamer_id}")
def remove_from_watchlist(streamer_id: int, db: Session = Depends(get_db)):
    s = db.get(Streamer, streamer_id)
    if not s:
        raise HTTPException(404, "Streamer not found")
    s.is_watched = False
    db.commit()
    return {"ok": True}


@router.post("/recordings/start")
async def start_recording(body: RecordingStartIn):
    try:
        channel, sid, auto_clip = await get_streamer_for_start(body.streamer_id, body.url)
        rec_id = await manager.start(channel, streamer_id=sid, auto_clip_on_end=auto_clip)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"recording_id": rec_id}


@router.post("/recordings/{recording_id}/stop")
async def stop_recording(recording_id: int):
    await manager.stop(recording_id)
    return {"ok": True}


@router.post("/recordings/{recording_id}/clip-last")
def clip_last(recording_id: int, body: ClipLastIn):
    try:
        mark = manager.mark_clip_last(recording_id, body.seconds)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"mark": mark}


@router.get("/recordings", response_model=list[RecordingOut])
def list_recordings(db: Session = Depends(get_db)):
    return db.query(Recording).order_by(Recording.id.desc()).limit(200).all()


@router.get("/recordings/{recording_id}")
def get_recording(recording_id: int, db: Session = Depends(get_db)):
    rec = db.get(Recording, recording_id)
    if not rec:
        raise HTTPException(404, "Recording not found")
    return {**RecordingOut.model_validate(rec).model_dump(),
            "clip_marks": json.loads(rec.clip_marks_json or "[]")}
