import asyncio
import json
import os
import random
import time
import uuid
from collections import deque
from typing import Callable, Awaitable

import config
import db.history as history
import services.llm as llm
import services.tts as tts
import services.persona as persona
from services import mcp_client
from services import vision
import core.context as ctx
from core.logging import logger
from core import events

_broadcaster: Callable[[dict], Awaitable[None]] | None = None
_tasks: set[asyncio.Task] = set()
_recent_cmds: deque = deque(maxlen=config.RECENT_CMD_RING_SIZE)

_TOOL_TRIGGER_KEYWORDS = (
    "썸타임", "매출", "revenue", "매칭", "매치", "유저", "가입", "구슬", "gem",
    "지표", "metric", "dau", "wau", "mau", "kpi", "결제", "환불", "payment",
    "운영", "cs", "버그", "리포트", "리뷰", "대학", "학교",
)

def _needs_tools(content: str) -> bool:
    low = content.lower()
    return any(k in low for k in _TOOL_TRIGGER_KEYWORDS)

_templates_cache: dict = {"mtime": 0.0, "data": None}

def _load_templates() -> dict:
    try:
        mtime = os.path.getmtime(config.PROACTIVE_TEMPLATES_PATH)
        if _templates_cache["data"] is not None and mtime == _templates_cache["mtime"]:
            return _templates_cache["data"]
        with open(config.PROACTIVE_TEMPLATES_PATH, encoding="utf-8") as f:
            data = json.load(f)
        _templates_cache["mtime"] = mtime
        _templates_cache["data"] = data
        return data
    except Exception as e:
        logger.warning(f"[Templates] 로드 실패: {e}")
        return {}

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
        logger.error(f"[Orchestrator] 태스크 오류: {task.exception()}")

async def _maybe_summarize(session_id: str):
    total = await history.count_turns(session_id)
    if total <= config.HISTORY_ROLLING_TURNS:
        return
    to_summarize = await history.get_turns_range(session_id, 0, config.HISTORY_SUMMARY_ON_OVERFLOW)
    if not to_summarize:
        return
    transcript = "\n".join(f"{t['role']}: {t['content']}" for t in to_summarize)
    prompt = [
        {"role": "system", "content": "아래 대화를 3~5문장으로 한국어 요약해."},
        {"role": "user", "content": transcript},
    ]
    summary = await llm.complete_once(prompt)
    await history.save_summary(session_id, summary, f"0-{config.HISTORY_SUMMARY_ON_OVERFLOW}")

async def _tool_loop(messages: list[dict], tools: list[dict]) -> list[dict]:
    """tool_calls 해소 후 최종 messages 반환. tools 비어있으면 패스스루."""
    if not tools:
        return messages
    for _ in range(config.MCP_MAX_TOOL_ITERATIONS):
        try:
            msg = await llm.complete_with_tools(messages, tools)
        except Exception as e:
            logger.warning(f"[ToolLoop] LLM 호출 실패: {e}")
            return messages
        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            return messages
        messages.append({"role": "assistant", "tool_calls": tool_calls, "content": msg.get("content") or ""})
        for tc in tool_calls:
            fn = tc.get("function", {})
            name = fn.get("name", "")
            args_raw = fn.get("arguments", "{}")
            try:
                args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
            except Exception:
                args = {}
            result = await mcp_client.call_tool(name, args)
            messages.append({
                "role": "tool", "tool_call_id": tc.get("id", ""),
                "name": name, "content": result,
            })
    return messages

async def _emit_text_only(msg: str, msg_id: str):
    """LLM 스킵 시 text_chunk + text_done + emotion + action + TTS."""
    cleaned, action = persona.extract_action(msg)
    await _send({"type": "text_chunk", "content": cleaned, "is_final": False, "message_id": msg_id})
    await _send({"type": "text_done", "message_id": msg_id, "full_content": cleaned})
    emotion, intensity = persona.classify_emotion(cleaned)
    await _send({"type": "avatar_emotion", "emotion": emotion, "intensity": intensity})
    if action:
        await _send({"type": "avatar_action", "action": action})
    await _dispatch_tts(cleaned, msg_id)

async def handle_message(content: str, session_id: str, event_type: str = "text"):
    msg_id = str(uuid.uuid4())[:8]

    await history.save_message(session_id, "user", content, event_type)
    ctx.touch()

    t0 = time.time()
    try:
        await events.emit("msg.start", {"content": content, "session_id": session_id, "event_type": event_type, "msg_id": msg_id})
    except Exception:
        pass

    system_prompt = persona.build_system_prompt(ctx.get())

    want_tools = config.MCP_ENABLED and _needs_tools(content)
    recent, summary, tools = await asyncio.gather(
        history.get_recent(session_id, limit=config.HISTORY_ROLLING_TURNS),
        history.get_latest_summary(session_id),
        mcp_client.list_tools() if want_tools else _noop_list(),
    )

    messages = [{"role": "system", "content": system_prompt}]
    if summary:
        messages.append({"role": "system", "content": f"이전 대화 요약: {summary}"})
    messages.extend(recent)

    messages = vision.prepare(messages)
    if want_tools and tools:
        logger.info(f"[Orchestrator] tool-loop 진입 ({len(tools)}개 tool)")
        messages = await _tool_loop(messages, tools)

    await _send({"type": "avatar_emotion", "emotion": "thinking", "intensity": 0.7})
    try:
        await events.emit("msg.emotion", {"emotion": "thinking", "intensity": 0.7})
    except Exception:
        pass

    full_text = ""
    chunker = tts.SentenceChunker()
    tts_tasks: list[asyncio.Task] = []
    stripper = persona.ActionTagStripper()
    action_sent = False

    async for chunk, is_final in llm.stream_response(messages):
        if not is_final:
            cleaned = stripper.feed(chunk)
            if not action_sent and stripper.action:
                action_sent = True
                await _send({"type": "avatar_action", "action": stripper.action})
                try:
                    await events.emit("msg.action", {"action": stripper.action})
                except Exception:
                    pass
            if cleaned:
                full_text += cleaned
                await _send({"type": "text_chunk", "content": cleaned, "is_final": False, "message_id": msg_id})
                for sentence in chunker.feed(cleaned):
                    tts_tasks.append(_track(_dispatch_tts(sentence, msg_id)))
        else:
            leftover = stripper.flush()
            if leftover:
                full_text += leftover
                await _send({"type": "text_chunk", "content": leftover, "is_final": False, "message_id": msg_id})
                for sentence in chunker.feed(leftover):
                    tts_tasks.append(_track(_dispatch_tts(sentence, msg_id)))
            try:
                await events.emit("msg.done", {"msg_id": msg_id, "full_text": full_text, "duration_ms": int((time.time()-t0)*1000), "tts_count": len(tts_tasks)})
            except Exception:
                pass
            await _send({"type": "text_done", "message_id": msg_id, "full_content": full_text})

    tail = chunker.finalize()
    if tail:
        tts_tasks.append(_track(_dispatch_tts(tail, msg_id)))

    await history.save_message(session_id, "assistant", full_text, event_type)
    emotion, intensity = persona.classify_emotion(full_text)
    await _send({"type": "avatar_emotion", "emotion": emotion, "intensity": intensity})
    try:
        await events.emit("msg.emotion", {"emotion": emotion, "intensity": intensity})
    except Exception:
        pass
    if not action_sent:
        chosen = random.choice(persona.EXPRESSIVE_ACTIONS)
        await _send({"type": "avatar_action", "action": chosen})
        try:
            await events.emit("msg.action", {"action": chosen})
        except Exception:
            pass
    await asyncio.gather(*tts_tasks, return_exceptions=True)
    _track(_maybe_summarize(session_id))

async def _noop_list() -> list:
    return []

async def _dispatch_tts(text: str, msg_id: str):
    if not text:
        return
    wav = await tts.synthesize(text)
    if wav:
        await _send({"type": "audio_response", "data": tts.to_base64(wav), "message_id": msg_id})
    else:
        await _send({"type": "error", "source": "tts", "message": "TTS 합성 실패"})

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

async def handle_templated(template_key: str, session_id: str, context: dict = None):
    """LLM 스킵, 템플릿에서 랜덤 선택 → TTS 직송."""
    templates = _load_templates()
    pool = templates.get(template_key, [])
    if not pool:
        return
    msg = random.choice(pool).format(**(context or {}))
    await history.save_message(session_id, "assistant", msg, f"proactive_{template_key}")
    await _emit_text_only(msg, "tpl")
