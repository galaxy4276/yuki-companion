import time
import config

_state = {
    "cwd": "",
    "last_command": "",
    "last_exit_code": None,
    "claude_task": "",
    "last_activity": time.time(),
}

_screenshot: dict = {"data": None, "ts": 0.0}

def touch():
    """활동 발생 시 호출, last_activity만 갱신."""
    _state["last_activity"] = time.time()

def update(key: str, value):
    """일반 상태 갱신. last_activity는 자동 갱신 안함."""
    if key == "last_activity":
        raise ValueError("use touch() instead")
    _state[key] = value

def get() -> dict:
    return dict(_state)

def idle_seconds() -> float:
    return time.time() - _state["last_activity"]

def set_screenshot(data: bytes):
    _screenshot["data"] = data
    _screenshot["ts"] = time.time()

def get_screenshot() -> bytes | None:
    if _screenshot["data"] is None:
        return None
    if time.time() - _screenshot["ts"] > config.SCREENSHOT_TTL_SECONDS:
        _screenshot["data"] = None
        return None
    return _screenshot["data"]

def clear_screenshot():
    _screenshot["data"] = None
