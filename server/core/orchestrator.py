import asyncio
import uuid
from typing import Callable, Awaitable

import db.history as history
import services.llm as llm
import services.tts as tts
import services.persona as persona
import core.context as ctx

_broadcaster: Callable[[dict], Awaitable[None]] | None = None
_tasks: set[asyncio.Task] = set()

def set_broadcaster(fn: Callable[[dict], Awaitable[None]]):
    global _broadcaster
    _broadcaster = fn

async def _send(payload: dict):
    if _broadcaster:
        await _broadcaster(payload)

def _track(coro) -> asyncio.Task:
    task = asyncio.create_task(coro)
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    task.add_done_callback(_log_exc)
    return task

def _log_exc(task: asyncio.Task):
    if not task.cancelled() and task.exception():
        print(f"[Orchestrator] 태스크 오류: {task.exception()}")

async def handle_message(content: str, session_id: str, event_type: str = "text"):
    msg_id = str(uuid.uuid4())[:8]

    await history.save_message(session_id, "user", content, event_type)
    ctx.update("last_activity", 0)  # last_activity를 현재 시각으로 갱신

    system_prompt = persona.build_system_prompt(ctx.get())
    recent = await history.get_recent(session_id, limit=10)
    messages = [{"role": "system", "content": system_prompt}] + recent

    await _send({"type": "avatar_emotion", "emotion": "thinking", "intensity": 0.7})

    full_text = ""
    async for chunk, is_final in llm.stream_response(messages):
        if not is_final:
            full_text += chunk
            await _send({"type": "text_chunk", "content": chunk, "is_final": False, "message_id": msg_id})
        else:
            await _send({"type": "text_done", "message_id": msg_id, "full_content": full_text})

    await history.save_message(session_id, "assistant", full_text, event_type)

    emotion, intensity = persona.classify_emotion(full_text)
    await asyncio.gather(
        _send({"type": "avatar_emotion", "emotion": emotion, "intensity": intensity}),
        _dispatch_tts(full_text, msg_id),
    )

async def _dispatch_tts(text: str, msg_id: str):
    if not text:
        return
    wav = await tts.synthesize(text)
    if wav:
        await _send({"type": "audio_response", "data": tts.to_base64(wav), "message_id": msg_id})

async def handle_terminal_event(command: str, exit_code: int, duration_ms: int, cwd: str, session_id: str):
    ctx.update("cwd", cwd)
    ctx.update("last_command", command)
    ctx.update("last_exit_code", exit_code)
    await history.save_terminal_event(command, exit_code, duration_ms, cwd)

    if exit_code != 0:
        msg = f"터미널에서 '{command}' 명령이 실패했어 (exit {exit_code}). 에러 확인해줄까?"
        await handle_message(msg, session_id, event_type="terminal")

async def handle_claude_hook(hook_type: str, payload: dict, session_id: str):
    ctx.update("claude_task", hook_type)
    if hook_type == "Stop":
        await handle_message("Claude Code 작업이 끝났어! 뭘 만들었는지 궁금한데?", session_id, event_type="claude_hook")
