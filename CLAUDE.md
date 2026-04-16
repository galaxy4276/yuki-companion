# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

Yuki Companion is a desktop VTuber coding companion. A transparent, always-on-top Electron overlay renders a VRM avatar on the user's screen. The avatar listens to the user's voice (push-to-talk), runs STT → LLM → TTS round trips, speaks back with lip-sync, and reacts proactively to terminal failures, long idle periods, late-night coding, and Claude Code hook events.

Client (Electron, macOS/Windows) and server (Python FastAPI orchestrator) run on separate machines and communicate over a single WebSocket.

## Remote Backend Access

The Python orchestrator, Gemma 4 LLM, and Qwen3-TTS run on a remote GPU host, not on the Mac dev machine. Connect to the backend host via:

```bash
ssh -p 22022 deveungu@125.242.221.180
```

Server code lives on that host (path referenced in `server/hooks/claude_hook.py`: `/home/deveungu/vtuber-companion/`). The client (`client/` in this repo) talks to it over `http://125.242.221.180:8002` / `ws://125.242.221.180:8002/ws` — those URLs are hardcoded in `client/main.js` and `server/hooks/terminal_hook.sh`.

## Commands

### Client (Electron, run on Mac/Windows)

```bash
cd client
npm install
npm start              # dev run
npm run build:mac      # dist/ .dmg (arm64 + x64)
npm run build:win      # NSIS installer
```

No test runner or linter is configured on the client side.

### Server (Python, run on GPU host via SSH)

```bash
cd server
pip install -r requirements.txt
python main.py         # uvicorn on 0.0.0.0:8002
```

The server lifespan hook (`server/main.py`) runs `init_db`, `load_persona`, `load_whisper`, and spawns the proactive loop. Gemma 4 (via llama.cpp OpenAI-compatible API on `localhost:8001`) and Qwen3-TTS (`localhost:8880`) must already be running on the host — the orchestrator does not spawn them.

### Health check

```bash
curl http://125.242.221.180:8002/health
```

## Architecture

### High-level data flow

```
User voice/text
  ↓ (Electron overlay/chat window)
WebSocket ws://host:8002/ws
  ↓
api/ws_handler.py  ──→  buffers audio chunks, dispatches by message type
  ↓                       ├─ text_message      → orchestrator.handle_message
  ↓                       ├─ audio_chunk       → stt.transcribe → handle_message
  ↓                       ├─ terminal_event    → handle_terminal_event
  ↓                       └─ claude_hook       → handle_claude_hook
core/orchestrator.py
  ├─ persist user turn via db/history.py
  ├─ build system prompt via services/persona.py (+ live core/context.py state)
  ├─ services/llm.py stream_response (Gemma 4, OpenAI-compatible)
  ├─ broadcast text_chunk frames as they arrive
  ├─ persona.classify_emotion → avatar_emotion frame
  └─ services/tts.py synthesize → audio_response frame (base64 wav)
  ↓
broadcast() in ws_handler fans out to every connected socket
  ↓
Electron renderer plays audio, runs lip-sync, updates speech bubble
```

Two parallel ingress paths feed the same orchestrator:
- **WebSocket** (user interaction): `api/ws_handler.py`
- **HTTP hooks** (passive events from terminal/Claude Code): `api/hooks.py`, mounted at `/hooks/terminal` and `/hooks/claude`

### Server module map

- `main.py` — FastAPI app, lifespan startup, `/ws` endpoint, static mount.
- `config.py` — all tunables (LLM/TTS/STT endpoints, proactive thresholds, DB path, persona path). Server-side URLs assume localhost; only the client and the zsh hook hit the public host.
- `core/orchestrator.py` — central fan-in. `handle_message` is the single code path that produces an assistant turn (LLM stream → TTS → emotion). Terminal failures and Claude Stop events synthesize a user-like message and re-enter `handle_message`.
- `core/context.py` — in-memory session state (`cwd`, `last_command`, `last_exit_code`, `claude_task`, `last_activity`). Read by `persona.build_system_prompt` and `proactive` loop. `update()` also stamps `last_activity`, so any event resets the idle timer.
- `core/proactive.py` — background task polling every 300s. Triggers idle nag and night-hour nag via `orchestrator.handle_message(..., event_type="proactive")`, reusing the full LLM→TTS pipeline.
- `services/llm.py` — thin `AsyncOpenAI` wrapper around Gemma 4 (llama.cpp exposes an OpenAI-compatible endpoint). Async generator yielding `(chunk, is_final)`.
- `services/tts.py` — POSTs to Qwen3-TTS OpenAI audio/speech endpoint, returns wav bytes. Failure returns `None` and the orchestrator skips the audio frame silently.
- `services/stt.py` — faster-whisper `medium` model, CUDA int8, Korean-fixed. Synchronous; called via `loop.run_in_executor` from `ws_handler._process_audio`.
- `services/persona.py` — loads `data/personas/default.json`, builds system prompt by interpolating persona fields + live context, and classifies emotion from response text with simple keyword heuristics (drives avatar animation).
- `db/database.py` — single aiosqlite connection (WAL), creates `conversations` and `terminal_events` tables idempotently at boot.
- `db/history.py` — writes user/assistant turns with `event_type` tag (`text` / `voice` / `terminal` / `claude_hook` / `proactive`); `get_recent` returns last N turns for LLM context (reversed to chronological order).
- `hooks/terminal_hook.sh` — zsh `preexec`/`precmd` pair that POSTs every command's exit code + duration to `/hooks/terminal`. Source it from `~/.zshrc`.
- `hooks/claude_hook.py` — stdin-reading Python script registered in `~/.claude/settings.json` hooks. Forwards to `/hooks/claude`; swallows all errors so a down server never blocks Claude Code.

### WebSocket frame contract

Client → server:
- `{type: "text_message", content, session_id}`
- `{type: "audio_chunk", data (base64), is_final, session_id}` — buffered per session until `is_final`
- `{type: "terminal_event", command, exit_code, duration_ms, cwd, session_id}`
- `{type: "claude_hook", hook_type, ...}`

Server → client (broadcast to all sockets):
- `{type: "system_status", llm_ready, tts_ready, stt_ready}` — sent on connect
- `{type: "text_chunk", content, is_final: false, message_id}` — streamed
- `{type: "text_done", message_id, full_content}`
- `{type: "avatar_emotion", emotion, intensity}` — `idle`/`happy`/`worried`/`thinking`/`surprised`
- `{type: "audio_response", data (base64 wav), message_id}`
- `{type: "stt_result", text}` — after voice input

Broadcast is all-or-nothing to every connected socket; dropped sockets are pruned on send failure. There is no per-session routing — messages from one client surface on every connected client.

### Client module map

- `main.js` — Electron main process. Creates two frameless, always-on-top windows: a transparent overlay (click-through except on the character) and a hidden chat panel. Tray icon toggles the chat panel. IPC channels: `set-ignore-mouse`, `move-window`, `show-speech-bubble`, `play-audio`, `toggle-chat`, `get-config`. Server URLs are constants at the top — change them here when the host moves.
- `preload.js` — context bridge only.
- `renderer/overlay.html` — VRM character (Three.js + `@pixiv/three-vrm`), speech bubble, audio playback, lip-sync. Falls back to an emoji avatar if `assets/model.vrm` is missing.
- `renderer/chat.html` — chat panel with text input + push-to-talk, maintains the WebSocket connection.

## Conventions and gotchas

- **All persona-facing text is Korean.** The persona file, emotion keywords, proactive messages, and Whisper language setting all assume Korean. Keep that when editing prompts or adding triggers.
- **Terminal failures re-enter as user messages.** `handle_terminal_event` does not call the LLM directly — on non-zero exit it crafts a Korean user-style message and calls `handle_message`, so the model sees it as if the user said it. Same pattern for Claude `Stop` hooks and proactive triggers. Keep this pattern when adding new passive triggers; don't branch the LLM path.
- **`core.context` is a module-level singleton.** Single-user assumption. Don't add per-session state here without also fixing the proactive loop (which reads the one global `context`).
- **`services/llm.stream_response` yields a trailing `("", True)` sentinel.** The orchestrator relies on the `is_final` flag to send the `text_done` frame. If you swap LLM clients, preserve that contract.
- **TTS is best-effort.** A `None` return just means no audio frame — text still streams. Don't raise from `services/tts.synthesize`.
- **Hardcoded ports.** LLM `:8001`, TTS `:8880`, orchestrator `:8002`. Client and zsh hook both point at `:8002` on the public host; any port change needs edits in `client/main.js`, `server/hooks/terminal_hook.sh`, and `server/config.py`.
- **Hook resilience.** Both terminal and Claude Code hooks swallow network errors — a down server must never break the user's shell or Claude Code session. Preserve this when editing hook scripts.
- **`GEMMA_API_KEY` is checked into `config.py`.** Treat it as a local llama.cpp token, not a secret — but still don't publish it in docs or commit messages.
