"""Streamers, autoclip, jobs, brand kits, presets, publish, settings, health, library."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import DOWNLOADS_DIR, OUTPUT_DIR, RECORDINGS_DIR, WORK_DIR
from ..db import get_db
from ..models import (BrandKit, Clip, Job, Preset, PublishQueueItem, Setting,
                      Source, Streamer)
from ..queue import queue
from ..schemas import (AutoClipIn, BrandKitIn, BrandKitOut, JobOut, MetadataIn,
                       MontageIn, PresetIn, PresetOut, ScheduleIn, StreamerIn,
                       StreamerLayoutIn, StreamerOut)
from ..services import profiles
from ..services.downloader import detect_platform
from ..services.health import health_report
from ..services.metadata_ai import generate_metadata

router = APIRouter()


# ---- streamers ----
@router.get("/streamers", response_model=list[StreamerOut])
def list_streamers(db: Session = Depends(get_db)):
    return db.query(Streamer).order_by(Streamer.handle).all()


@router.post("/streamers", response_model=StreamerOut)
def create_streamer(body: StreamerIn, db: Session = Depends(get_db)):
    s = Streamer(**body.model_dump())
    db.add(s)
    db.commit()
    return s


@router.put("/streamers/{streamer_id}", response_model=StreamerOut)
def update_streamer(streamer_id: int, body: StreamerIn, db: Session = Depends(get_db)):
    s = db.get(Streamer, streamer_id)
    if not s:
        raise HTTPException(404, "Streamer not found")
    for k, v in body.model_dump().items():
        setattr(s, k, v)
    db.commit()
    return s


@router.put("/streamers/{streamer_id}/layout")
def update_layout(streamer_id: int, body: StreamerLayoutIn):
    try:
        profiles.save_layout(streamer_id,
                             body.facecam_rect.model_dump() if body.facecam_rect else None,
                             body.gameplay_rect.model_dump() if body.gameplay_rect else None,
                             body.split_ratio)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    return {"ok": True}


@router.post("/streamers/{streamer_id}/suggest-facecam")
async def suggest_facecam(streamer_id: int, source_id: int, db: Session = Depends(get_db)):
    src = db.get(Source, source_id)
    if not src or not src.file_path:
        raise HTTPException(400, "Source has no file")
    rect = await profiles.suggest_facecam_rect(src.file_path)
    return {"rect": rect}


# ---- autoclip ----
@router.post("/autoclip")
async def autoclip(body: AutoClipIn, db: Session = Depends(get_db)):
    source_id = body.source_id
    if not source_id and body.url:
        src = Source(origin="vod", platform=detect_platform(body.url), url=body.url,
                     title=body.url, status="queued")
        db.add(src)
        db.commit()
        source_id = src.id
        dl_job = await queue.enqueue("download", {"url": body.url, "quality": "best",
                                                  "source_id": source_id},
                                     source_id=source_id)
        # The autoclip job will fail fast if the download hasn't finished;
        # for URL flow the operator runs autoclip after download completes.
        return {"source_id": source_id, "download_job_id": dl_job,
                "note": "Run auto-clip again on this source after the download finishes"}
    if not source_id:
        raise HTTPException(400, "Provide source_id or url")
    job_id = await queue.enqueue("autoclip", {"source_id": source_id, "n": body.n,
                                              "exclusions": body.exclusions,
                                              "brandkit_id": body.brandkit_id,
                                              "preset_id": body.preset_id},
                                 source_id=source_id)
    return {"job_id": job_id}


# ---- jobs ----
@router.get("/jobs", response_model=list[JobOut])
def list_jobs(db: Session = Depends(get_db)):
    return db.query(Job).order_by(Job.id.desc()).limit(200).all()


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: int):
    queue.cancel(job_id)
    return {"ok": True}


@router.post("/jobs/{job_id}/retry")
async def retry_job(job_id: int):
    await queue.retry(job_id)
    return {"ok": True}


# ---- montage ----
@router.post("/montage")
async def create_montage(body: MontageIn):
    job_id = await queue.enqueue("montage", body.model_dump())
    return {"job_id": job_id}


# ---- brand kits ----
@router.get("/brandkits", response_model=list[BrandKitOut])
def list_brandkits(db: Session = Depends(get_db)):
    return db.query(BrandKit).all()


@router.post("/brandkits", response_model=BrandKitOut)
def create_brandkit(body: BrandKitIn, db: Session = Depends(get_db)):
    kit = BrandKit(**body.model_dump())
    db.add(kit)
    db.commit()
    return kit


@router.put("/brandkits/{kit_id}", response_model=BrandKitOut)
def update_brandkit(kit_id: int, body: BrandKitIn, db: Session = Depends(get_db)):
    kit = db.get(BrandKit, kit_id)
    if not kit:
        raise HTTPException(404, "Brand kit not found")
    for k, v in body.model_dump().items():
        setattr(kit, k, v)
    db.commit()
    return kit


# ---- presets ----
@router.get("/presets", response_model=list[PresetOut])
def list_presets(db: Session = Depends(get_db)):
    return db.query(Preset).all()


@router.post("/presets", response_model=PresetOut)
def create_preset(body: PresetIn, db: Session = Depends(get_db)):
    p = Preset(**body.model_dump())
    db.add(p)
    db.commit()
    return p


# ---- publish ----
@router.post("/publish/metadata")
async def publish_metadata(body: MetadataIn):
    try:
        meta = await generate_metadata(body.clip_id, body.platform)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(400, str(exc))
    return meta


@router.post("/publish/schedule")
def publish_schedule(body: ScheduleIn, db: Session = Depends(get_db)):
    item = PublishQueueItem(clip_id=body.clip_id, platform=body.platform,
                            scheduled_at=body.scheduled_at)
    db.add(item)
    db.commit()
    return {"id": item.id}


@router.get("/publish/queue")
def publish_queue(db: Session = Depends(get_db)):
    items = db.query(PublishQueueItem).order_by(PublishQueueItem.id.desc()).limit(200).all()
    return [{"id": i.id, "clip_id": i.clip_id, "platform": i.platform,
             "scheduled_at": i.scheduled_at, "status": i.status} for i in items]


@router.post("/clips/{clip_id}/preflight")
def preflight(clip_id: int, db: Session = Depends(get_db)):
    clip = db.get(Clip, clip_id)
    if not clip:
        raise HTTPException(404, "Clip not found")
    preset = db.get(Preset, clip.preset_id) if clip.preset_id else \
        db.query(Preset).filter(Preset.is_default.is_(True)).first()
    checks = []
    dur = clip.duration_sec or (clip.end_sec - clip.start_sec)
    max_dur = preset.max_duration_sec if preset else 60
    checks.append({"name": "duration", "ok": dur <= max_dur,
                   "detail": f"{dur:.0f}s / max {max_dur}s"})
    has_file = bool(clip.file_path and Path(clip.file_path).exists())
    checks.append({"name": "rendered_file", "ok": has_file,
                   "detail": clip.file_path or "not rendered yet"})
    return {"checks": checks, "all_ok": all(c["ok"] for c in checks)}


# ---- settings + health + storage ----
@router.get("/settings")
def get_settings(db: Session = Depends(get_db)):
    from ..config import settings as cfg
    stored = {s.key: s.value for s in db.query(Setting).all()}
    return {"anthropic_model": cfg.anthropic_model,
            "anthropic_key_set": bool(cfg.anthropic_api_key),
            "whisper_model": cfg.whisper_model, "whisper_device": cfg.whisper_device,
            "live_poll_interval_sec": cfg.live_poll_interval_sec,
            "disk_min_free_gb": cfg.disk_min_free_gb,
            "queue_concurrency": cfg.queue_concurrency,
            "ui_language": stored.get("ui_language", cfg.ui_language),
            "auto_purge_sources": stored.get("auto_purge_sources", "false") == "true",
            "overrides": stored}


@router.put("/settings")
def put_settings(body: dict, db: Session = Depends(get_db)):
    from ..config import settings as cfg
    for key, value in body.items():
        row = db.get(Setting, key)
        if row:
            row.value = str(value)
        else:
            db.add(Setting(key=key, value=str(value)))
        # Apply live-tunable settings immediately.
        if key == "live_poll_interval_sec":
            cfg.live_poll_interval_sec = int(value)
        elif key == "disk_min_free_gb":
            cfg.disk_min_free_gb = float(value)
        elif key == "whisper_model":
            cfg.whisper_model = str(value)
        elif key == "anthropic_model":
            cfg.anthropic_model = str(value)
    db.commit()
    return {"ok": True}


@router.get("/health")
async def health():
    return await health_report()


@router.get("/storage")
def storage():
    def dir_size(p: Path) -> int:
        return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
    import shutil as sh
    usage = sh.disk_usage(OUTPUT_DIR)
    return {"free_gb": round(usage.free / 1024**3, 1),
            "dirs": {"recordings": dir_size(RECORDINGS_DIR),
                     "downloads": dir_size(DOWNLOADS_DIR),
                     "work": dir_size(WORK_DIR),
                     "output": dir_size(OUTPUT_DIR)}}
