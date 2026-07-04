"""faster-whisper transcription: word-level timestamps, auto HE/EN,
CUDA -> CPU fallback, streamer context as initial_prompt. Cached per source."""
from __future__ import annotations

import asyncio
import json
import logging

from ..config import settings
from ..db import SessionLocal
from ..models import Source, Streamer

log = logging.getLogger("transcribe")

_model = None
_model_key: tuple[str, str, str] | None = None


def _load_model():
    global _model, _model_key
    from faster_whisper import WhisperModel

    key = (settings.whisper_model, settings.whisper_device, settings.whisper_compute_type)
    if _model is not None and _model_key == key:
        return _model
    device = settings.whisper_device
    compute = settings.whisper_compute_type
    candidates = []
    if device in ("auto", "cuda"):
        candidates.append(("cuda", "float16" if compute == "auto" else compute))
    candidates.append(("cpu", "int8" if compute == "auto" else compute))
    last_exc: Exception | None = None
    for dev, comp in candidates:
        try:
            _model = WhisperModel(settings.whisper_model, device=dev, compute_type=comp)
            _model_key = key
            log.info("whisper model %s loaded on %s/%s", settings.whisper_model, dev, comp)
            return _model
        except Exception as exc:  # noqa: BLE001 - try next device
            last_exc = exc
            log.warning("whisper load failed on %s: %s", dev, exc)
    raise RuntimeError(f"Could not load whisper model: {last_exc}")


def _transcribe_blocking(path: str, lang: str | None, initial_prompt: str | None) -> dict:
    model = _load_model()
    segments, info = model.transcribe(
        path, language=lang, word_timestamps=True,
        initial_prompt=initial_prompt or None, vad_filter=True)
    out_segments = []
    for seg in segments:
        words = [{"w": w.word, "start": round(w.start, 3), "end": round(w.end, 3)}
                 for w in (seg.words or [])]
        out_segments.append({"start": round(seg.start, 3), "end": round(seg.end, 3),
                             "text": seg.text.strip(), "words": words})
    return {"language": info.language, "segments": out_segments}


async def transcribe_source(source_id: int, lang: str | None = None,
                            force: bool = False) -> dict:
    """Transcribe a whole source; cache on the sources row."""
    with SessionLocal() as db:
        src = db.get(Source, source_id)
        if not src or not src.file_path:
            raise ValueError("Source has no file")
        if src.transcript_json and not force:
            return json.loads(src.transcript_json)
        path = src.file_path
        prompt = ""
        if src.streamer_id:
            s = db.get(Streamer, src.streamer_id)
            if s and s.context_notes:
                prompt = s.context_notes
    result = await asyncio.to_thread(_transcribe_blocking, path, lang, prompt)
    with SessionLocal() as db:
        src = db.get(Source, source_id)
        if src:
            src.transcript_json = json.dumps(result, ensure_ascii=False)
            db.commit()
    return result


async def transcribe_file(path: str, lang: str | None = None,
                          initial_prompt: str | None = None) -> dict:
    return await asyncio.to_thread(_transcribe_blocking, path, lang, initial_prompt)
