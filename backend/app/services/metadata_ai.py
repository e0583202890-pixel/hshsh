"""Per-platform Hebrew title/description/hashtags generation (OpenRouter/Anthropic)."""
from __future__ import annotations

import json
import logging

from ..db import SessionLocal
from ..models import Clip, Source, Streamer
from . import llm
from .ai_clipper import safe_json

log = logging.getLogger("metadata_ai")

SYSTEM = ("You write high-CTR Hebrew titles/descriptions/hashtags for Kick clip Shorts, "
          "tuned per platform. Output STRICT JSON only.")

USER = """Streamer {display_name}. Platform {platform}. Clip transcript
{clip_transcript}. Hook {hook}. Context {context_notes}.
Return {{ "title_he": "...", "description_he": "...", "hashtags": ["HE+EN, 8-12"] }}."""


async def generate_metadata(clip_id: int, platform: str) -> dict:
    with SessionLocal() as db:
        clip = db.get(Clip, clip_id)
        if not clip:
            raise ValueError("Clip not found")
        src = db.get(Source, clip.source_id)
        streamer = db.get(Streamer, src.streamer_id) if src and src.streamer_id else None
        display_name = (streamer.display_name or streamer.handle) if streamer else "unknown"
        context_notes = streamer.context_notes if streamer else ""
        hook = clip.hook_text or ""
        transcript = ""
        if clip.transcript_json:
            segs = json.loads(clip.transcript_json).get("segments", [])
            transcript = " ".join(s.get("text", "") for s in segs)[:6000]
        elif src and src.transcript_json:
            segs = json.loads(src.transcript_json).get("segments", [])
            transcript = " ".join(s.get("text", "") for s in segs
                                  if clip.start_sec - 2 <= s.get("start", 0) <= clip.end_sec + 2)[:6000]

    user = USER.format(display_name=display_name, platform=platform,
                       clip_transcript=transcript or "(no transcript)", hook=hook,
                       context_notes=context_notes or "none")
    for _ in range(2):
        raw = await llm.complete(SYSTEM, user, max_tokens=1024)
        parsed = safe_json(raw)
        if parsed and "title_he" in parsed:
            return parsed
    raise RuntimeError("AI returned malformed metadata twice")
