import time
import httpx
import config
from core.logging import logger
from core import events
from core.events import since_ms

_MAX_TIMEOUT = max([config.MCP_TOOL_TIMEOUT_SECONDS, *config.MCP_TOOL_TIMEOUTS.values()])
_client = httpx.AsyncClient(timeout=_MAX_TIMEOUT)


def _timeout_for(tool_name: str) -> float:
    return float(config.MCP_TOOL_TIMEOUTS.get(tool_name, config.MCP_TOOL_TIMEOUT_SECONDS))
_tool_cache = {"ts": 0.0, "tools": None}
_req_id = 0
_initialized = False

def _next_id() -> int:
    global _req_id
    _req_id += 1
    return _req_id

def _headers() -> dict:
    h = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    if config.MCP_BEARER_TOKEN:
        h["Authorization"] = f"Bearer {config.MCP_BEARER_TOKEN}"
    return h

def _parse_response(text: str, content_type: str) -> dict:
    if "text/event-stream" in content_type:
        for line in text.splitlines():
            if line.startswith("data:"):
                import json
                return json.loads(line[5:].strip())
        raise RuntimeError("MCP SSE: no data line")
    import json
    return json.loads(text)

async def _rpc(method: str, params: dict | None = None, timeout: float | None = None) -> dict:
    body = {"jsonrpc": "2.0", "id": _next_id(), "method": method}
    if params is not None:
        body["params"] = params
    kwargs = {"json": body, "headers": _headers()}
    if timeout is not None:
        kwargs["timeout"] = timeout
    r = await _client.post(config.MCP_BASE_URL, **kwargs)
    r.raise_for_status()
    data = _parse_response(r.text, r.headers.get("content-type", ""))
    if "error" in data:
        raise RuntimeError(f"MCP error: {data['error']}")
    return data.get("result", {})

async def list_tools(force: bool = False) -> list[dict]:
    """OpenAI function-calling 스키마로 변환된 tool 리스트."""
    global _initialized
    if not config.MCP_ENABLED:
        return []
    if not force and _tool_cache["tools"] and time.time() - _tool_cache["ts"] < config.MCP_TOOL_LIST_TTL_SECONDS:
        return _tool_cache["tools"]
    try:
        if not _initialized:
            await _rpc("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "yuki-companion", "version": "1.0.0"},
            })
            _initialized = True
        result = await _rpc("tools/list")
        raw = result.get("tools", [])
        filtered = [t for t in raw if t["name"] in config.MCP_TOOL_ALLOWLIST]
        converted = [{
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("inputSchema", {"type": "object", "properties": {}}),
            }
        } for t in filtered]
        _tool_cache["tools"] = converted
        _tool_cache["ts"] = time.time()
        names = [t['function']['name'] for t in converted]
        logger.info(f"[MCP] {len(converted)}개 tool 로드: {names}")
        await events.emit("mcp.list_tools", {"count": len(converted), "names": names})
        return converted
    except Exception as e:
        logger.warning(f"[MCP] tools/list 실패: {e}")
        return []

_RESULT_PREVIEW_CHARS = 500

def _err_repr(e: Exception) -> str:
    s = str(e)
    return s if s else f"{type(e).__name__}"

async def call_tool(name: str, args: dict) -> str:
    if name not in config.MCP_TOOL_ALLOWLIST:
        return f"Tool '{name}' not in allowlist"
    timeout = _timeout_for(name)
    t0 = time.time()
    await events.emit("mcp.call", {"name": name, "args": args, "timeout_s": timeout})
    try:
        result = await _rpc("tools/call", {"name": name, "arguments": args}, timeout=timeout)
        contents = result.get("content", [])
        texts = [c.get("text", "") for c in contents if c.get("type") == "text"]
        text_result = "\n".join(texts) or str(result)
        if len(text_result) > config.MCP_TOOL_RESULT_MAX_CHARS:
            text_result = text_result[:config.MCP_TOOL_RESULT_MAX_CHARS] + f"\n...[truncated {len(text_result)-config.MCP_TOOL_RESULT_MAX_CHARS} chars]"
        await events.emit("mcp.result", {"name": name, "text": text_result[:_RESULT_PREVIEW_CHARS], "duration_ms": since_ms(t0)})
        return text_result
    except Exception as e:
        reason = _err_repr(e)
        logger.warning(f"[MCP] call_tool({name}) 실패 (timeout={timeout}s): {reason}")
        await events.emit("mcp.fail", {"name": name, "reason": reason, "duration_ms": since_ms(t0), "timeout_s": timeout})
        return f"[MCP 오류: {reason}]"
