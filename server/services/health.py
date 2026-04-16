import time
import httpx
import config
from db.database import get_db

_cache = {"ts": 0.0, "data": None}
CACHE_TTL = 5.0

async def _probe(url: str, timeout: float = 0.3) -> bool:
    try:
        async with httpx.AsyncClient(timeout=timeout) as c:
            r = await c.get(url)
            return r.status_code < 500
    except Exception:
        return False

async def _db_ping() -> bool:
    try:
        db = await get_db()
        async with db.execute("SELECT 1") as cur:
            await cur.fetchone()
        return True
    except Exception:
        return False

async def check() -> dict:
    if time.time() - _cache["ts"] < CACHE_TTL and _cache["data"]:
        return _cache["data"]
    from services import stt
    data = {
        "llm": await _probe(f"{config.GEMMA_BASE_URL}/models"),
        "tts": await _probe(f"{config.TTS_URL}/health"),
        "stt": stt._model is not None,
        "db": await _db_ping(),
    }
    data["ok"] = all(data.values())
    _cache["ts"] = time.time()
    _cache["data"] = data
    return data
