import asyncio
import datetime
import config
import core.context as ctx
import core.orchestrator as orchestrator

DEFAULT_SESSION = "default"

async def _send_proactive(msg: str):
    await orchestrator.handle_message(msg, DEFAULT_SESSION, event_type="proactive")

async def _check_idle():
    if ctx.idle_seconds() >= config.IDLE_TRIGGER_MINUTES * 60:
        await _send_proactive("한동안 조용하네. 막힌 거야, 아니면 생각 중이야?")

async def _check_night():
    hour = datetime.datetime.now().hour
    if config.NIGHT_HOUR_START <= hour < config.NIGHT_HOUR_END:
        await _send_proactive(f"지금 {hour}시잖아. 이 시간에도 코딩 중이야? 좀 쉬어야 하지 않아?")

async def run():
    while True:
        await asyncio.sleep(300)
        try:
            await _check_idle()
            await _check_night()
        except Exception as e:
            print(f"[Proactive] 오류: {e}")
