import asyncio
import json
import os
import time
from datetime import datetime
from typing import Callable, Awaitable

from core.logging import logger

_subscribers: list[Callable[[dict], Awaitable[None]]] = []
_jsonl_path: str | None = None
_jsonl_lock = asyncio.Lock()


def init(log_dir: str):
    global _jsonl_path
    os.makedirs(log_dir, exist_ok=True)
    _jsonl_path = os.path.join(log_dir, f"events-{datetime.now():%Y%m%d}.jsonl")


def subscribe(fn: Callable[[dict], Awaitable[None]]):
    _subscribers.append(fn)


async def emit(stage: str, payload: dict | None = None):
    evt = {"ts": time.time(), "stage": stage, "payload": payload or {}}
    if _jsonl_path:
        try:
            async with _jsonl_lock:
                with open(_jsonl_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(evt, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning(f"[EventBus] JSONL write 실패: {e}")
    for fn in list(_subscribers):
        try:
            await fn(evt)
        except Exception as e:
            logger.warning(f"[EventBus] subscriber 오류: {e}")
