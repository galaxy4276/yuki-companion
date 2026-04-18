import asyncio
import pytest
from unittest.mock import patch

from core import proactive


def test_topic_hash_stable():
    h1 = proactive._topic_hash("get_revenue", "100", 10.0)
    h2 = proactive._topic_hash("get_revenue", "100", 10.0)
    assert h1 == h2


def test_topic_hash_same_bucket():
    h1 = proactive._topic_hash("get_revenue", "100", 10.0)
    h2 = proactive._topic_hash("get_revenue", "105", 10.0)
    assert h1 == h2


def test_topic_hash_different_bucket():
    h1 = proactive._topic_hash("get_revenue", "100", 10.0)
    h2 = proactive._topic_hash("get_revenue", "200", 10.0)
    assert h1 != h2


def test_detect_delta_none_baseline():
    assert proactive._detect_delta(None, "100", 10.0) is False


def test_detect_delta_below_threshold():
    assert proactive._detect_delta("100", "105", 10.0) is False


def test_detect_delta_above_threshold():
    assert proactive._detect_delta("100", "120", 10.0) is True


def test_detect_delta_zero_old():
    assert proactive._detect_delta("0", "10", 10.0) is True


def test_detect_delta_non_numeric_fallback():
    assert proactive._detect_delta("foo", "bar", 10.0) is True
    assert proactive._detect_delta("foo", "foo", 10.0) is False


def test_synth_message_korean():
    msg = proactive._synth_message("get_revenue", "100", "200")
    assert "[알림]" in msg
    assert "매출 지표" in msg
    assert "100" in msg
    assert "200" in msg


@pytest.mark.asyncio
async def test_poll_metrics_gathers_parallel():
    async def fake_call_tool(name, args):
        return {"get_revenue": "100", "get_gem_stats": "50", "get_metric": "7"}[name]

    with patch("core.proactive.mcp_client.call_tool", side_effect=fake_call_tool):
        with patch("core.proactive.config.PROACTIVE_METRIC_TOOLS",
                   ["get_revenue", "get_gem_stats", "get_metric"]):
            result = await proactive._poll_metrics()
    assert result == {"get_revenue": "100", "get_gem_stats": "50", "get_metric": "7"}


@pytest.mark.asyncio
async def test_poll_metrics_isolates_failure():
    async def fake_call_tool(name, args):
        if name == "get_revenue":
            raise RuntimeError("boom")
        return "42"

    with patch("core.proactive.mcp_client.call_tool", side_effect=fake_call_tool):
        with patch("core.proactive.config.PROACTIVE_METRIC_TOOLS", ["get_revenue", "get_gem_stats"]):
            result = await proactive._poll_metrics()
    assert "get_revenue" not in result
    assert result.get("get_gem_stats") == "42"


@pytest.mark.asyncio
async def test_poll_metrics_timeout():
    async def slow_tool(name, args):
        await asyncio.sleep(5)
        return "42"

    with patch("core.proactive.mcp_client.call_tool", side_effect=slow_tool):
        with patch("core.proactive.config.PROACTIVE_METRIC_TOOLS", ["get_revenue"]):
            with patch("core.proactive.config.PROACTIVE_METRIC_PER_TOOL_TIMEOUT", 0.1):
                result = await proactive._poll_metrics()
    assert result == {}


@pytest.mark.asyncio
async def test_check_metrics_baseline_first_run_no_fire(monkeypatch):
    """First run writes baseline, does NOT call handle_message."""
    monkeypatch.setattr(proactive, "_baseline_established", False)
    monkeypatch.setattr(proactive.config, "PROACTIVE_METRIC_ENABLED", True)
    monkeypatch.setattr(proactive.config, "MCP_ENABLED", True)
    monkeypatch.setattr(proactive.config, "PROACTIVE_METRIC_SKIP_IF_NO_CLIENT", False)
    monkeypatch.setattr(proactive, "_hourly_trigger_log", [])

    saved = []
    handled = []

    async def fake_poll():
        return {"get_revenue": "100"}

    async def fake_save(topic, tool, raw, triggered):
        saved.append((topic, tool, raw, triggered))

    async def fake_handle(*args, **kwargs):
        handled.append((args, kwargs))

    monkeypatch.setattr(proactive, "_poll_metrics", fake_poll)
    monkeypatch.setattr(proactive.db_history, "save_proactive_snapshot", fake_save)
    monkeypatch.setattr(proactive.orchestrator, "handle_message", fake_handle)

    await proactive._check_metrics()
    assert proactive._baseline_established is True
    assert len(saved) == 1
    assert saved[0][3] is False  # triggered=False
    assert handled == []


@pytest.mark.asyncio
async def test_check_metrics_skip_if_no_client(monkeypatch):
    monkeypatch.setattr(proactive.config, "PROACTIVE_METRIC_ENABLED", True)
    monkeypatch.setattr(proactive.config, "MCP_ENABLED", True)
    monkeypatch.setattr(proactive.config, "PROACTIVE_METRIC_SKIP_IF_NO_CLIENT", True)
    monkeypatch.setattr(proactive, "_baseline_established", True)
    monkeypatch.setattr(proactive, "_hourly_trigger_log", [])

    from api import ws_handler
    monkeypatch.setattr(ws_handler, "has_active_clients", lambda: False)

    polled = []

    async def fake_poll():
        polled.append("poll")
        return {"get_revenue": "100"}

    monkeypatch.setattr(proactive, "_poll_metrics", fake_poll)
    await proactive._check_metrics()
    assert polled == []


@pytest.mark.asyncio
async def test_rate_limit_caps_triggers(monkeypatch):
    import time as _time
    monkeypatch.setattr(proactive.config, "PROACTIVE_GLOBAL_MAX_PER_HOUR", 2)
    proactive._hourly_trigger_log = [_time.time(), _time.time()]
    assert (await proactive._rate_limit_ok()) is False
    proactive._hourly_trigger_log = []
    assert (await proactive._rate_limit_ok()) is True


def test_proactive_event_skips_tool_loop_source_regression():
    """Regression guard: handle_message must reference is_proactive and skip tool_loop."""
    import inspect
    from core import orchestrator as orch
    src = inspect.getsource(orch.handle_message)
    assert "is_proactive" in src
    assert 'event_type.startswith("proactive_")' in src
    # _tool_loop gated on not is_proactive
    assert "not is_proactive" in src
