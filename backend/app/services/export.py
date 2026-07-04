"""Clip build + export pipeline.

Render order: trim -> vertical/reframe -> loudnorm -> captions -> branding ->
encode, combined into as few ffmpeg passes as possible (one trim/vertical/audio
pass + one captions/branding pass).
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from ..config import LOGS_DIR, OUTPUT_DIR, WORK_DIR
from ..db import SessionLocal
from ..models import BrandKit, Clip, Preset, Source, Streamer
from ..queue import queue
from ..config import settings
from .audio import loudnorm_filter
from .branding import build_brand_filters, caption_style_from_kit, get_kit, lower_third_for_clip
from .captions import burn_args, clip_transcript, write_ass
from .effects import punch_in_filter
from .probe import probe
from .reframe import auto_reframe_filter
from .thumbs import grab_frame
from .transcribe import transcribe_source
from .util import run_process, slugify
from .vertical import build_vertical_filter, encoder_args


def _clip_ctx(clip_id: int) -> dict:
    with SessionLocal() as db:
        clip = db.get(Clip, clip_id)
        if not clip:
            raise RuntimeError("Clip not found")
        src = db.get(Source, clip.source_id)
        if not src or not src.file_path:
            raise RuntimeError("Clip source has no file")
        streamer = db.get(Streamer, src.streamer_id) if src.streamer_id else None
        preset = db.get(Preset, clip.preset_id) if clip.preset_id else \
            db.query(Preset).filter(Preset.is_default.is_(True)).first()
        return {"clip": clip, "src": src, "streamer": streamer, "preset": preset}


def _vertical_params(clip: Clip, src: Source, streamer: Streamer | None) -> tuple[str, dict]:
    mode = clip.vertical_mode
    params = json.loads(clip.vertical_params_json or "{}")
    if mode == "facecam_stack" and "facecam_rect" not in params:
        if streamer and streamer.facecam_rect_json:
            params["facecam_rect"] = json.loads(streamer.facecam_rect_json)
            params["gameplay_rect"] = (json.loads(streamer.gameplay_rect_json)
                                       if streamer.gameplay_rect_json else
                                       {"x": 0, "y": 0, "w": src.width or 1920, "h": src.height or 1080})
            params.setdefault("split_ratio", streamer.split_ratio)
        else:
            mode = "auto_reframe"  # no saved layout -> face-aware reframe
    return mode, params


def _audio_graph(aopts: dict, has_audio: bool, loud_target: float) -> tuple[str, str, list[str]]:
    """Build the pass-1 audio filter chain.

    Returns (graph_str, out_map, extra_inputs). Single-pass loudnorm is used
    (correct for a short clip; two-pass whole-file measurement would mis-apply).
    """
    if not has_audio:
        return "", "", []
    do_loud = aopts.get("loudnorm", True)
    music = aopts.get("music_path")
    use_music = bool(music and Path(music).exists())
    vol = aopts.get("music_volume", 0.3)
    if use_music:
        speech = f"[0:a]{loudnorm_filter(None, loud_target)}[sp]" if do_loud else "[0:a]anull[sp]"
        graph = (f"{speech};[1:a]volume={vol}[m];"
                 f"[sp][m]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=300[aout]"
                 if aopts.get("ducking", True) else
                 f"{speech};[1:a]volume={vol}[m];[sp][m]amix=inputs=2:duration=first[aout]")
        return graph, "[aout]", ["-stream_loop", "-1", "-i", music]
    if do_loud:
        return f"[0:a]{loudnorm_filter(None, loud_target)}[aout]", "[aout]", []
    return "", "0:a?", []


async def build_clip_file(clip_id: int, job_id: int | None = None,
                          target_w: int = 1080, target_h: int = 1920,
                          aspect: str = "9:16") -> Path:
    ctx = _clip_ctx(clip_id)
    clip: Clip = ctx["clip"]
    src: Source = ctx["src"]
    streamer = ctx["streamer"]
    preset: Preset | None = ctx["preset"]
    encoder = preset.encoder if preset else "libx264"
    loud_target = preset.loudnorm_target if preset else -14.0

    work = WORK_DIR / f"clip_{clip_id}"
    work.mkdir(parents=True, exist_ok=True)
    log = LOGS_DIR / f"job_{job_id}.log" if job_id else None
    ffmpeg = settings.which("ffmpeg") or "ffmpeg"

    async def progress(pct: float, msg: str) -> None:
        if job_id:
            await queue.update(job_id, progress_pct=pct, message=msg)

    # ---- pass 1: trim + vertical + audio ----
    await progress(10, "Trim + vertical conversion")
    mode, vparams = _vertical_params(clip, src, streamer)
    aopts = vparams.get("audio", {})
    duration = clip.end_sec - clip.start_sec
    if duration <= 0:
        raise RuntimeError("Invalid clip timestamps")
    src_info = await probe(src.file_path)
    has_audio = src_info.get("has_audio", True)

    trimmed = work / "trimmed.mp4"
    if mode == "auto_reframe":
        # Reframe needs a trimmed file first for face tracking.
        pre = work / "pre.mp4"
        rc, last = await run_process(
            [ffmpeg, "-y", "-ss", f"{clip.start_sec:.2f}", "-t", f"{duration:.2f}",
             "-i", src.file_path, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
             "-c:a", "aac", str(pre)], log)
        if rc != 0:
            raise RuntimeError(f"Trim failed: {last}")
        info = await probe(pre)
        vf = await auto_reframe_filter(str(pre), info.get("width") or 1920,
                                       info.get("height") or 1080, work)
        a_graph, a_map, a_inputs = _audio_graph(aopts, has_audio, loud_target)
        graph = f"[0:v]{vf}[v]" + (f";{a_graph}" if a_graph else "")
        cmd = [ffmpeg, "-y", "-i", str(pre), *a_inputs, "-filter_complex", graph,
               "-map", "[v]", "-map", a_map or "0:a?",
               *encoder_args(encoder), "-c:a", "aac", "-b:a", "192k", str(trimmed)]
    else:
        filter_v = build_vertical_filter(mode, vparams, target_w, target_h)
        a_graph, a_map, a_inputs = _audio_graph(aopts, has_audio, loud_target)
        graph = filter_v + (f";{a_graph}" if a_graph else "")
        cmd = [ffmpeg, "-y", "-ss", f"{clip.start_sec:.2f}", "-t", f"{duration:.2f}",
               "-i", src.file_path, *a_inputs, "-filter_complex", graph,
               "-map", "[v]", "-map", a_map or "0:a?",
               *encoder_args(encoder), "-c:a", "aac", "-b:a", "192k", str(trimmed)]
    rc, last = await run_process(cmd, log)
    if rc != 0:
        raise RuntimeError(f"Vertical render failed: {last}")

    # ---- pass 2: captions + branding ----
    await progress(55, "Captions + branding")
    kit = get_kit(clip.brandkit_id)

    ass_path = None
    if clip.has_captions or clip.transcript_json:
        transcript = None
        if clip.transcript_json:
            transcript = json.loads(clip.transcript_json)
        elif src.transcript_json:
            transcript = clip_transcript(json.loads(src.transcript_json),
                                         clip.start_sec, clip.end_sec)
        if transcript and transcript.get("segments"):
            style = caption_style_from_kit(kit)
            ass_path = write_ass(transcript, work / "captions.ass", style)
            with SessionLocal() as db:
                c = db.get(Clip, clip_id)
                if c:
                    c.has_captions = True
                    c.caption_lang = transcript.get("language")
                    if not c.transcript_json:
                        c.transcript_json = json.dumps(transcript, ensure_ascii=False)
                    db.commit()

    # Optional punch-in zoom on audio-hype peaks (clip-relative).
    fx_opts = vparams.get("effects", {})
    fx_peaks: list[float] = []
    if fx_opts.get("punch_in") and src.signals_json:
        try:
            hype = json.loads(src.signals_json).get("audio_hype_windows", [])
            fx_peaks = [p["t"] - clip.start_sec for p in hype
                        if clip.start_sec <= p["t"] <= clip.end_sec]
        except (json.JSONDecodeError, KeyError, TypeError):
            fx_peaks = []

    final_name = slugify(f"clip_{clip_id}_{clip.title or 'untitled'}_{aspect.replace(':', 'x')}") + ".mp4"
    final = OUTPUT_DIR / final_name

    def _pass2_cmd(with_kit: bool) -> tuple[list[str], list[str]]:
        steps: list[str] = []
        label = "0:v"
        if ass_path:
            steps.append(f"[{label}]{burn_args(ass_path)}[cap]")
            label = "cap"
        if fx_peaks:
            steps.append(f"[{label}]{punch_in_filter(fx_peaks, 30, fx_opts.get('intensity', 0.15))}[v]")
        else:
            steps.append(f"[{label}]null[v]")
        inputs: list[str] = []
        if with_kit and kit:
            b_inputs, b_steps = build_brand_filters(
                kit, hook_text=clip.hook_text, lower_third_name=lower_third_for_clip(src.streamer_id),
                duration=duration, w=target_w, h=target_h)
            inputs = b_inputs
            steps += b_steps
        else:
            steps.append("[v]null[vout]")
        return inputs, steps

    if kit or ass_path or fx_peaks:
        # Try full (captions + branding + effects). If branding text (drawtext /
        # missing font) fails, degrade to captions/effects only, then to a plain
        # copy - a clip must always render.
        attempts = [True, False] if kit else [False]
        ok = False
        for with_kit in attempts:
            extra_inputs, steps = _pass2_cmd(with_kit)
            cmd = [ffmpeg, "-y", "-i", str(trimmed), *extra_inputs,
                   "-filter_complex", ";".join(steps),
                   "-map", "[vout]", "-map", "0:a?",
                   *encoder_args(encoder), "-c:a", "copy", str(final)]
            rc, last = await run_process(cmd, log)
            if rc == 0:
                ok = True
                if not with_kit and kit:
                    await progress(70, "Branding overlay skipped (font/drawtext unavailable)")
                break
        if not ok:
            shutil.copyfile(trimmed, final)  # last-resort: unbranded, uncaptioned
    else:
        shutil.copyfile(trimmed, final)

    # thumbnail + bookkeeping
    await progress(90, "Finalizing")
    thumb = final.with_suffix(".jpg")
    await grab_frame(final, min(1.0, duration / 2), thumb)
    info = await probe(final)
    with SessionLocal() as db:
        c = db.get(Clip, clip_id)
        if c:
            c.file_path = str(final)
            c.duration_sec = info.get("duration_sec") or duration
            c.status = "done"
            db.commit()
    shutil.rmtree(work, ignore_errors=True)  # clean work/ after each job
    return final


async def handle_build_clip(job_id: int, params: dict) -> None:
    clip_id = params["clip_id"]
    # Auto-built clips want captions from the source transcript, but a caption
    # failure (no Whisper / no GPU) must not kill the clip - build it uncaptioned.
    if params.get("auto"):
        try:
            await transcribe_source_if_needed(clip_id)
            with SessionLocal() as db:
                clip = db.get(Clip, clip_id)
                if clip:
                    clip.has_captions = True
                    db.commit()
        except Exception as exc:  # noqa: BLE001 - degrade to no captions
            await queue.update(job_id, message=f"Captions skipped: {exc}")
    try:
        await build_clip_file(clip_id, job_id)
    except Exception:
        with SessionLocal() as db:
            clip = db.get(Clip, clip_id)
            if clip:
                clip.status = "failed"
                db.commit()
        raise


async def transcribe_source_if_needed(clip_id: int) -> None:
    with SessionLocal() as db:
        clip = db.get(Clip, clip_id)
        src = db.get(Source, clip.source_id) if clip else None
        need = bool(src and not src.transcript_json)
        source_id = src.id if src else None
    if need and source_id:
        await transcribe_source(source_id)


async def handle_export(job_id: int, params: dict) -> None:
    """Multi-aspect export: re-render per requested aspect ratio."""
    clip_id = params["clip_id"]
    aspects = params.get("aspect_ratios", ["9:16"])
    dims = {"9:16": (1080, 1920), "1:1": (1080, 1080), "16:9": (1920, 1080)}
    for i, aspect in enumerate(aspects):
        w, h = dims.get(aspect, (1080, 1920))
        await queue.update(job_id, progress_pct=100 * i / len(aspects),
                           message=f"Exporting {aspect}")
        await build_clip_file(clip_id, job_id, target_w=w, target_h=h, aspect=aspect)
    await queue.update(job_id, status="done", progress_pct=100, message="Export done")


def register() -> None:
    from ..queue import register_handler
    register_handler("build_clip", handle_build_clip)
    register_handler("export", handle_export)
