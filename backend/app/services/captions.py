"""Animated word-level ASS captions with correct Hebrew RTL rendering.

Hebrew lines get an RLM (U+200F) prefix so libass orders them correctly.
Style comes from the brand kit's caption_style_json; safe-zone placement
keeps text clear of the platform bottom UI.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..config import ASSETS_DIR

RLM = "‏"
_HEBREW_RE = re.compile(r"[֐-׿]")

DEFAULT_STYLE = {
    "font": "Rubik",
    "font_size": 84,
    "primary_color": "&H00FFFFFF",   # white
    "highlight_color": "&H00EED322", # cyan-ish accent (BGR) - not red/green
    "outline_color": "&H00000000",
    "outline": 5,
    "shadow": 2,
    "margin_v_pct": 0.30,            # from bottom -> ~70% height, above Shorts UI
    "animation": "pop",              # pop|karaoke|none
    "keywords": [],                   # emphasized words
}


def is_hebrew(text: str) -> bool:
    return bool(_HEBREW_RE.search(text))


def _ass_time(t: float) -> str:
    t = max(0.0, t)
    h = int(t // 3600)
    m = int(t % 3600 // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _header(style: dict, play_w: int = 1080, play_h: int = 1920) -> str:
    margin_v = int(play_h * style["margin_v_pct"])
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {play_w}
PlayResY: {play_h}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{style['font']},{style['font_size']},{style['primary_color']},{style['highlight_color']},{style['outline_color']},&H96000000,-1,0,0,0,100,100,0,0,1,{style['outline']},{style['shadow']},2,60,60,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _group_words(words: list[dict], max_words: int = 4, max_gap: float = 0.8) -> list[list[dict]]:
    groups: list[list[dict]] = []
    cur: list[dict] = []
    for w in words:
        if cur and (len(cur) >= max_words or w["start"] - cur[-1]["end"] > max_gap):
            groups.append(cur)
            cur = []
        cur.append(w)
    if cur:
        groups.append(cur)
    return groups


def _escape(text: str) -> str:
    return text.replace("{", "(").replace("}", ")").replace("\n", " ")


def build_ass(transcript: dict, style_overrides: dict | None = None,
              play_w: int = 1080, play_h: int = 1920) -> str:
    """Word-level animated captions. Hebrew groups rendered RTL with RLM."""
    style = {**DEFAULT_STYLE, **(style_overrides or {})}
    keywords = {k.lower() for k in style.get("keywords", [])}
    lines = [_header(style, play_w, play_h)]
    for seg in transcript.get("segments", []):
        words = seg.get("words") or []
        if not words:
            words = [{"w": seg["text"], "start": seg["start"], "end": seg["end"]}]
        rtl = is_hebrew(seg.get("text", ""))
        for group in _group_words(words):
            g_start, g_end = group[0]["start"], group[-1]["end"]
            if style["animation"] == "karaoke":
                parts = []
                for w in group:
                    dur_cs = max(1, int((w["end"] - w["start"]) * 100))
                    token = _escape(w["w"].strip())
                    if token.lower().strip(".,!?") in keywords:
                        token = r"{\c" + style["highlight_color"] + "}" + token + r"{\c" + style["primary_color"] + "}"
                    parts.append(rf"{{\k{dur_cs}}}{token}")
                text = " ".join(parts)
                if rtl:
                    text = RLM + text
                lines.append(f"Dialogue: 0,{_ass_time(g_start)},{_ass_time(g_end)},Cap,,0,0,0,,{text}")
            else:  # pop: each word appears with a quick scale-in, group stays on screen
                for i, w in enumerate(group):
                    shown = [x["w"].strip() for x in group[:i + 1]]
                    text = _escape(" ".join(shown))
                    if rtl:
                        text = RLM + text
                    anim = r"{\fscx80\fscy80\t(0,90,\fscx100\fscy100)}" if style["animation"] == "pop" else ""
                    w_end = group[i + 1]["start"] if i + 1 < len(group) else g_end
                    lines.append(f"Dialogue: 0,{_ass_time(w['start'])},{_ass_time(w_end)},Cap,,0,0,0,,{anim}{text}")
    return "\n".join(lines) + "\n"


def write_ass(transcript: dict, out_path: Path, style_overrides: dict | None = None) -> Path:
    out_path.write_text(build_ass(transcript, style_overrides), encoding="utf-8")
    return out_path


def burn_args(ass_path: Path) -> str:
    """ffmpeg -vf value for burning the ASS file with the bundled fonts dir."""
    fonts = (ASSETS_DIR / "fonts").as_posix()
    return f"ass={ass_path.as_posix()}:fontsdir={fonts}"


def profanity_spans(transcript: dict, words_list: list[str]) -> list[tuple[float, float]]:
    """Time spans of profane words for optional auto-bleep/mute."""
    bad = {w.lower() for w in words_list}
    spans = []
    for seg in transcript.get("segments", []):
        for w in seg.get("words", []):
            if w["w"].strip().lower().strip(".,!?") in bad:
                spans.append((w["start"], w["end"]))
    return spans


def clip_transcript(source_transcript: dict, start: float, end: float) -> dict:
    """Slice + re-zero a source transcript to a clip's window."""
    segments = []
    for seg in source_transcript.get("segments", []):
        if seg["end"] < start or seg["start"] > end:
            continue
        words = [{"w": w["w"], "start": max(0.0, w["start"] - start),
                  "end": max(0.0, w["end"] - start)}
                 for w in seg.get("words", []) if start <= w["start"] <= end]
        segments.append({"start": max(0.0, seg["start"] - start),
                         "end": min(end, seg["end"]) - start,
                         "text": seg["text"], "words": words})
    return {"language": source_transcript.get("language"), "segments": segments}
