import asyncio
import time
import uuid
from collections import deque
from typing import Callable, Awaitable

import config
import db.history as history
import services.llm as llm
import services.tts as tts
import services.persona as persona
import core.context as ctx

_broadcaster: Callable[[dict], Awaitable[None]] | None = None
_tasks: set[asyncio.Task] = set()
_recent_cmds: deque = deque(maxlen=config.RECENT_CMD_RING_SIZE)

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
    ctx.touch()

    system_prompt = persona.build_system_prompt(ctx.get())
    recent = await history.get_recent(session_id, limit=20)
    messages = [{"role": "system", "content": system_prompt}] + recent

    await _send({"type": "avatar_emotion", "emotion": "thinking", "intensity": 0.7})

    full_text = ""
    chunker = tts.SentenceChunker()
    tts_tasks: list[asyncio.Task] = []

    async for chunk, is_final in llm.stream_response(messages):
        if not is_final:
            full_text += chunk
            await _send({"type": "text_chunk", "content": chunk, "is_final": False, "message_id": msg_id})
            for sentence in chunker.feed(chunk):
                tts_tasks.append(_track(_dispatch_tts(sentence, msg_id)))
        else:
            await _send({"type": "text_done", "message_id": msg_id, "full_content": full_text})

    tail = chunker.finalize()
    if tail:
        tts_tasks.append(_track(_dispatch_tts(tail, msg_id)))

    await history.save_message(session_id, "assistant", full_text, event_type)
    emotion, intensity = persona.classify_emotion(full_text)
    await _send({"type": "avatar_emotion", "emotion": emotion, "intensity": intensity})
    await asyncio.gather(*tts_tasks, return_exceptions=True)

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

    _recent_cmds.append((command, exit_code))

    if exit_code != 0:
        recent_fails = [c for c, e in list(_recent_cmds)[-config.REPEAT_FAIL_THRESHOLD:]
                        if c == command and e != 0]
        if len(recent_fails) >= config.REPEAT_FAIL_THRESHOLD:
            msg = f"'{command}' 계속 실패하고 있네. 다른 방법 시도해볼까?"
            _recent_cmds.clear()
        else:
            msg = f"터미널에서 '{command}' 명령이 실패했어 (exit {exit_code}). 에러 확인해줄까?"
        await handle_message(msg, session_id, event_type="terminal")

_last_posttool_ts = 0.0

async def _on_stop(payload: dict, session_id: str):
    await handle_message("Claude Code 작업이 끝났어! 뭘 만들었는지 궁금한데?", session_id, event_type="claude_hook")

async def _on_post_tool_use(payload: dict, session_id: str):
    global _last_posttool_ts
    tool_name = payload.get("tool_name", "")
    if tool_name not in config.CLAUDE_POSTTOOL_TOOLS:
        return
    now = time.time()
    if now - _last_posttool_ts < config.CLAUDE_POSTTOOL_DEBOUNCE_SECONDS:
        return
    _last_posttool_ts = now
    await handle_message(f"{tool_name} 썼네. 뭐 고쳤어?", session_id, event_type="claude_hook")

CLAUDE_HOOK_HANDLERS = {
    "Stop": _on_stop,
    "PostToolUse": _on_post_tool_use,
}

async def handle_claude_hook(hook_type: str, payload: dict, session_id: str):
    ctx.update("claude_task", hook_type)
    handler = CLAUDE_HOOK_HANDLERS.get(hook_type)
    if handler:
        await handler(payload, session_id)
