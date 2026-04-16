import os

# Gemma 4
GEMMA_BASE_URL = "http://localhost:8001/v1"
GEMMA_API_KEY  = "w7PhLd603vZQ8Om-Ys7wHeK6CZyzK4ngp1lwsYh2oyQ"
GEMMA_MODEL    = "gemma-4"
GEMMA_MAX_TOKENS = 512

# TTS
TTS_URL = "http://localhost:8880"

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
