"""TTS facade.

기존 호출자는 `services.tts.synthesize`, `services.tts.to_base64`,
`services.tts.SentenceChunker` 사용. 본 모듈이 그 시그니처를 유지하면서
provider 교체와 EventBus emit을 캡슐화한다 (ISP — provider는 emit 모름).
"""
import base64
import time

from core import events
from core.events import since_ms

from .base import SpeechSynthesizer
from .chunker import SentenceChunker
from .factory import create_synthesizer

_synth: SpeechSynthesizer = create_synthesizer()


async def synthesize(text: str) -> bytes | None:
    t0 = time.time()
    await events.emit("tts.request", {"text": text, "provider": _synth.name, "len": len(text)})
    wav = await _synth.synthesize(text)
    if wav:
        await events.emit("tts.response", {"bytes": len(wav), "duration_ms": since_ms(t0), "len": len(text), "provider": _synth.name})
    else:
        await events.emit("tts.fail", {"text": text, "duration_ms": since_ms(t0), "provider": _synth.name})
    return wav


def to_base64(wav_bytes: bytes) -> str:
    return base64.b64encode(wav_bytes).decode()


__all__ = ["synthesize", "to_base64", "SentenceChunker", "SpeechSynthesizer"]
