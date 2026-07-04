"""AI Auto-Clip engine: transcript + signals -> Claude highlight selection +
virality scoring -> auto-build vertical captioned branded clips.

Safe JSON parsing, one retry, degrade to signal-only highlights if the API is
unavailable. Never crash on malformed AI output.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re

from ..config import settings
from ..db import SessionLocal
from ..models import AiRun, BrandKit, Clip, Preset, Source, Streamer
from ..queue import queue
from . import llm
from .signals import analyze_source, signals_near
from .transcribe import transcribe_source

log = logging.getLogger("ai_clipper")

HIGHLIGHT_SYSTEM = (
    "You are a senior short-form clip producer for an Israeli Kick clips channel. You "
    "find moments most likely to perform as YouTube Shorts / TikTok / Reels. Output "
    "STRICT JSON only - no prose, no markdown fences.")

HIGHLIGHT_USER = """Streamer: {display_name} (Kick). Audience: Israeli, Hebrew-first.
Streamer context (games, catchphrases, correct name spellings): {context_notes}
Timestamped transcript (seconds): {transcript_segments}
Non-text signals: {signals}
Exclusions (skip these): {exclusions}
Find the {n} best self-contained moments, each 15-60s. For each:
{{ "start": float, "end": float, "hook": "<=8 words",
  "hook_variants": ["2-3 alt openers"], "title_he": "<=60 chars",
  "hashtags": ["HE+EN, 5-8"], "virality_score": 0-100, "tier": "High|Medium|Low",
  "reason": "1-2 lines: hook, emotion, payoff, shareability" }}
Return {{ "clips": [ ... ] }}. JSON only."""

MAX_TRANSCRIPT_CHARS = 90_000  # chunk long transcripts


def safe_json(raw: str) -> dict | None:
    """Strip fences/noise and parse; return None on failure."""
    raw = raw.strip()
    raw = re.sub(r"^```[a-z]*\s*|\s*```$", "", raw)
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(raw[start:end + 1])
    except json.JSONDecodeError:
        return None


async def _ask_llm(system: str, user: str) -> dict | None:
    """Call the configured LLM (OpenRouter or Anthropic). Returns parsed JSON or
    None (API down / malformed twice) so callers degrade to signal-only."""
    for attempt in range(2):  # retry once on malformed output
        try:
            raw = await llm.complete(system, user, max_tokens=4096)
        except Exception as exc:  # noqa: BLE001 - API down -> caller degrades
            log.warning("LLM call failed: %s", exc)
            return None
        parsed = safe_json(raw)
        if parsed is not None:
            return parsed
        log.warning("malformed AI JSON (attempt %d)", attempt + 1)
    return None


def _chunk_segments(segments: list[dict]) -> list[list[dict]]:
    chunks: list[list[dict]] = [[]]
    size = 0
    for seg in segments:
        line = json.dumps(seg, ensure_ascii=False)
        if size + len(line) > MAX_TRANSCRIPT_CHARS and chunks[-1]:
            chunks.append([])
            size = 0
        chunks[-1].append(seg)
        size += len(line)
    return chunks


def _compact_transcript(segments: list[dict]) -> list[dict]:
    return [{"start": s["start"], "end": s["end"], "text": s["text"]} for s in segments]


def _signal_only_candidates(signals: dict, n: int) -> list[dict]:
    """Fallback ranking when the LLM is unavailable: strongest signal windows."""
    points: list[tuple[float, float, str]] = []
    for key, label in (("audio_hype_windows", "audio hype"),
                       ("chat_spike_windows", "chat spike"),
                       ("face_reactions", "face reaction")):
        for p in signals.get(key, []):
            points.append((p.get("score", 1.0), p["t"], label))
    points.sort(reverse=True)
    out = []
    for score, t, label in points[:n]:
        out.append({"start": max(0.0, t - 15), "end": t + 25,
                    "hook": "", "hook_variants": [], "title_he": "",
                    "hashtags": [], "virality_score": min(99, int(40 + score * 10)),
                    "tier": "Medium",
                    "reason": f"Signal-only fallback: strong {label} at {t:.0f}s "
                              "(AI ranking unavailable)"})
    return out


def content_hash(source_id: int, start: float, end: float) -> str:
    return hashlib.sha1(f"{source_id}:{round(start)}:{round(end)}".encode()).hexdigest()[:16]


def _overlaps_existing(db, source_id: int, start: float, end: float) -> bool:
    for c in db.query(Clip).filter(Clip.source_id == source_id,
                                   Clip.status != "discarded").all():
        overlap = min(end, c.end_sec) - max(start, c.start_sec)
        shorter = min(end - start, (c.end_sec - c.start_sec) or 1)
        if shorter > 0 and overlap / shorter > 0.6:
            return True
    return False


async def handle_autoclip(job_id: int, params: dict) -> None:
    source_id = params["source_id"]
    n = int(params.get("n", 10))
    exclusions = params.get("exclusions", [])
    brandkit_id = params.get("brandkit_id")
    preset_id = params.get("preset_id")

    with SessionLocal() as db:
        src = db.get(Source, source_id)
        if not src or not src.file_path:
            raise RuntimeError("Source has no downloaded file")
        streamer = db.get(Streamer, src.streamer_id) if src.streamer_id else None
        display_name = streamer.display_name or streamer.handle if streamer else "unknown"
        context_notes = streamer.context_notes if streamer else ""
        if brandkit_id is None and streamer and streamer.default_brandkit_id:
            brandkit_id = streamer.default_brandkit_id
        if brandkit_id is None:
            kit = db.query(BrandKit).filter(BrandKit.is_default.is_(True)).first()
            brandkit_id = kit.id if kit else None
        if preset_id is None:
            preset = db.query(Preset).filter(Preset.is_default.is_(True)).first()
            preset_id = preset.id if preset else None

    await queue.update(job_id, progress_pct=5, message="Transcribing source")
    transcript = await transcribe_source(source_id)

    await queue.update(job_id, progress_pct=35, message="Analyzing signals")
    signals = await analyze_source(source_id)

    await queue.update(job_id, progress_pct=50, message="Asking AI for highlights")
    candidates: list[dict] = []
    for chunk in _chunk_segments(_compact_transcript(transcript["segments"])):
        user = HIGHLIGHT_USER.format(
            display_name=display_name, context_notes=context_notes or "none",
            transcript_segments=json.dumps(chunk, ensure_ascii=False),
            signals=json.dumps(signals, ensure_ascii=False)[:8000],
            exclusions=json.dumps(exclusions, ensure_ascii=False), n=n)
        parsed = await _ask_llm(HIGHLIGHT_SYSTEM, user)
        if parsed and isinstance(parsed.get("clips"), list):
            candidates.extend(parsed["clips"])
    if not candidates:
        await queue.update(job_id, message="AI unavailable - using signal-only highlights")
        candidates = _signal_only_candidates(signals, n)
    if not candidates:
        raise RuntimeError("No highlight candidates found (no AI and no strong signals)")

    # Fuse: boost scores when non-text signals coincide.
    for c in candidates:
        fired = signals_near(signals, float(c.get("start", 0)), float(c.get("end", 0)))
        c["signals"] = fired
        c["virality_score"] = min(100, int(c.get("virality_score", 50)) + 5 * len(fired))
    candidates.sort(key=lambda c: c.get("virality_score", 0), reverse=True)
    candidates = candidates[:n]

    with SessionLocal() as db:
        db.add(AiRun(source_id=source_id, model=llm.active_model(),
                     n_requested=n, n_returned=len(candidates),
                     params_json=json.dumps(params)))
        db.commit()

    await queue.update(job_id, progress_pct=60, message="Building clips")
    built = 0
    for i, c in enumerate(candidates):
        start, end = float(c.get("start", 0)), float(c.get("end", 0))
        if end <= start:
            continue
        with SessionLocal() as db:
            if _overlaps_existing(db, source_id, start, end):
                continue  # dedup
            clip = Clip(source_id=source_id, title=c.get("title_he", ""),
                        start_sec=start, end_sec=end,
                        duration_sec=end - start,
                        virality_score=int(c.get("virality_score", 50)),
                        virality_tier=c.get("tier", "Medium"),
                        virality_reason=c.get("reason", ""),
                        signals_json=json.dumps(c.get("signals", [])),
                        hook_text=c.get("hook", ""),
                        hook_variants_json=json.dumps(c.get("hook_variants", []), ensure_ascii=False),
                        hashtags_json=json.dumps(c.get("hashtags", []), ensure_ascii=False),
                        brandkit_id=brandkit_id, preset_id=preset_id,
                        content_hash=content_hash(source_id, start, end),
                        status="building")
            db.add(clip)
            db.commit()
            clip_id = clip.id
        await queue.enqueue("build_clip", {"clip_id": clip_id, "auto": True}, clip_id=clip_id)
        built += 1
        await queue.update(job_id, progress_pct=60 + 35 * (i + 1) / max(1, len(candidates)),
                           message=f"Queued clip build {built}")
    await queue.update(job_id, status="done", progress_pct=100,
                       message=f"Done: {built} clips queued for build")


def register() -> None:
    from ..queue import register_handler
    register_handler("autoclip", handle_autoclip)
