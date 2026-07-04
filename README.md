# KICKLIPS Studio

A local, single-user, browser-based production system for an Israeli clips channel
(`@kicklipsil`) that clips **Kick.com** streamers into vertical Shorts for
YouTube / TikTok / Reels.

Three top-level workflows:

1. **Live & Auto-Record** — a watchlist of streamers; record live broadcasts
   (manually or automatically on go-live), with segmented crash-safe recording,
   reconnect-on-drop, disk guard, live chat capture, and optional auto-run of the
   AI clip pipeline when the stream ends.
2. **AI Auto-Clip** — paste a VOD (or use a recording) → Whisper transcription →
   Claude highlight selection + virality scoring, fused with audio-hype /
   chat-spike / scene-change / face-reaction signals → auto-built vertical,
   captioned, branded clips in a review grid.
3. **Manual Editor** — trim, vertical modes (facecam-top/gameplay-bottom,
   blur-fill, face-aware auto-reframe, center crop, brand letterbox), editable
   Hebrew/English word-level animated captions, brand kits, audio, effects,
   multi-aspect export.

## Honest scope

- **Live recording of Kick is reliable**: Streamlink (with `cloudscraper`) records
  live channels to segmented files; auto-record polls the channel's live status and
  starts/stops recording automatically. This is a stable, well-worn pattern.
- **The reliable 80%** is all here and local: capture (live + VOD), Whisper
  transcription, LLM highlight selection + virality scoring, facecam-top/
  gameplay-bottom + face-aware auto-reframe, animated captions, branding, audio,
  multi-aspect export, metadata generation.
- **The hard 20%** — game-specific kill-feed detection (reading each game's HUD) —
  needs per-game computer vision and is fragile. The default highlight baseline is
  audio-hype + chat-spike + scene-change + face-reaction. Kill-feed OCR exists as an
  **optional, clearly-labelled experimental** module (`killfeed_ocr.py`, off by
  default, FPS-only, may miss or mis-fire).

## Prerequisites

- **Python 3.11+** (on PATH)
- **Node.js 18+** (on PATH)
- **ffmpeg + ffprobe** (on PATH, or set `FFMPEG_PATH`/`FFPROBE_PATH` in `.env`)
- **streamlink** with its Kick plugin dependencies (installed by
  `requirements.txt`; the Kick plugin needs `cloudscraper` for Cloudflare)
- Optional: **NVIDIA CUDA** (RTX GPU) for fast Whisper + NVENC encoding
- Optional: **tesseract** for the experimental kill-feed OCR

## Install & run (Windows)

```powershell
powershell -ExecutionPolicy Bypass -File run.ps1
```

`run.ps1` creates a Python venv, installs backend + frontend dependencies on
first run, copies `.env.example` to `.env` if missing, then starts:

- Backend (FastAPI): http://127.0.0.1:8123
- Frontend (Vite dev): http://127.0.0.1:5173

Put your AI key in `.env` (never echoed to the UI). Two options — set **either**:

- `OPENROUTER_API_KEY` (+ optional `OPENROUTER_MODEL`, default
  `anthropic/claude-3.5-sonnet`) — one key, routes to Claude/GPT/others. If both
  keys are set, OpenRouter wins.
- `ANTHROPIC_API_KEY` (+ optional `ANTHROPIC_MODEL`) — Anthropic native.

The active provider + model is shown on the Settings page and in the health row.

For a production-style single-server run, build the frontend once
(`cd frontend && npm run build`) — the backend then serves the built app itself
at http://127.0.0.1:8123.

## Kick download notes (Cloudflare)

Kick VOD downloads use a cascade: `yt-dlp --impersonate chrome` (via `curl_cffi`) →
browser cookies (`firefox`/`chrome`/`edge`) → referer + UA → yt-dlp nightly →
**manual m3u8 fallback**. If everything is blocked, the source card asks you to
paste the `master.m3u8` URL (open the VOD, F12 → Network, filter "m3u8") — never a
dead end. Having Firefox or Chrome logged in to kick.com helps the cookie steps.

## Accessibility

The operator has protanomaly (red-green color weakness). The UI never encodes
meaning by red/green alone: **every status is an icon + a text label**, the palette
is blue/amber/slate/gray, and the virality score is always number + filled bar +
tier label + icon.

## Layout

```
backend/app/       FastAPI app: routers, services (recorder, live_monitor,
                   chat_capture, downloader, ai_clipper, signals, vertical,
                   reframe, captions, branding, audio, effects, montage,
                   export, thumbs, metadata_ai, killfeed_ocr, profiles)
frontend/src/      React + Vite + TS + Tailwind, Hebrew RTL default + EN toggle
data/              kicklips.db, recordings/, downloads/, work/, output/, assets/
run.ps1            one-command launcher
```

## Fonts for Hebrew captions

Drop `Rubik.ttf` (or another Hebrew-glyph font, e.g. Noto Sans Hebrew) into
`data/assets/fonts/` — burned-in captions use this fontsdir. Hebrew caption lines
are prefixed with RLM (U+200F) so libass renders RTL correctly. The branding text
overlays (hook, `@kicklipsil` watermark, lower-third) use ffmpeg's `drawtext`,
which the standard Windows ffmpeg builds include. If a machine's ffmpeg lacks
`drawtext` or a usable font, the render **degrades gracefully** — you still get the
vertical, captioned clip, just without the text overlays (a warning appears in the
job message) rather than a failed render.

## Editor keyboard shortcuts

`Space` play/pause · `I` / `O` mark in / out · `J` / `L` seek −5s / +5s.

## Nice extras beyond the base spec

- **Live "clip last 60s" marks become draft clips** on the recording's source when
  the stream ends — they're waiting in the Library/Editor, not just noted.
- **Signals panel** on the Auto-Clip page: compute audio-hype / chat-spike /
  scene-change / face-reaction windows and one-click "create clip here (±15s) →
  editor" for any of them.
- **One-click Auto-Clip from a URL**: pasting a VOD URL downloads it and then
  auto-runs the AI pipeline in one go (chained jobs).
- **Graceful degradation everywhere**: caption failure never kills an auto-build;
  branding/font failure falls back to a captioned clip; a missing `ffprobe` is
  tolerated. A clip always renders.

## All code / logs / filenames are English-only

Downloaded and recorded filenames are slugified to ASCII, and all console output
is English (the operator's Windows console mis-renders Hebrew RTL). The app UI
itself is Hebrew-first with an English toggle.
