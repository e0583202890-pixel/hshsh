"""Pydantic schemas for the REST API."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Rect(BaseModel):
    x: int
    y: int
    w: int
    h: int


# ---- streamers ----
class StreamerIn(BaseModel):
    platform: str = "kick"
    handle: str
    display_name: str = ""
    is_watched: bool = True
    context_notes: str = ""
    auto_record: bool = False
    auto_clip_on_end: bool = False
    default_vertical_mode: str = "facecam_stack"
    default_brandkit_id: Optional[int] = None


class StreamerLayoutIn(BaseModel):
    facecam_rect: Optional[Rect] = None
    gameplay_rect: Optional[Rect] = None
    split_ratio: Optional[float] = None


class StreamerOut(ORM):
    id: int
    platform: str
    handle: str
    display_name: str
    is_watched: bool
    facecam_rect_json: Optional[str]
    gameplay_rect_json: Optional[str]
    split_ratio: float
    default_vertical_mode: str
    default_brandkit_id: Optional[int]
    context_notes: str
    auto_record: bool
    auto_clip_on_end: bool


# ---- recordings ----
class RecordingStartIn(BaseModel):
    streamer_id: Optional[int] = None
    url: Optional[str] = None


class ClipLastIn(BaseModel):
    seconds: int = 60


class RecordingOut(ORM):
    id: int
    streamer_id: Optional[int]
    started_at: datetime
    ended_at: Optional[datetime]
    status: str
    file_path: Optional[str]
    segment_count: int
    reconnect_count: int
    duration_sec: Optional[float]
    had_chat: bool
    error: Optional[str]


# ---- sources ----
class DownloadIn(BaseModel):
    urls: list[str]
    quality: str = "best"
    section: Optional[str] = None  # "HH:MM:SS-HH:MM:SS"


class ManualM3u8In(BaseModel):
    m3u8_url: str


class SourceOut(ORM):
    id: int
    origin: str
    platform: str
    url: Optional[str]
    title: str
    streamer_id: Optional[int]
    duration_sec: Optional[float]
    width: Optional[int]
    height: Optional[int]
    fps: Optional[float]
    file_path: Optional[str]
    thumb_path: Optional[str]
    chat_log_path: Optional[str]
    created_at: datetime
    status: str
    error: Optional[str]


# ---- autoclip / clips ----
class AutoClipIn(BaseModel):
    source_id: Optional[int] = None
    url: Optional[str] = None
    n: int = 10
    brandkit_id: Optional[int] = None
    preset_id: Optional[int] = None
    exclusions: list[str] = []


class ClipIn(BaseModel):
    source_id: int
    title: str = ""
    start_sec: float
    end_sec: float
    vertical_mode: Optional[str] = None
    preset_id: Optional[int] = None
    brandkit_id: Optional[int] = None


class VerticalIn(BaseModel):
    mode: str  # facecam_stack|blur_fill|auto_reframe|center_crop|letterbox
    params: dict[str, Any] = {}


class CaptionsIn(BaseModel):
    lang: Optional[str] = None  # None = auto
    style: dict[str, Any] = {}
    burn: bool = True


class TranscriptPatchIn(BaseModel):
    segments: list[dict[str, Any]]


class BrandIn(BaseModel):
    brandkit_id: Optional[int] = None
    hook_text: Optional[str] = None
    lower_third: bool = False
    progress_bar: bool = False
    intro_outro: bool = False


class AudioIn(BaseModel):
    loudnorm: bool = True
    music_path: Optional[str] = None
    music_volume: float = 0.3
    ducking: bool = True
    remove_silence: bool = False


class EffectsIn(BaseModel):
    punch_in: bool = False
    intensity: float = 0.15
    facecam_zoom_on_reaction: bool = False


class ExportIn(BaseModel):
    preset_id: Optional[int] = None
    aspect_ratios: list[str] = ["9:16"]


class ClipOut(ORM):
    id: int
    source_id: int
    title: str
    start_sec: float
    end_sec: float
    file_path: Optional[str]
    vertical_mode: str
    preset_id: Optional[int]
    brandkit_id: Optional[int]
    has_captions: bool
    caption_lang: Optional[str]
    duration_sec: Optional[float]
    virality_score: Optional[int]
    virality_tier: Optional[str]
    virality_reason: Optional[str]
    signals_json: Optional[str]
    hook_text: Optional[str]
    hook_variants_json: Optional[str]
    hashtags_json: Optional[str]
    status: str
    created_at: datetime


# ---- jobs ----
class JobOut(ORM):
    id: int
    type: str
    status: str
    progress_pct: float
    message: str
    source_id: Optional[int]
    clip_id: Optional[int]
    error: Optional[str]
    created_at: datetime


# ---- brand kits / presets ----
class BrandKitIn(BaseModel):
    name: str
    logo_path: Optional[str] = None
    logo_pos: str = "top_right"
    logo_scale: float = 0.12
    font: str = "Rubik"
    primary_color: str = "#142847"
    accent_color: str = "#22d3ee"
    handle_watermark_text: str = "@kicklipsil"
    caption_style_json: Optional[str] = None
    intro_path: Optional[str] = None
    outro_path: Optional[str] = None
    is_default: bool = False


class BrandKitOut(ORM, BrandKitIn):
    id: int


class PresetIn(BaseModel):
    name: str
    vertical_mode: str = "facecam_stack"
    target_w: int = 1080
    target_h: int = 1920
    max_duration_sec: int = 60
    loudnorm_target: float = -14.0
    aspect_ratios_json: str = '["9:16"]'
    encoder: str = "libx264"
    is_default: bool = False


class PresetOut(ORM, PresetIn):
    id: int


# ---- publish ----
class MetadataIn(BaseModel):
    clip_id: int
    platform: str  # youtube|tiktok|reels


class ScheduleIn(BaseModel):
    clip_id: int
    platform: str
    scheduled_at: Optional[datetime] = None


# ---- montage ----
class MontageIn(BaseModel):
    clip_ids: list[int]
    music_path: Optional[str] = None
    beat_sync: bool = False
    transitions: bool = True
