from services.tts import SentenceChunker

def test_sentence_flush():
    c = SentenceChunker()
    out = c.feed("안녕. 반가워!")
    assert len(out) >= 2

def test_code_block_skip():
    c = SentenceChunker()
    inside = c.feed("설명: ```python\nprint(1)\n``` 끝.")
    tail = c.finalize()
    flushed = inside + ([tail] if tail else [])
    assert not any("print(1)" in s for s in flushed)
    assert any("끝" in s for s in flushed)

def test_max_chunk_chars_flush():
    c = SentenceChunker()
    long_text = "가" * 250
    out = c.feed(long_text)
    assert out, "200자 상한 도달 시 flush 되어야 함"

def test_finalize_drops_unterminated_code_block():
    c = SentenceChunker()
    c.feed("코드: ```python\nprint(1)")
    assert c.finalize() is None
