import os

# Gemma 4
GEMMA_BASE_URL = "http://localhost:8001/v1"
GEMMA_API_KEY  = "w7PhLd603vZQ8Om-Ys7wHeK6CZyzK4ngp1lwsYh2oyQ"
GEMMA_MODEL    = "gemma-4"
GEMMA_MAX_TOKENS = 200  # 1-2문장 답변 유도 (v2 persona 기준)
MCP_TOOL_RESULT_MAX_CHARS = 4000  # LLM에 다시 보낼 때 truncate

# LTM 주입 cap — prefill 증가 억제
RECENT_MEMORY_MAX_CHARS = 600
EPISODE_MAX_CHARS = 300

# TTS
TTS_PROVIDER = os.environ.get("TTS_PROVIDER", "qwen")  # qwen | elevenlabs

# Qwen3-TTS (provider=qwen)
TTS_URL = "http://localhost:8880"
TTS_USERNAME = os.environ.get("TTS_USERNAME", "tts")
TTS_PASSWORD = os.environ.get("TTS_PASSWORD", "SmartNewbie!0705")
TTS_VOICE = os.environ.get("TTS_VOICE", "Ono_Anna")  # Sohee는 EOS 미도달로 무한 generation

# ElevenLabs (provider=elevenlabs)
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "sk_ea17cd9711839459d5e030ffa2900669b4a63da94df1143f")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "Lb7qkOn5hF8p7qfCDH8q")  # Annie — friendly/soft/cute Korean female
ELEVENLABS_MODEL_ID = os.environ.get("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")

# STT
WHISPER_MODEL  = "medium"
WHISPER_DEVICE = "cuda"
WHISPER_COMPUTE = "int8"

# Server
HOST = "0.0.0.0"
PORT = 8002

# DB
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "companion.db")

# Yuki data roots (persona v2 + LTM)
YUKI_DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "yuki")
YUKI_MEMORY_DIR = os.path.join(YUKI_DATA_DIR, "memory")
YUKI_WIKI_DIR = os.path.join(YUKI_DATA_DIR, "wiki")
YUKI_RAW_DIR = os.path.join(YUKI_DATA_DIR, "raw")

# Persona — v2 MD (frontmatter). data/personas/default.json 는 deprecated fallback.
PERSONA_PATH = os.path.join(YUKI_DATA_DIR, "persona", "default.md")

# Proactive triggers
IDLE_TRIGGER_MINUTES  = 30
NIGHT_HOUR_START      = 1
NIGHT_HOUR_END        = 5
REPEAT_CMD_THRESHOLD  = 3
NIGHT_TRIGGER_COOLDOWN_HOURS = 8

CLAUDE_POSTTOOL_DEBOUNCE_SECONDS = 5
CLAUDE_POSTTOOL_TOOLS = {"Edit", "Write", "MultiEdit"}

REPEAT_FAIL_THRESHOLD = 3
RECENT_CMD_RING_SIZE = 10

HISTORY_ROLLING_TURNS = 8
HISTORY_SUMMARY_ON_OVERFLOW = 10

PROACTIVE_TEMPLATES_PATH = os.path.join(os.path.dirname(__file__), "data", "proactive_templates.json")

SCREENSHOT_TTL_SECONDS = 300
VISION_MODEL_CAPABLE = False
OCR_LANGUAGES = "kor+eng"

# sometime-central MCP는 이미 macmini.tail6899df.ts.net(Tailscale)에 배포됨.
# 공개 HTTPS 경로 기본 사용. Tailscale 참여 시 ts.net 호스트 가능.
MCP_BASE_URL = os.environ.get("MCP_BASE_URL", "https://mcp.sometime-central.com/mcp")
MCP_BEARER_TOKEN = os.environ.get("MCP_BEARER_TOKEN", "")
MCP_TOOL_ALLOWLIST = [
    "ask_sometime", "search_knowledge", "health",
    "get_metric", "get_revenue", "get_gem_stats",
    "ask_marketing_mentor", "get_fact",
]
MCP_TOOL_LIST_TTL_SECONDS = 60
MCP_MAX_TOOL_ITERATIONS = 5
MCP_TOOL_TIMEOUT_SECONDS = 60  # 도구별 매핑 없을 때 fallback
MCP_TOOL_TIMEOUTS = {
    # 빠른 DB/lookup (즉답)
    "health": 5,
    "get_fact": 5,
    "get_metric": 15,
    "get_revenue": 30,
    "get_gem_stats": 30,
    "search_knowledge": 30,
    # LLM 호출 기반 (macmini Claude opus) — 분석 요청은 길게
    "ask_sometime": 180,
    "ask_marketing_mentor": 180,
}
MCP_ENABLED = bool(MCP_BEARER_TOKEN)
