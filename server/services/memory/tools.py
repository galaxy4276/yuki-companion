"""Gemma-facing memory/wiki tool schemas + dispatch."""
from __future__ import annotations
import json
from typing import Any
from core.logging import logger
from core import events

_memory = None
_wiki = None


def init(memory_store, wiki_store):
    global _memory, _wiki
    _memory = memory_store
    _wiki = wiki_store


_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "memory_recall",
            "description": "장기 기억(MEMORY.md + 최근 episode)에서 키워드로 관련 내용 회상. 질문의 배경이 될 과거 맥락이 필요할 때 호출.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "회상할 키워드 또는 문구"},
                    "k": {"type": "integer", "description": "반환할 episode 수", "default": 3}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "memory_save",
            "description": "사용자가 '기억해', '이거 중요' 등으로 명시적으로 저장 요청한 사실/선호/결정을 MEMORY.md에 추가.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "enum": ["fact", "preference", "project", "decision"]},
                    "content": {"type": "string", "description": "저장할 내용(한국어, 한두 문장)"}
                },
                "required": ["category", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "wiki_search",
            "description": "Wiki(개념/엔티티/비교) 페이지에서 용어 검색. 특정 기술·사람·도구·서비스를 대화 도중 발견했을 때 배경지식을 꺼낼 때 사용.",
            "parameters": {
                "type": "object",
                "properties": {
                    "term": {"type": "string"},
                    "type": {"type": "string", "enum": ["concept", "entity", "comparison"], "description": "없으면 전체"}
                },
                "required": ["term"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "wiki_update",
            "description": "Wiki 페이지의 특정 섹션을 추가/갱신. 새 기술·사람·서비스 등장 시 엔티티 페이지를 만들거나 갱신.",
            "parameters": {
                "type": "object",
                "properties": {
                    "page_type": {"type": "string", "enum": ["concept", "entity", "comparison"]},
                    "name": {"type": "string", "description": "페이지 이름 (파일 슬러그)"},
                    "section": {"type": "string", "description": "## 섹션 제목"},
                    "content": {"type": "string", "description": "섹션 본문 (한국어)"}
                },
                "required": ["page_type", "name", "section", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "episode_summarize",
            "description": "지금 대화 세션을 즉시 episode로 요약 저장. 사용자가 '이번 대화 기록해', '정리해'라고 할 때.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string", "default": "manual"}
                }
            }
        }
    },
]

_NAMES = {s["function"]["name"] for s in _SCHEMAS}


def list_tools() -> list[dict]:
    return list(_SCHEMAS)


def names() -> set[str]:
    return set(_NAMES)


async def dispatch(name: str, args: dict[str, Any] | str) -> str:
    if isinstance(args, str):
        try:
            args = json.loads(args) if args else {}
        except Exception:
            args = {}
    try:
        if name == "memory_recall":
            return await _memory_recall(**args)
        if name == "memory_save":
            return await _memory_save(**args)
        if name == "wiki_search":
            return await _wiki_search(**args)
        if name == "wiki_update":
            return await _wiki_update(**args)
        if name == "episode_summarize":
            return await _episode_summarize(**args)
    except TypeError as e:
        logger.warning(f"[memory.tools] bad args for {name}: {e}")
        return f"인자 오류: {e}"
    except Exception as e:
        logger.warning(f"[memory.tools] dispatch {name} error: {e}")
        return f"도구 실행 실패: {e}"
    return f"알 수 없는 도구: {name}"


async def _memory_recall(query: str, k: int = 3) -> str:
    if _memory is None:
        return "메모리 미초기화"
    body = _memory.load_memory() or ""
    episodes = _memory.load_recent_episode(k=k) or []
    haystack = body + "\n" + "\n---\n".join(episodes)
    q = (query or "").strip()
    hits = []
    if q:
        for line in haystack.splitlines():
            if q.lower() in line.lower():
                hits.append(line.strip())
    snippet = "\n".join(hits[:20]) if hits else "(매칭 없음)"
    await events.emit("mem.recall", {"query": query, "hits": len(hits), "k": k})
    return f"recall '{query}': {len(hits)}건\n{snippet}"


async def _memory_save(category: str, content: str) -> str:
    if _memory is None:
        return "메모리 미초기화"
    if category not in ("fact", "preference", "project", "decision"):
        return f"category 오류: {category}"
    _memory.append_memory(category, content)
    await events.emit("mem.save", {"category": category, "length": len(content)})
    return f"저장 완료 [{category}]"


async def _wiki_search(term: str, type: str | None = None) -> str:
    if _wiki is None:
        return "wiki 미초기화"
    term_l = (term or "").lower()
    # 단순 substring 검색 (Phase 5에서 시맨틱 추가)
    pages = _wiki.list_pages(page_type=None)
    results = []
    for p in pages:
        if type and p.get("type", "").rstrip("s") != type.rstrip("s"):
            continue
        name = p.get("name", "")
        title = p.get("title", "")
        # load content for search
        try:
            from services.memory.frontmatter import load_page
            post = load_page(p["path"])
            body = post.content if post else ""
        except Exception:
            body = ""
        if term_l in name.lower() or term_l in title.lower() or term_l in body.lower():
            # snippet
            idx = body.lower().find(term_l)
            snip = body[max(0, idx-60):idx+120].replace("\n", " ") if idx >= 0 else (title or name)
            results.append(f"- [[{name}]] ({p.get('type')}): {snip}")
    await events.emit("wiki.search", {"term": term, "type": type, "hits": len(results)})
    if not results:
        return f"wiki '{term}' 매칭 없음"
    return "wiki 검색 결과:\n" + "\n".join(results[:10])


async def _wiki_update(page_type: str, name: str, section: str, content: str) -> str:
    if _wiki is None:
        return "wiki 미초기화"
    pt = page_type if page_type.endswith("s") else page_type + "s"
    # Normalize to plural dir ('concepts'|'entities'|'comparisons')
    if pt not in ("concepts", "entities", "comparisons"):
        return f"page_type 오류: {page_type}"
    path = _wiki.update_page_section(pt, name, section, content)
    _wiki.update_index()
    _wiki.append_log(f"update {pt}/{name} §{section}")
    await events.emit("wiki.update", {"page_type": pt, "name": name, "section": section, "path": path})
    return f"wiki 갱신 완료: {pt}/{name} §{section}"


async def _episode_summarize(reason: str = "manual") -> str:
    # Phase 4 (flusher)에서 실제 구현. 지금은 큐잉 스텁.
    await events.emit("episode.flush", {"reason": reason, "status": "queued"})
    try:
        from services.memory import flusher  # type: ignore
        if hasattr(flusher, "flush_episode"):
            await flusher.flush_episode(reason)
            return f"episode 플러시 완료 ({reason})"
    except Exception as e:
        logger.info(f"[memory.tools] flusher 없음/미완 — queued: {e}")
    return f"episode 큐잉 ({reason})"
