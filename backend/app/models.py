"""SQLAlchemy models (SQLite)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def _now() -> datetime:
    return datetime.utcnow()


class Streamer(Base):
    __tablename__ = "streamers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    platform: Mapped[str] = mapped_column(String, default="kick")
    handle: Mapped[str] = mapped_column(String, index=True)
    display_name: Mapped[str] = mapped_column(String, default="")
    is_watched: Mapped[bool] = mapped_column(Boolean, default=False)
    facecam_rect_json: Mapped[str | None] = mapped_column(Text)   # {x,y,w,h}
    gameplay_rect_json: Mapped[str | None] = mapped_column(Text)
    split_ratio: Mapped[float] = mapped_column(Float, default=0.4)  # top height fraction
    default_vertical_mode: Mapped[str] = mapped_column(String, default="facecam_stack")
    default_brandkit_id: Mapped[int | None] = mapped_column(ForeignKey("brandkits.id"))
    default_caption_style_json: Mapped[str | None] = mapped_column(Text)
    context_notes: Mapped[str] = mapped_column(Text, default="")
    auto_record: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_clip_on_end: Mapped[bool] = mapped_column(Boolean, default=False)
    schedule_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Recording(Base):
    __tablename__ = "recordings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    streamer_id: Mapped[int | None] = mapped_column(ForeignKey("streamers.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String, default="recording")  # recording|remuxing|done|failed
    file_path: Mapped[str | None] = mapped_column(Text)   # final remuxed mp4
    segments_json: Mapped[str | None] = mapped_column(Text)
    segment_count: Mapped[int] = mapped_column(Integer, default=0)
    reconnect_count: Mapped[int] = mapped_column(Integer, default=0)
    duration_sec: Mapped[float | None] = mapped_column(Float)
    had_chat: Mapped[bool] = mapped_column(Boolean, default=False)
    chat_log_path: Mapped[str | None] = mapped_column(Text)
    clip_marks_json: Mapped[str | None] = mapped_column(Text)  # [{t, seconds}]
    error: Mapped[str | None] = mapped_column(Text)


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    origin: Mapped[str] = mapped_column(String, default="vod")  # live_recording|vod|clip|upload
    platform: Mapped[str] = mapped_column(String, default="")
    url: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text, default="")
    streamer_id: Mapped[int | None] = mapped_column(ForeignKey("streamers.id"))
    duration_sec: Mapped[float | None] = mapped_column(Float)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    fps: Mapped[float | None] = mapped_column(Float)
    file_path: Mapped[str | None] = mapped_column(Text)
    thumb_path: Mapped[str | None] = mapped_column(Text)
    chat_log_path: Mapped[str | None] = mapped_column(Text)
    transcript_json: Mapped[str | None] = mapped_column(Text)  # cached whisper output
    signals_json: Mapped[str | None] = mapped_column(Text)     # cached signal analysis
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    status: Mapped[str] = mapped_column(String, default="queued")  # queued|downloading|needs_input|done|failed
    error: Mapped[str | None] = mapped_column(Text)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="queued")  # queued|running|done|failed|cancelled|needs_input
    progress_pct: Mapped[float] = mapped_column(Float, default=0.0)
    message: Mapped[str] = mapped_column(Text, default="")
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"))
    clip_id: Mapped[int | None] = mapped_column(ForeignKey("clips.id"))
    params_json: Mapped[str | None] = mapped_column(Text)
    log_path: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


class AiRun(Base):
    __tablename__ = "ai_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    model: Mapped[str] = mapped_column(String, default="")
    n_requested: Mapped[int] = mapped_column(Integer, default=10)
    n_returned: Mapped[int] = mapped_column(Integer, default=0)
    params_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Clip(Base):
    __tablename__ = "clips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    title: Mapped[str] = mapped_column(Text, default="")
    start_sec: Mapped[float] = mapped_column(Float, default=0.0)
    end_sec: Mapped[float] = mapped_column(Float, default=0.0)
    file_path: Mapped[str | None] = mapped_column(Text)
    vertical_mode: Mapped[str] = mapped_column(String, default="facecam_stack")
    vertical_params_json: Mapped[str | None] = mapped_column(Text)
    preset_id: Mapped[int | None] = mapped_column(ForeignKey("presets.id"))
    brandkit_id: Mapped[int | None] = mapped_column(ForeignKey("brandkits.id"))
    has_captions: Mapped[bool] = mapped_column(Boolean, default=False)
    caption_lang: Mapped[str | None] = mapped_column(String)
    transcript_json: Mapped[str | None] = mapped_column(Text)  # editable clip transcript
    duration_sec: Mapped[float | None] = mapped_column(Float)
    virality_score: Mapped[int | None] = mapped_column(Integer)
    virality_tier: Mapped[str | None] = mapped_column(String)   # High|Medium|Low
    virality_reason: Mapped[str | None] = mapped_column(Text)
    signals_json: Mapped[str | None] = mapped_column(Text)      # which signals fired
    hook_text: Mapped[str | None] = mapped_column(Text)
    hook_variants_json: Mapped[str | None] = mapped_column(Text)
    hashtags_json: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str | None] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, default="draft")  # draft|building|done|failed|discarded
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class BrandKit(Base):
    __tablename__ = "brandkits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    logo_path: Mapped[str | None] = mapped_column(Text)
    logo_pos: Mapped[str] = mapped_column(String, default="top_right")
    logo_scale: Mapped[float] = mapped_column(Float, default=0.12)
    font: Mapped[str] = mapped_column(String, default="Rubik")
    primary_color: Mapped[str] = mapped_column(String, default="#142847")
    accent_color: Mapped[str] = mapped_column(String, default="#22d3ee")
    handle_watermark_text: Mapped[str] = mapped_column(String, default="@kicklipsil")
    caption_style_json: Mapped[str | None] = mapped_column(Text)
    intro_path: Mapped[str | None] = mapped_column(Text)
    outro_path: Mapped[str | None] = mapped_column(Text)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)


class Preset(Base):
    __tablename__ = "presets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    vertical_mode: Mapped[str] = mapped_column(String, default="facecam_stack")
    target_w: Mapped[int] = mapped_column(Integer, default=1080)
    target_h: Mapped[int] = mapped_column(Integer, default=1920)
    max_duration_sec: Mapped[int] = mapped_column(Integer, default=60)
    loudnorm_target: Mapped[float] = mapped_column(Float, default=-14.0)
    aspect_ratios_json: Mapped[str] = mapped_column(Text, default='["9:16"]')
    encoder: Mapped[str] = mapped_column(String, default="libx264")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)


class PublishQueueItem(Base):
    __tablename__ = "publish_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    clip_id: Mapped[int] = mapped_column(ForeignKey("clips.id"))
    platform: Mapped[str] = mapped_column(String)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String, default="queued")
    generated_meta_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
