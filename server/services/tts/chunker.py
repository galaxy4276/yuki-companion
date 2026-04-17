_SENTENCE_END_CHARS = ('.', '!', '?', '。', '？', '！', '…')
MAX_CHUNK_CHARS = 200


class SentenceChunker:
    """LLM 스트림 청크 누적 + 문장/상한/코드블록 경계에서 flush.

    코드블록(```...```) 내부 텍스트는 TTS에서 완전히 제외.
    진입 시 이전까지 누적된 평문을 즉시 flush, 종료 시 내부 텍스트 폐기.
    """

    def __init__(self):
        self._parts: list[str] = []
        self.in_code_block = False
        self._backtick_run = 0

    def _flush_outside(self) -> str | None:
        if not self._parts:
            return None
        buf = "".join(self._parts).strip()
        self._parts = []
        return buf or None

    def feed(self, chunk: str) -> list[str]:
        out: list[str] = []
        for ch in chunk:
            if ch == '`':
                self._backtick_run += 1
            else:
                self._backtick_run = 0

            if not self.in_code_block:
                self._parts.append(ch)

            if self._backtick_run == 3:
                if self.in_code_block:
                    self.in_code_block = False
                else:
                    self._parts = self._parts[:-3]
                    flushed = self._flush_outside()
                    if flushed:
                        out.append(flushed)
                    self.in_code_block = True
                self._backtick_run = 0
                continue

            if self.in_code_block:
                continue

            if ch in _SENTENCE_END_CHARS or len(self._parts) >= MAX_CHUNK_CHARS:
                flushed = self._flush_outside()
                if flushed:
                    out.append(flushed)
        return out

    def finalize(self) -> str | None:
        if self.in_code_block:
            self._parts = []
            return None
        return self._flush_outside()
