import asyncio
import datetime
import time
import config
import core.context as ctx
import core.orchestrator as orchestrator
from core.logging import logger

DEFAULT_SESSION = "default"
_last_idle_trigger = 0.0
_last_night_trigger = 0.0

async def _check_idle():
    global _last_idle_trigger
    if ctx.idle_seconds() < config.IDLE_TRIGGER_MINUTES * 60:
        return
    now = time.time()
    if now - _last_idle_trigger < config.IDLE_TRIGGER_MINUTES * 60:
        return
    _last_idle_trigger = now
    await orchestrator.handle_templated("idle", DEFAULT_SESSION)

async def _check_night():
    global _last_night_trigger
    hour = datetime.datetime.now().hour
    if not (config.NIGHT_HOUR_START <= hour < config.NIGHT_HOUR_END):
        return
    elapsed = time.time() - _last_night_trigger
    if elapsed < config.NIGHT_TRIGGER_COOLDOWN_HOURS * 3600:
        return
    _last_night_trigger = time.time()
    await orchestrator.handle_templated("night", DEFAULT_SESSION, {"hour": hour})

async def run():
    while True:
        await asyncio.sleep(300)
        try:
            await _check_idle()
            await _check_night()
        except Exception as e:
            logger.warning(f"[Proactive] 오류: {e}")
