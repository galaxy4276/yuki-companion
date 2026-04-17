import time
from openai import AsyncOpenAI
import config
from core import events

_client: AsyncOpenAI | None = None

def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(base_url=config.GEMMA_BASE_URL, api_key=config.GEMMA_API_KEY)
    return _client

def _sanitize_messages(messages):
    out = []
    for m in messages:
        c = m.get("content")
        if isinstance(c, list):
            new_c = []
            for item in c:
                if isinstance(item, dict) and item.get("type") == "image_url":
                    new_c.append({"type": "image_url", "image_url": {"url": "[IMAGE]"}})
                else:
                    new_c.append(item)
            out.append({**m, "content": new_c})
        else:
            out.append(m)
    return out

async def stream_response(messages: list[dict], tools: list[dict] | None = None):
    """Gemma 4 스트리밍. (content chunk, is_final) yield. tools 전달 시 function-calling 지원."""
    client = get_client()
    kwargs = dict(
        model=config.GEMMA_MODEL,
        messages=messages,
        max_tokens=config.GEMMA_MAX_TOKENS,
        stream=True,
    )
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    t0 = time.time()
    try:
        await events.emit("llm.request", {"messages": _sanitize_messages(messages), "tools_count": len(tools) if tools else 0, "model": config.GEMMA_MODEL, "stream": True})
    except Exception:
        pass

    try:
        stream = await client.chat.completions.create(**kwargs)
    except Exception as e:
        try:
            await events.emit("llm.fail", {"reason": str(e)})
        except Exception:
            pass
        raise

    accum = ""
    async for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        content = delta.content or ""
        if content:
            accum += content
            try:
                await events.emit("llm.chunk", {"content": content})
            except Exception:
                pass
            yield content, False
    yield "", True

    try:
        await events.emit("llm.response", {"chars": len(accum), "duration_ms": int((time.time()-t0)*1000), "stream": True})
    except Exception:
        pass

async def complete_once(messages: list[dict]) -> str:
    """단발 응답 (요약 생성 등)."""
    client = get_client()
    resp = await client.chat.completions.create(
        model=config.GEMMA_MODEL, messages=messages, max_tokens=config.GEMMA_MAX_TOKENS,
    )
    return resp.choices[0].message.content or ""

async def complete_with_tools(messages: list[dict], tools: list[dict]) -> dict:
    """tool_calls 응답 판별용 non-stream 호출. 결과 message dict 리턴."""
    client = get_client()

    t0 = time.time()
    try:
        await events.emit("llm.request", {"messages": _sanitize_messages(messages), "tools_count": len(tools) if tools else 0, "model": config.GEMMA_MODEL, "stream": False})
    except Exception:
        pass

    try:
        resp = await client.chat.completions.create(
            model=config.GEMMA_MODEL, messages=messages,
            max_tokens=config.GEMMA_MAX_TOKENS, tools=tools, tool_choice="auto",
        )
    except Exception as e:
        try:
            await events.emit("llm.fail", {"reason": str(e)})
        except Exception:
            pass
        raise

    msg = resp.choices[0].message
    if msg.tool_calls:
        try:
            await events.emit("llm.tool_call", {"tool_calls": [tc.model_dump() for tc in msg.tool_calls]})
        except Exception:
            pass
    else:
        try:
            await events.emit("llm.response", {"chars": len(msg.content or ""), "duration_ms": int((time.time()-t0)*1000), "stream": False})
        except Exception:
            pass

    return msg.model_dump()
