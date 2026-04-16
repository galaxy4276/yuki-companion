import time
import httpx
import config
from core.logging import logger

_client = httpx.AsyncClient(timeout=config.MCP_TOOL_TIMEOUT_SECONDS)
_tool_cache = {"ts": 0.0, "tools": None}
_req_id = 0

def _next_id() -> int:
    global _req_id
    _req_id += 1
    return _req_id

def _headers() -> dict:
    h = {"Content-Type": "application/json", "Accept": "application/json"}
    if config.MCP_BEARER_TOKEN:
        h["Authorization"] = f"Bearer {config.MCP_BEARER_TOKEN}"
    return h

async def _rpc(method: str, params: dict | None = None) -> dict:
    body = {"jsonrpc": "2.0", "id": _next_id(), "method": method}
    if params is not None:
        body["params"] = params
    r = await _client.post(config.MCP_BASE_URL, json=body, headers=_headers())
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        raise RuntimeError(f"MCP error: {data['error']}")
    return data.get("result", {})

async def list_tools(force: bool = False) -> list[dict]:
    """OpenAI function-calling 스키마로 변환된 tool 리스트."""
    if not config.MCP_ENABLED:
        return []
    if not force and _tool_cache["tools"] and time.time() - _tool_cache["ts"] < config.MCP_TOOL_LIST_TTL_SECONDS:
        return _tool_cache["tools"]
    try:
        await _rpc("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "yuki-companion", "version": "1.0.0"},
        })
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
        logger.info(f"[MCP] {len(converted)}개 tool 로드: {[t['function']['name'] for t in converted]}")
        return converted
    except Exception as e:
        logger.warning(f"[MCP] tools/list 실패: {e}")
        return []

async def call_tool(name: str, args: dict) -> str:
    if name not in config.MCP_TOOL_ALLOWLIST:
        return f"Tool '{name}' not in allowlist"
    try:
        result = await _rpc("tools/call", {"name": name, "arguments": args})
        contents = result.get("content", [])
        texts = [c.get("text", "") for c in contents if c.get("type") == "text"]
        return "\n".join(texts) or str(result)
    except Exception as e:
        logger.warning(f"[MCP] call_tool({name}) 실패: {e}")
        return f"[MCP 오류: {e}]"
