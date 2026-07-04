"""Brand kit application: logo watermark, @handle watermark, hook text,
lower-third, progress bar, intro/outro concat."""
from __future__ import annotations

import json
from pathlib import Path

from ..config import ASSETS_DIR
from ..db import SessionLocal
from ..models import BrandKit, Streamer


def get_kit(brandkit_id: int | None) -> BrandKit | None:
    with SessionLocal() as db:
        if brandkit_id:
            return db.get(BrandKit, brandkit_id)
        return db.query(BrandKit).filter(BrandKit.is_default.is_(True)).first()


def _font_path(font: str) -> str:
    p = ASSETS_DIR / "fonts" / f"{font}.ttf"
    return p.as_posix() if p.exists() else ""


def _drawtext(text: str, font: str, size: int, color: str, x: str, y: str,
              alpha: float = 1.0, enable: str | None = None) -> str:
    text = text.replace("\\", "").replace("'", "’").replace(":", r"\:")
    fontfile = _font_path(font)
    font_part = f"fontfile='{fontfile}':" if fontfile else f"font='{font}':"
    parts = (f"drawtext={font_part}text='{text}':fontsize={size}"
             f":fontcolor={color}@{alpha}:borderw=4:bordercolor=black@0.8:x={x}:y={y}")
    if enable:
        parts += f":enable='{enable}'"
    return parts


def logo_pos_expr(pos: str) -> str:
    return {"top_right": "W-w-30:30", "top_left": "30:30",
            "bottom_right": "W-w-30:H-h-30", "bottom_left": "30:H-h-30"}.get(pos, "W-w-30:30")


def build_brand_filters(kit: BrandKit, *, hook_text: str | None = None,
                        lower_third_name: str | None = None,
                        progress_bar: bool = False,
                        duration: float | None = None,
                        w: int = 1080, h: int = 1920) -> tuple[list[str], list[str]]:
    """Returns (extra_inputs, filter_chain_steps) to append after [v]."""
    inputs: list[str] = []
    steps: list[str] = []
    label = "v"
    idx = 1  # input 0 is the clip

    if kit.logo_path and Path(kit.logo_path).exists():
        inputs += ["-i", kit.logo_path]
        logo_w = int(w * kit.logo_scale)
        steps.append(f"[{idx}:v]scale={logo_w}:-1[wm]")
        steps.append(f"[{label}][wm]overlay={logo_pos_expr(kit.logo_pos)}[b{idx}]")
        label = f"b{idx}"
        idx += 1

    if kit.handle_watermark_text:
        steps.append(f"[{label}]{_drawtext(kit.handle_watermark_text, kit.font, 36, 'white', '(w-text_w)/2', 'h-160', alpha=0.55)}[hw]")
        label = "hw"

    if hook_text:
        # Hook overlay for the first ~1.8 seconds.
        steps.append(f"[{label}]{_drawtext(hook_text, kit.font, 76, 'white', '(w-text_w)/2', 'h*0.16', enable='between(t,0,1.8)')}[hk]")
        label = "hk"

    if lower_third_name:
        steps.append(f"[{label}]{_drawtext(lower_third_name, kit.font, 44, 'white', '60', 'h-320', alpha=0.9)}[lt]")
        label = "lt"

    if progress_bar and duration:
        color = kit.accent_color.lstrip("#")
        steps.append(f"color=c=0x{color}:s={w}x12[pbsrc]")
        steps.append(f"[pbsrc]crop=w='max(2,{w}*t/{duration:.2f})':h=12:x=0:y=0[pb]")
        steps.append(f"[{label}][pb]overlay=0:0:shortest=1[pbv]")
        label = "pbv"

    steps.append(f"[{label}]format=yuv420p[vout]")
    return inputs, steps


def lower_third_for_clip(clip_streamer_id: int | None) -> str | None:
    if not clip_streamer_id:
        return None
    with SessionLocal() as db:
        s = db.get(Streamer, clip_streamer_id)
        if s:
            return f"{s.display_name or s.handle} | kick.com/{s.handle}"
    return None


def caption_style_from_kit(kit: BrandKit | None) -> dict:
    if kit and kit.caption_style_json:
        try:
            style = json.loads(kit.caption_style_json)
            style.setdefault("font", kit.font)
            return style
        except json.JSONDecodeError:
            pass
    return {"font": kit.font} if kit else {}
