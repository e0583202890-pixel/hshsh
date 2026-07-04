"""Clip CRUD + build steps (vertical, captions, brand, audio, effects, export)."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Clip, Source, Streamer
from ..queue import queue
from ..schemas import (AudioIn, BrandIn, CaptionsIn, ClipIn, ClipOut, EffectsIn,
                       ExportIn, TranscriptPatchIn, VerticalIn)
from ..services.ai_clipper import content_hash
from ..services.captions import clip_transcript
from ..services.transcribe import transcribe_source

router = APIRouter()


@router.post("/clips", response_model=ClipOut)
def create_clip(body: ClipIn, db: Session = Depends(get_db)):
    src = db.get(Source, body.source_id)
    if not src:
        raise HTTPException(404, "Source not found")
    mode = body.vertical_mode
    if not mode and src.streamer_id:
        s = db.get(Streamer, src.streamer_id)
        mode = s.default_vertical_mode if s else None
    clip = Clip(source_id=body.source_id, title=body.title,
                start_sec=body.start_sec, end_sec=body.end_sec,
                duration_sec=body.end_sec - body.start_sec,
                vertical_mode=mode or "facecam_stack",
                preset_id=body.preset_id, brandkit_id=body.brandkit_id,
                content_hash=content_hash(body.source_id, body.start_sec, body.end_sec))
    db.add(clip)
    db.commit()
    return clip


@router.get("/clips", response_model=list[ClipOut])
def list_clips(source_id: int | None = None, db: Session = Depends(get_db)):
    q = db.query(Clip).filter(Clip.status != "discarded")
    if source_id:
        q = q.filter(Clip.source_id == source_id)
    return q.order_by(Clip.id.desc()).limit(300).all()


@router.get("/clips/{clip_id}", response_model=ClipOut)
def get_clip(clip_id: int, db: Session = Depends(get_db)):
    clip = db.get(Clip, clip_id)
    if not clip:
        raise HTTPException(404, "Clip not found")
    return clip


@router.delete("/clips/{clip_id}")
def delete_clip(clip_id: int, db: Session = Depends(get_db)):
    clip = db.get(Clip, clip_id)
    if not clip:
        raise HTTPException(404, "Clip not found")
    clip.status = "discarded"
    db.commit()
    return {"ok": True}


@router.post("/clips/{clip_id}/vertical")
def set_vertical(clip_id: int, body: VerticalIn, db: Session = Depends(get_db)):
    clip = db.get(Clip, clip_id)
    if not clip:
        raise HTTPException(404, "Clip not found")
    clip.vertical_mode = body.mode
    clip.vertical_params_json = json.dumps(body.params)
    db.commit()
    return {"ok": True}


@router.post("/clips/{clip_id}/captions")
async def gen_captions(clip_id: int, body: CaptionsIn, db: Session = Depends(get_db)):
    clip = db.get(Clip, clip_id)
    if not clip:
        raise HTTPException(404, "Clip not found")
    src = db.get(Source, clip.source_id)
    if not src or not src.file_path:
        raise HTTPException(400, "Source has no file")
    source_transcript = json.loads(src.transcript_json) if src.transcript_json else \
        await transcribe_source(src.id, lang=body.lang)
    transcript = clip_transcript(source_transcript, clip.start_sec, clip.end_sec)
    clip.transcript_json = json.dumps(transcript, ensure_ascii=False)
    clip.has_captions = body.burn
    clip.caption_lang = body.lang or transcript.get("language")
    db.commit()
    return {"transcript": transcript}


@router.patch("/clips/{clip_id}/transcript")
def patch_transcript(clip_id: int, body: TranscriptPatchIn, db: Session = Depends(get_db)):
    clip = db.get(Clip, clip_id)
    if not clip:
        raise HTTPException(404, "Clip not found")
    existing = json.loads(clip.transcript_json or "{}")
    existing["segments"] = body.segments
    clip.transcript_json = json.dumps(existing, ensure_ascii=False)
    db.commit()
    return {"ok": True}


@router.post("/clips/{clip_id}/brand")
def set_brand(clip_id: int, body: BrandIn, db: Session = Depends(get_db)):
    clip = db.get(Clip, clip_id)
    if not clip:
        raise HTTPException(404, "Clip not found")
    if body.brandkit_id is not None:
        clip.brandkit_id = body.brandkit_id
    if body.hook_text is not None:
        clip.hook_text = body.hook_text
    db.commit()
    return {"ok": True}


@router.post("/clips/{clip_id}/audio")
def set_audio(clip_id: int, body: AudioIn, db: Session = Depends(get_db)):
    clip = db.get(Clip, clip_id)
    if not clip:
        raise HTTPException(404, "Clip not found")
    params = json.loads(clip.vertical_params_json or "{}")
    params["audio"] = body.model_dump()
    clip.vertical_params_json = json.dumps(params)
    db.commit()
    return {"ok": True}


@router.post("/clips/{clip_id}/effects")
def set_effects(clip_id: int, body: EffectsIn, db: Session = Depends(get_db)):
    clip = db.get(Clip, clip_id)
    if not clip:
        raise HTTPException(404, "Clip not found")
    params = json.loads(clip.vertical_params_json or "{}")
    params["effects"] = body.model_dump()
    clip.vertical_params_json = json.dumps(params)
    db.commit()
    return {"ok": True}


@router.post("/clips/{clip_id}/export")
async def export_clip(clip_id: int, body: ExportIn, db: Session = Depends(get_db)):
    clip = db.get(Clip, clip_id)
    if not clip:
        raise HTTPException(404, "Clip not found")
    if clip.end_sec <= clip.start_sec:
        raise HTTPException(400, "Invalid clip timestamps")
    if body.preset_id:
        clip.preset_id = body.preset_id
    clip.status = "building"
    db.commit()
    job_id = await queue.enqueue("export", {"clip_id": clip_id,
                                            "aspect_ratios": body.aspect_ratios},
                                 clip_id=clip_id)
    return {"job_id": job_id}


@router.post("/clips/{clip_id}/regenerate")
async def regenerate_clip(clip_id: int, db: Session = Depends(get_db)):
    clip = db.get(Clip, clip_id)
    if not clip:
        raise HTTPException(404, "Clip not found")
    clip.status = "building"
    db.commit()
    job_id = await queue.enqueue("build_clip", {"clip_id": clip_id, "auto": True},
                                 clip_id=clip_id)
    return {"job_id": job_id}
