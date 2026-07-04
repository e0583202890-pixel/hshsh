"""Vertical conversion filter graphs (1080x1920 by default).

Modes: facecam_stack (primary), blur_fill, auto_reframe, center_crop, letterbox.
All produce yuv420p; encoder chosen by preset (libx264 or h264_nvenc).
"""
from __future__ import annotations

from ..config import settings


def encoder_args(encoder: str) -> list[str]:
    if encoder == "h264_nvenc":
        return ["-c:v", "h264_nvenc", "-preset", "p5", "-cq", "19"]
    return ["-c:v", "libx264", "-preset", "medium", "-crf", "18"]


def facecam_stack_filter(facecam: dict, gameplay: dict, split_ratio: float = 0.4,
                         w: int = 1080, h: int = 1920) -> str:
    """Facecam on top, gameplay on bottom (PRIMARY mode)."""
    top_h = int(h * split_ratio) // 2 * 2
    bot_h = h - top_h
    fx, fy, fw, fh = facecam["x"], facecam["y"], facecam["w"], facecam["h"]
    gx, gy, gw, gh = gameplay["x"], gameplay["y"], gameplay["w"], gameplay["h"]
    return (
        f"[0:v]crop={fw}:{fh}:{fx}:{fy},"
        f"scale={w}:{top_h}:force_original_aspect_ratio=increase,crop={w}:{top_h}[top];"
        f"[0:v]crop={gw}:{gh}:{gx}:{gy},"
        f"scale={w}:{bot_h}:force_original_aspect_ratio=increase,crop={w}:{bot_h}[bot];"
        f"[top][bot]vstack,format=yuv420p[v]")


def blur_fill_filter(w: int = 1080, h: int = 1920) -> str:
    """Centered full-width video over a zoomed heavily-blurred background."""
    return (
        f"[0:v]split=2[bg][fg];"
        f"[bg]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
        f"gblur=sigma=25[bgb];"
        f"[fg]scale={w}:-2[fgs];"
        f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2,format=yuv420p[v]")


def center_crop_filter(offset_x: int | str = "(iw-ih*9/16)/2",
                       w: int = 1080, h: int = 1920) -> str:
    return (f"[0:v]crop=ih*9/16:ih:{offset_x}:0,scale={w}:{h},format=yuv420p[v]")


def letterbox_filter(primary_color: str = "#142847", w: int = 1080, h: int = 1920) -> str:
    """Video on a solid brand-navy canvas (logo/title overlaid by branding step)."""
    color = primary_color.lstrip("#")
    return (
        f"[0:v]scale={w}:-2[fg];"
        f"color=c=0x{color}:s={w}x{h}:d=1[bg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2:shortest=1,format=yuv420p[v]")


def aspect_filter(aspect: str, w_base: int = 1080) -> tuple[int, int]:
    """Target dimensions for a requested aspect ratio."""
    table = {"9:16": (1080, 1920), "1:1": (1080, 1080), "16:9": (1920, 1080)}
    return table.get(aspect, (1080, 1920))


def build_vertical_filter(mode: str, params: dict, w: int = 1080, h: int = 1920) -> str:
    if mode == "facecam_stack":
        return facecam_stack_filter(params["facecam_rect"], params["gameplay_rect"],
                                    float(params.get("split_ratio", 0.4)), w, h)
    if mode == "blur_fill":
        return blur_fill_filter(w, h)
    if mode == "center_crop":
        return center_crop_filter(params.get("offset_x", "(iw-ih*9/16)/2"), w, h)
    if mode == "letterbox":
        return letterbox_filter(params.get("primary_color", "#142847"), w, h)
    raise ValueError(f"Unknown vertical mode '{mode}'")
