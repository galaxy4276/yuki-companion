import base64
import re
import httpx
import config
from core.logging import logger

_client = httpx.AsyncClient(timeout=60.0)
_SENTENCE_END = re.compile(r'[.!?。?!…]\s*')
MAX_CHUNK_CHARS = 200

async def synthesize(text: str) -> bytes | None:
    try:
        resp = await _client.post(
            f"{config.TTS_URL}/v1/audio/speech",
            json={"input": text, "voice": "Sohee", "response_format": "wav"},
        )
        if resp.status_code == 200:
            return resp.content
    except Exception as e:
        logger.warning(f"[TTS] 오류: {e}")
    return None

def to_base64(wav_bytes: bytes) -> str:
    return base64.b64encode(wav_bytes).decode()

class SentenceChunker:
    """LLM 스트림 청크 누적 + 문장/상한/코드블록 경계에서 flush."""
    def __init__(self):
        self.buffer = ""
        self.in_code_block = False
        self._backtick_run = 0

    def feed(self, chunk: str) -> list[str]:
        """chunk 주입 후 flush 준비된 문장 리스트 반환."""
        out: list[str] = []
        for ch in chunk:
            self.buffer += ch
            if ch == '`':
                self._backtick_run += 1
                if self._backtick_run == 3:
                    self.in_code_block = not self.in_code_block
                    self._backtick_run = 0
            else:
                self._backtick_run = 0

            if self.in_code_block:
                continue

            if _SENTENCE_END.search(self.buffer[-2:]) or len(self.buffer) >= MAX_CHUNK_CHARS:
                flushed = self.buffer.strip()
                if flushed and not flushed.startswith("```"):
                    out.append(flushed)
                self.buffer = ""
        return out

    def finalize(self) -> str | None:
        rest = self.buffer.strip()
        self.buffer = ""
        if rest and not rest.startswith("```") and not self.in_code_block:
            return rest
        return None

def strip_code_blocks(text: str) -> str:
    """요약 등에서 코드블록 제거."""
    return re.sub(r"```[\s\S]*?```", "", text)
