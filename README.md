# 🧝‍♀️ Yuki Companion

> AI VTuber coding companion powered by **Gemma 4 26B** — always on top, always by your side.

![License](https://img.shields.io/badge/license-MIT-purple)
![Electron](https://img.shields.io/badge/Electron-41-blue)
![LLM](https://img.shields.io/badge/LLM-Gemma%204%2026B-orange)
![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows-lightgrey)

---

## What is this?

Yuki is a transparent, always-on-top desktop VTuber companion that sits on your screen while you code. She watches your terminal activity, responds to your voice, and proactively checks in when you've been stuck for a while.

Built for developers who code alone and want something alive on their screen.

### Features

- **Transparent overlay** — character floats on screen, clicks pass through empty areas
- **Always on top** — stays above all windows
- **VRM avatar** — supports any VRoid/VRM model, falls back to emoji if none provided
- **Voice chat** — push-to-talk → Whisper STT → Gemma 4 → Qwen3 TTS → lip sync
- **Terminal awareness** — reacts to build failures, long idle time, late-night coding
- **Claude Code hooks** — knows when you finish a coding task
- **Proactive personality** — speaks up on her own, not just when you ask

---

## Architecture

```
┌──────────────────────────────────┐
│  Electron App (macOS / Windows)  │
│  ┌─────────────┐ ┌────────────┐  │
│  │ Transparent │ │ Chat Panel │  │
│  │  Overlay    │ │  (toggle)  │  │
│  │  VRM + TTS  │ │  WS + PTT  │  │
│  └─────────────┘ └────────────┘  │
└────────────┬─────────────────────┘
             │ WebSocket
┌────────────▼─────────────────────┐
│  Orchestrator Server (Python)    │
│  ┌──────────┐  ┌───────────────┐ │
│  │ Gemma 4  │  │  Qwen3-TTS   │ │
│  │ 26B-A4B  │  │  (CPU)       │ │
│  │ (GPU)    │  └───────────────┘ │
│  └──────────┘  ┌───────────────┐ │
│                │ Whisper STT   │ │
│  ┌──────────┐  │ (CUDA int8)   │ │
│  │  SQLite  │  └───────────────┘ │
│  │ history  │                   │
│  └──────────┘                   │
└──────────────────────────────────┘
        ↑
  zsh hooks (terminal events)
  Claude Code hooks
```

---

## Requirements

### Server
- Python 3.12+
- NVIDIA GPU (16GB+ VRAM recommended)
- CUDA 12.x

### Client (this repo)
- Node.js 18+
- macOS or Windows

---

## Quick Start

### 1. Set up the server

```bash
git clone https://github.com/galaxy4276/yuki-companion
cd yuki-companion

pip install -r server/requirements.txt

# Start Gemma 4 (llama.cpp)
./scripts/start-llm.sh

# Start orchestrator
cd server && python main.py
```

### 2. Run the Electron client

```bash
cd client
npm install
npm start
```

### 3. Add a VRM model (optional)

Place any `.vrm` file at `client/assets/model.vrm`.

Free models: [VRoid Hub](https://hub.vroid.com)

---

## Terminal Hook (macOS zsh)

Add to `~/.zshrc` to let Yuki react to your terminal:

```zsh
source /path/to/yuki-companion/server/hooks/terminal_hook.sh
```

## Claude Code Hook

Add to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "python3 /path/to/yuki-companion/server/hooks/claude_hook.py"
      }]
    }]
  }
}
```

---

## Configuration

Edit `client/main.js`:

```js
const SERVER_URL = 'http://your-server-ip:8002'
const WS_URL     = 'ws://your-server-ip:8002/ws'
```

---

## Project Structure

```
yuki-companion/
├── client/                  # Electron app
│   ├── main.js              # Main process (transparent overlay)
│   ├── preload.js           # Context bridge
│   ├── renderer/
│   │   ├── overlay.html     # VRM character window
│   │   └── chat.html        # Chat panel
│   └── hooks/
│       └── terminal_hook.sh # zsh activity hook
│
└── server/                  # Python orchestrator
    ├── main.py
    ├── config.py
    ├── core/
    │   ├── orchestrator.py  # Event routing
    │   ├── context.py       # Session state
    │   └── proactive.py     # Proactive speech triggers
    ├── services/
    │   ├── llm.py           # Gemma 4 client
    │   ├── tts.py           # Qwen3-TTS client
    │   └── stt.py           # Whisper STT
    ├── db/
    │   ├── database.py
    │   └── history.py
    ├── api/
    │   ├── ws_handler.py    # WebSocket handler
    │   └── hooks.py         # Terminal / Claude Code hooks
    └── hooks/
        └── claude_hook.py   # Claude Code Stop hook
```

---

## License

MIT © [galaxy4276](https://github.com/galaxy4276)
