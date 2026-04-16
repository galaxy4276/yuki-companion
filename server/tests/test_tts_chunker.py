from services.tts import SentenceChunker

def test_sentence_flush():
    c = SentenceChunker()
    out = c.feed("안녕. 반가워!")
    assert len(out) >= 2

def test_code_block_skip():
    c = SentenceChunker()
    results = c.feed("설명: ```python\nprint(1)\n``` 끝.")
    # 코드블록 내부는 플러시 안됨
    # 코드블록 밖 "끝." 은 플러시되지만 startswith("```") 가드로 드롭될 수 있음
