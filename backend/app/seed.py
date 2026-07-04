"""First-run seeding: 3 presets + the KICKLIPS brand kit."""
from __future__ import annotations

import json

from .db import SessionLocal
from .models import BrandKit, Preset

DEFAULT_CAPTION_STYLE = {
    "font": "Rubik", "font_size": 84, "animation": "pop",
    "margin_v_pct": 0.30, "outline": 5,
}


def seed() -> None:
    with SessionLocal() as db:
        if db.query(Preset).count() == 0:
            db.add_all([
                Preset(name="YouTube Shorts", target_w=1080, target_h=1920,
                       max_duration_sec=60, loudnorm_target=-14.0,
                       aspect_ratios_json='["9:16"]', is_default=True),
                Preset(name="TikTok", target_w=1080, target_h=1920,
                       max_duration_sec=180, loudnorm_target=-14.0,
                       aspect_ratios_json='["9:16"]'),
                Preset(name="Instagram Reels", target_w=1080, target_h=1920,
                       max_duration_sec=90, loudnorm_target=-14.0,
                       aspect_ratios_json='["9:16"]'),
            ])
        if db.query(BrandKit).count() == 0:
            db.add(BrandKit(name="KICKLIPS", logo_pos="top_right", logo_scale=0.12,
                            font="Rubik", primary_color="#142847",
                            accent_color="#22d3ee",
                            handle_watermark_text="@kicklipsil",
                            caption_style_json=json.dumps(DEFAULT_CAPTION_STYLE),
                            is_default=True))
        db.commit()
