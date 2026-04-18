import asyncio
import datetime
import hashlib
import json
import math
import re
import time
import config
import core.context as ctx
import core.orchestrator as orchestrator
from core.logging import logger
from services.memory import flusher
from services import mcp_client
from db import history as db_history

DEFAULT_SESSION = "default"
_last_idle_trigger = 0.0
_last_night_trigger = 0.0
_baseline_established = False
_hourly_trigger_log: list[float] = []

async def _check_idle():
    global _last_idle_trigger
    if ctx.idle_seconds() < config.IDLE_TRIGGER_MINUTES * 60:
        return
    now = time.time()
    if now - _last_idle_trigger < config.IDLE_TRIGGER_MINUTES * 60:
        return
    _last_idle_trigger = now
    await orchestrator.handle_templated("idle", DEFAULT_SESSION)
    await flusher.maybe_flush("idle")


async def _check_ctx_pressure():
    try:
        from db import history
        if hasattr(history, "count_turns"):
            turns = await history.count_turns(DEFAULT_SESSION)
        else:
            recent = await history.get_recent(session_id=DEFAULT_SESSION, limit=200)
            turns = len(recent)
        if turns > getattr(config, "HISTORY_ROLLING_TURNS", 40) * 1.5:
            await flusher.maybe_flush("ctx_pressure", force=True)
    except Exception as e:
        logger.warning(f"[proactive] ctx-pressure check failed: {e}")

async def _check_night():
    global _last_night_trigger
    hour = datetime.datetime.now().hour
    if not (config.NIGHT_HOUR_START <= hour < config.NIGHT_HOUR_END):
        return
    elapsed = time.time() - _last_night_trigger
    if elapsed < config.NIGHT_TRIGGER_COOLDOWN_HOURS * 3600:
        return
    _last_night_trigger = time.time()
    await orchestrator.handle_templated("night", DEFAULT_SESSION, {"hour": hour})

_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _extract_numeric(raw: str) -> float | None:
    if raw is None:
        return None
    m = _NUM_RE.search(raw)
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def _topic_hash(tool_name: str, raw_value: str, bucket_pct: float) -> str:
    """Same bucket → same hash. bucket_pct=10 → quantize by order-of-magnitude × pct.

    Reference magnitude = 10^floor(log10(|n|)) so values within same order-of-magnitude
    bucket to the same step (stable across nearby values, unlike value-dependent mag).
    """
    n = _extract_numeric(raw_value)
    if n is None or n == 0:
        key = f"{tool_name}:{raw_value}"
    else:
        oom = 10 ** math.floor(math.log10(abs(n)))
        step = oom * (bucket_pct / 100.0) or 1.0
        bucketed = round(n / step) * step
        key = f"{tool_name}:{bucketed:.4f}"
    return hashlib.sha1(key.encode()).hexdigest()[:16]


def _detect_delta(old_raw: str | None, new_raw: str, threshold_pct: float) -> bool:
    if old_raw is None:
        return False  # baseline run — never trigger on first sample
    if old_raw == new_raw:
        return False
    old_n = _extract_numeric(old_raw)
    new_n = _extract_numeric(new_raw)
    if old_n is None or new_n is None:
        return old_raw != new_raw  # fall back to string equality
    if old_n == 0:
        return abs(new_n) > 0
    pct = abs(new_n - old_n) / abs(old_n) * 100.0
    return pct >= threshold_pct


def _synth_message(tool_name: str, old_raw: str | None, new_raw: str) -> str:
    """Build Korean user-role quoted message. MCP raw is untrusted — wrap in quote block."""
    tool_ko = {
        "get_revenue": "매출 지표",
        "get_gem_stats": "재화 지표",
        "get_metric": "지표",
    }.get(tool_name, tool_name)
    old_excerpt = (old_raw or "없음")[:200]
    new_excerpt = new_raw[:200]
    return (
        f"[알림] {tool_ko}에서 변화 감지:\n"
        f"> 이전: {old_excerpt}\n"
        f"> 현재: {new_excerpt}\n"
        f"이 변화에 대해 짧게 한 문장으로 질문해줘."
    )


async def _poll_one(tool_name: str, timeout: float) -> tuple[str, str | None, str | None]:
    """Return (tool_name, raw_result, error). Never raises."""
    try:
        raw = await asyncio.wait_for(mcp_client.call_tool(tool_name, {}), timeout=timeout)
        if raw.startswith("[MCP 오류") or raw.startswith("Tool '"):
            return tool_name, None, raw
        return tool_name, raw, None
    except asyncio.TimeoutError:
        return tool_name, None, f"timeout>{timeout}s"
    except Exception as e:
        return tool_name, None, str(e)


async def _poll_metrics() -> dict[str, str]:
    """Parallel poll with per-tool timeout. Returns {tool_name: raw} for successes only."""
    tools = config.PROACTIVE_METRIC_TOOLS
    timeout = config.PROACTIVE_METRIC_PER_TOOL_TIMEOUT
    results = await asyncio.gather(
        *[_poll_one(t, timeout) for t in tools],
        return_exceptions=False,
    )
    out = {}
    for name, raw, err in results:
        if err:
            logger.warning(f"[Proactive] MCP poll {name} 실패: {err}")
        elif raw is not None:
            out[name] = raw
    return out


async def _rate_limit_ok() -> bool:
    now = time.time()
    cutoff = now - 3600
    global _hourly_trigger_log
    _hourly_trigger_log = [t for t in _hourly_trigger_log if t >= cutoff]
    return len(_hourly_trigger_log) < config.PROACTIVE_GLOBAL_MAX_PER_HOUR


async def _check_metrics():
    global _baseline_established
    if not config.PROACTIVE_METRIC_ENABLED:
        return
    if not config.MCP_ENABLED:
        return
    if config.PROACTIVE_METRIC_SKIP_IF_NO_CLIENT:
        try:
            from api.ws_handler import has_active_clients
            if not has_active_clients():
                return
        except Exception:
            pass  # import cycle fallback — proceed
    if not await _rate_limit_ok():
        return

    current = await _poll_metrics()
    if not current:
        return

    if not _baseline_established:
        # First run: persist baselines silently, no firing.
        for tool_name, raw in current.items():
            topic = _topic_hash(tool_name, raw, config.PROACTIVE_METRIC_BUCKET_PCT)
            await db_history.save_proactive_snapshot(topic, tool_name, raw, triggered=False)
        _baseline_established = True
        logger.info(f"[Proactive] baseline 기록: {list(current.keys())}")
        return

    for tool_name, raw in current.items():
        topic = _topic_hash(tool_name, raw, config.PROACTIVE_METRIC_BUCKET_PCT)
        snapshot = await db_history.load_proactive_snapshot(tool_name)
        old_raw = None
        if topic in snapshot:
            old_raw = snapshot[topic]["last_value"]
        elif snapshot:
            most_recent = max(snapshot.values(),
                              key=lambda m: m.get("last_triggered_at") or "")
            old_raw = most_recent.get("last_value")

        if not _detect_delta(old_raw, raw, config.PROACTIVE_METRIC_DELTA_PCT):
            await db_history.save_proactive_snapshot(topic, tool_name, raw, triggered=False)
            continue

        if await db_history.is_proactive_throttled(topic, config.PROACTIVE_METRIC_TOPIC_THROTTLE_SECONDS):
            continue

        msg = _synth_message(tool_name, old_raw, raw)
        await db_history.save_proactive_snapshot(topic, tool_name, raw, triggered=True)
        _hourly_trigger_log.append(time.time())
        await orchestrator.handle_message(msg, DEFAULT_SESSION, event_type="proactive_metric")
        return  # one trigger per cycle (anti-overlap)


async def run():
    while True:
        await asyncio.sleep(300)
        try:
            await _check_idle()
            await _check_night()
            await _check_ctx_pressure()
            await _check_metrics()
        except Exception as e:
            logger.warning(f"[Proactive] 오류: {e}")
