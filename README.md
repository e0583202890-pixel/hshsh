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

## Install & run (Windows) — the easy way

**Double-click `start.bat`.** That's it.

On the first run it installs everything and builds the app (a few minutes), then
every run after that starts in seconds and **opens your browser automatically** at:

- **http://127.0.0.1:8123**  (one address — the backend serves the UI and the API)

Keep the black window open while you use the app; close it to stop. If Python or
Node.js is missing, `start.bat` tells you exactly what to install and where.

### Developer alternative (hot-reload)

```powershell
powershell -ExecutionPolicy Bypass -File run.ps1
```

`run.ps1` runs the backend (http://127.0.0.1:8123) plus the Vite dev server with
hot-reload (http://127.0.0.1:5173).

### Your AI key

Put your AI key in `.env` (never echoed to the UI). `start.bat` creates `.env` and
opens it in Notepad on the first run. Set **either**:

- `OPENROUTER_API_KEY` (+ optional `OPENROUTER_MODEL`) — one key, many models. The
  default `deepseek/deepseek-chat` (DeepSeek V3) is a **cheap** pick (~40-50x
  cheaper than Claude, good JSON, decent Hebrew). Other cheap options:
  `qwen/qwen-2.5-72b-instruct`, `z-ai/glm-4.5-air`, `deepseek/deepseek-r1`, or a
  free `:free` slug. Bump to `anthropic/claude-3.5-sonnet` / `openai/gpt-4o` only
  if Hebrew titles come out weak. If both keys are set, OpenRouter wins.
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
