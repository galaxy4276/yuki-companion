import time
from core import context
import config

def test_screenshot_set_get():
    context.clear_screenshot()
    context.set_screenshot(b"fake")
    assert context.get_screenshot() == b"fake"
    context.clear_screenshot()
    assert context.get_screenshot() is None

def test_screenshot_ttl_expiry(monkeypatch):
    context.clear_screenshot()
    context.set_screenshot(b"fake")
    monkeypatch.setattr(config, "SCREENSHOT_TTL_SECONDS", 0)
    time.sleep(0.01)
    assert context.get_screenshot() is None
