from openai import AsyncOpenAI
import config

_client: AsyncOpenAI | None = None

def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(base_url=config.GEMMA_BASE_URL, api_key=config.GEMMA_API_KEY)
    return _client

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

    stream = await client.chat.completions.create(**kwargs)
    async for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        content = delta.content or ""
        if content:
            yield content, False
    yield "", True

async def complete_once(messages: list[dict]) -> str:
    """단발 응답 (요약 생성 등)."""
    client = get_client()
    resp = await client.chat.completions.create(
        model=config.GEMMA_MODEL, messages=messages, max_tokens=config.GEMMA_MAX_TOKENS,
    )
    return resp.choices[0].message.content or ""
