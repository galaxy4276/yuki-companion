from services.persona import classify_emotion

def test_happy():
    assert classify_emotion("성공했어 축하")[0] == "happy"

def test_worried():
    assert classify_emotion("에러 났어")[0] == "worried"

def test_idle_default():
    assert classify_emotion("ㅇㅇ")[0] == "idle"
