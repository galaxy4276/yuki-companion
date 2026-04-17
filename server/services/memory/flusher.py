"""Episode flushing + MEMORY.md compaction."""
from __future__ import annotations
import time
from datetime import date
from core.logging import logger
from core import events

_memory = None
_last_flush_ts: dict[str, float] = {}
_COOLDOWN_S = 300


def init(memory_store):
    global _memory
    _memory = memory_store


async def flush_episode(reason: str, session_id: str = "default") -> str:
    """최근 대화를 LLM 요약 → episodes/YYYY-MM-DD-NN.md 저장. best-effort."""
    if _memory is None:
        return ""
    try:
        from db import history
        from services import llm

        turns = await history.get_recent(session_id=session_id, limit=20)
        if not turns:
            return ""

        convo = []
        for t in turns:
            role = t.get("role") if isinstance(t, dict) else getattr(t, "role", "")
            content = t.get("content") if isinstance(t, dict) else getattr(t, "content", "")
            if role and content:
                convo.append(f"{role}: {content}")
        raw = "\n".join(convo)

        sys_prompt = (
            "다음 대화를 한국어로 5-8문장 이내 요약. "
            "사용자 선호·진행 중 작업·중요 결정 위주. "
            "단순 감탄/잡담은 생략. 요약문만 출력."
        )
        summary = await _llm_summarize(llm, sys_prompt, raw)
        if not summary:
            return ""

        meta = {
            "type": "episode",
            "reason": reason,
            "source_count": len(turns),
            "date": date.today().isoformat(),
        }
        path = _memory.write_episode(summary, meta)
        await events.emit("episode.flush", {"reason": reason, "path": path, "source_count": len(turns)})
        logger.info(f"[flusher] episode saved reason={reason} path={path}")
        return path
    except Exception as e:
        logger.warning(f"[flusher] flush_episode failed: {e}")
        return ""


async def compact_memory() -> str:
    """MEMORY.md 200줄 초과 시 archive 후 LLM compact."""
    if _memory is None:
        return ""
    try:
        if _memory.count_lines() <= 200:
            return ""
        archive_path = _memory.archive()
        if not archive_path:
            return ""
        from pathlib import Path
        from services import llm
        archived = Path(archive_path).read_text(encoding="utf-8")
        sys_prompt = (
            "다음 메모리 본문을 50줄 이내로 compact. "
            "카테고리별로 그룹화. 중복 제거. 핵심 사실·선호·결정만 유지. "
            "원본의 '## [category] 날짜' 헤더 스타일 재사용."
        )
        compacted = await _llm_summarize(llm, sys_prompt, archived)
        if compacted:
            _memory.replace_memory(compacted)
        await events.emit("memory.compact", {"archived": archive_path, "compacted_lines": len((compacted or "").splitlines())})
        logger.info(f"[flusher] memory compacted, archive={archive_path}")
        return archive_path
    except Exception as e:
        logger.warning(f"[flusher] compact_memory failed: {e}")
        return ""


async def maybe_flush(trigger: str, force: bool = False, cooldown_s: int = _COOLDOWN_S) -> str:
    """Debounced trigger. Returns path if flushed, '' otherwise."""
    now = time.time()
    last = _last_flush_ts.get(trigger, 0.0)
    if not force and (now - last) < cooldown_s:
        return ""
    _last_flush_ts[trigger] = now
    path = await flush_episode(trigger)
    if trigger in ("ctx_pressure",):
        await compact_memory()
    return path


async def _llm_summarize(llm_module, system_prompt: str, user_content: str) -> str:
    """LLM 단발 요약. complete_once(messages) 우선, 없으면 stream_response fallback."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]
    if hasattr(llm_module, "complete_once"):
        try:
            result = await llm_module.complete_once(messages)
            return (result or "").strip()
        except Exception as e:
            logger.warning(f"[flusher] complete_once failed: {e}")
            return ""
    if hasattr(llm_module, "stream_response"):
        try:
            out = []
            async for chunk, is_final in llm_module.stream_response(messages):
                if chunk:
                    out.append(chunk)
                if is_final:
                    break
            return "".join(out).strip()
        except Exception as e:
            logger.warning(f"[flusher] stream_response summarize failed: {e}")
            return ""
    logger.warning("[flusher] llm module has neither complete_once nor stream_response")
    return ""
