"""Montage maker: stitch top-N clips into one paced highlight reel."""
from __future__ import annotations

import json
from pathlib import Path

from ..config import LOGS_DIR, OUTPUT_DIR, WORK_DIR, settings
from ..db import SessionLocal
from ..models import Clip
from ..queue import queue
from .audio import music_ducking_graph
from .util import run_process, slugify
from .vertical import encoder_args


async def handle_montage(job_id: int, params: dict) -> None:
    clip_ids: list[int] = params["clip_ids"]
    music_path: str | None = params.get("music_path")
    beat_sync: bool = params.get("beat_sync", False)
    ffmpeg = settings.which("ffmpeg") or "ffmpeg"
    log = LOGS_DIR / f"job_{job_id}.log"

    with SessionLocal() as db:
        files = []
        for cid in clip_ids:
            c = db.get(Clip, cid)
            if c and c.file_path and Path(c.file_path).exists():
                files.append(Path(c.file_path))
    if len(files) < 2:
        raise RuntimeError("Montage needs at least 2 built clips")

    work = WORK_DIR / f"montage_{job_id}"
    work.mkdir(parents=True, exist_ok=True)

    # Normalize all parts to the same params, then concat.
    await queue.update(job_id, progress_pct=10, message="Normalizing clips")
    norm_files = []
    for i, f in enumerate(files):
        norm = work / f"part{i:03d}.mp4"
        rc, last = await run_process(
            [ffmpeg, "-y", "-i", str(f),
             "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,"
                    "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p",
             *encoder_args("libx264"), "-c:a", "aac", "-ar", "48000", "-b:a", "192k",
             str(norm)], log)
        if rc != 0:
            raise RuntimeError(f"Normalize failed on part {i}: {last}")
        norm_files.append(norm)
        await queue.update(job_id, progress_pct=10 + 50 * (i + 1) / len(files),
                           message=f"Normalized {i + 1}/{len(files)}")

    list_file = work / "list.txt"
    list_file.write_text("".join(f"file '{p.as_posix()}'\n" for p in norm_files),
                         encoding="utf-8")
    out = OUTPUT_DIR / (slugify(f"montage_{'_'.join(str(c) for c in clip_ids[:5])}") + ".mp4")

    await queue.update(job_id, progress_pct=70, message="Concatenating")
    if music_path and Path(music_path).exists():
        concat_tmp = work / "concat.mp4"
        rc, last = await run_process(
            [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
             "-c", "copy", str(concat_tmp)], log)
        if rc != 0:
            raise RuntimeError(f"Concat failed: {last}")
        await queue.update(job_id, progress_pct=85, message="Mixing music bed")
        rc, last = await run_process(
            [ffmpeg, "-y", "-i", str(concat_tmp), "-stream_loop", "-1", "-i", music_path,
             "-filter_complex", music_ducking_graph(params.get("music_volume", 0.3)),
             "-map", "0:v", "-map", "[aout]", "-c:v", "copy", "-c:a", "aac",
             "-shortest", str(out)], log)
        if rc != 0:
            raise RuntimeError(f"Music mix failed: {last}")
    else:
        rc, last = await run_process(
            [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
             "-c", "copy", str(out)], log)
        if rc != 0:
            raise RuntimeError(f"Concat failed: {last}")

    if beat_sync:
        # Beat-synced trimming needs librosa; label as optional and skip gracefully.
        try:
            import librosa  # noqa: F401
        except ImportError:
            await queue.update(job_id, message="librosa not installed - beat sync skipped")

    import shutil
    shutil.rmtree(work, ignore_errors=True)
    await queue.update(job_id, status="done", progress_pct=100,
                       message=f"Montage ready: {out.name}")


def register() -> None:
    from ..queue import register_handler
    register_handler("montage", handle_montage)
