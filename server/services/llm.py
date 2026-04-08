from openai import AsyncOpenAI
import config

_client: AsyncOpenAI = None

def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(base_url=config.GEMMA_BASE_URL, api_key=config.GEMMA_API_KEY)
    return _client

async def stream_response(messages: list[dict]):
    """Gemma 4 스트리밍 응답. (content 청크, is_final) yield"""
    client = get_client()
    async with client.chat.completions.stream(
        model=config.GEMMA_MODEL,
        messages=messages,
        max_tokens=config.GEMMA_MAX_TOKENS,
    ) as stream:
        async for chunk in stream:
            content = chunk.choices[0].delta.content if chunk.choices else ""
            if content:
                yield content, False
    yield "", True
