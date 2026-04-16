import os

# Gemma 4
GEMMA_BASE_URL = "http://localhost:8001/v1"
GEMMA_API_KEY  = "w7PhLd603vZQ8Om-Ys7wHeK6CZyzK4ngp1lwsYh2oyQ"
GEMMA_MODEL    = "gemma-4"
GEMMA_MAX_TOKENS = 2048

# TTS
TTS_URL = "http://localhost:8880"
TTS_USERNAME = os.environ.get("TTS_USERNAME", "tts")
TTS_PASSWORD = os.environ.get("TTS_PASSWORD", "SmartNewbie!0705")

# STT
WHISPER_MODEL  = "medium"
WHISPER_DEVICE = "cuda"
WHISPER_COMPUTE = "int8"

# Server
HOST = "0.0.0.0"
PORT = 8002

# DB
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "companion.db")

# Persona
PERSONA_PATH = os.path.join(os.path.dirname(__file__), "data", "personas", "default.json")

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

HISTORY_ROLLING_TURNS = 20
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
    "ask-sometime", "search-knowledge", "health",
    "get-metric", "get-revenue", "get-gem-stats",
]
MCP_TOOL_LIST_TTL_SECONDS = 60
MCP_MAX_TOOL_ITERATIONS = 5
MCP_TOOL_TIMEOUT_SECONDS = 30
MCP_ENABLED = bool(MCP_BEARER_TOKEN)
