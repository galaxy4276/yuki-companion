import pytest
from core import context

def test_touch_updates_last_activity():
    before = context.get()["last_activity"]
    context.touch()
    assert context.get()["last_activity"] >= before

def test_update_does_not_touch():
    context.update("cwd", "/tmp")
    assert context.get()["cwd"] == "/tmp"

def test_update_last_activity_raises():
    with pytest.raises(ValueError):
        context.update("last_activity", 0)
