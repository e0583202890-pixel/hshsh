"""Source download + management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Source
from ..queue import queue
from ..schemas import DownloadIn, ManualM3u8In, SourceOut
from ..services.downloader import detect_platform
from ..services.signals import analyze_source

router = APIRouter()


@router.post("/sources/download")
async def download(body: DownloadIn, db: Session = Depends(get_db)):
    job_ids = []
    for url in body.urls:
        src = Source(origin="vod", platform=detect_platform(url), url=url,
                     title=url, status="queued")
        db.add(src)
        db.commit()
        job_id = await queue.enqueue(
            "download", {"url": url, "quality": body.quality,
                         "section": body.section, "source_id": src.id},
            source_id=src.id)
        job_ids.append({"source_id": src.id, "job_id": job_id})
    return {"jobs": job_ids}


@router.post("/sources/{source_id}/manual-m3u8")
async def manual_m3u8(source_id: int, body: ManualM3u8In, db: Session = Depends(get_db)):
    src = db.get(Source, source_id)
    if not src:
        raise HTTPException(404, "Source not found")
    src.status = "queued"
    src.error = None
    db.commit()
    job_id = await queue.enqueue(
        "download", {"url": src.url or body.m3u8_url, "quality": "best",
                     "source_id": source_id, "m3u8_url": body.m3u8_url},
        source_id=source_id)
    return {"job_id": job_id}


@router.get("/sources", response_model=list[SourceOut])
def list_sources(db: Session = Depends(get_db)):
    return db.query(Source).order_by(Source.id.desc()).limit(300).all()


@router.get("/sources/{source_id}", response_model=SourceOut)
def get_source(source_id: int, db: Session = Depends(get_db)):
    src = db.get(Source, source_id)
    if not src:
        raise HTTPException(404, "Source not found")
    return src


@router.delete("/sources/{source_id}")
def delete_source(source_id: int, db: Session = Depends(get_db)):
    src = db.get(Source, source_id)
    if not src:
        raise HTTPException(404, "Source not found")
    db.delete(src)
    db.commit()
    return {"ok": True}


@router.post("/sources/{source_id}/signals")
async def compute_signals(source_id: int):
    try:
        return await analyze_source(source_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
