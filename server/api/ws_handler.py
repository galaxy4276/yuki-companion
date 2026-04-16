import asyncio
import json
import base64
from fastapi import WebSocket, WebSocketDisconnect

import core.orchestrator as orchestrator
from core import context
import services.stt as stt
from core.logging import logger

_connections: set[WebSocket] = set()
_audio_buffers: dict[str, list[bytes]] = {}
_tasks: set[asyncio.Task] = set()

def _track(coro) -> asyncio.Task:
    task = asyncio.create_task(coro)
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    task.add_done_callback(_log_exc)
    return task

def _log_exc(task: asyncio.Task):
    if not task.cancelled() and task.exception():
        logger.error(f"[WS] 태스크 오류: {task.exception()}")

async def broadcast(payload: dict):
    if not _connections:
        return
    msg = json.dumps(payload, ensure_ascii=False)
    results = await asyncio.gather(
        *[ws.send_text(msg) for ws in _connections],
        return_exceptions=True,
    )
    dead = {ws for ws, r in zip(list(_connections), results) if isinstance(r, Exception)}
    _connections.difference_update(dead)

orchestrator.set_broadcaster(broadcast)

async def handle_ws(websocket: WebSocket):
    await websocket.accept()
    _connections.add(websocket)
    session_id = "default"

    await websocket.send_text(json.dumps({
        "type": "system_status",
        "llm_ready": True,
        "tts_ready": True,
        "stt_ready": True,
    }))

    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            msg_type = data.get("type")
            session_id = data.get("session_id", session_id)

            if msg_type == "text_message":
                _track(orchestrator.handle_message(data["content"], session_id, "text"))

            elif msg_type == "audio_chunk":
                buf = _audio_buffers.setdefault(session_id, [])
                buf.append(base64.b64decode(data["data"]))
                if data.get("is_final"):
                    audio_bytes = b"".join(_audio_buffers.pop(session_id, []))
                    _track(_process_audio(audio_bytes, session_id))

            elif msg_type == "terminal_event":
                _track(orchestrator.handle_terminal_event(
                    data.get("command", ""),
                    data.get("exit_code", 0),
                    data.get("duration_ms", 0),
                    data.get("cwd", ""),
                    session_id,
                ))

            elif msg_type == "claude_hook":
                _track(orchestrator.handle_claude_hook(
                    data.get("hook_type", ""),
                    data,
                    session_id,
                ))

            elif msg_type == "screen_capture":
                try:
                    context.set_screenshot(base64.b64decode(data["data"]))
                except Exception as e:
                    logger.warning(f"[WS] screen_capture decode 실패: {e}")

    except WebSocketDisconnect:
        _connections.discard(websocket)

async def _process_audio(audio_bytes: bytes, session_id: str):
    loop = asyncio.get_running_loop()
    text = await loop.run_in_executor(None, stt.transcribe, audio_bytes)
    if not text:
        return
    await broadcast({"type": "stt_result", "text": text})
    await orchestrator.handle_message(text, session_id, "voice")
