import time

_state = {
    "cwd": "",
    "last_command": "",
    "last_exit_code": None,
    "claude_task": "",
    "last_activity": time.time(),
}

def update(key: str, value):
    if key != "last_activity":
        _state[key] = value
    _state["last_activity"] = time.time()

def get() -> dict:
    return dict(_state)

def idle_seconds() -> float:
    return time.time() - _state["last_activity"]
