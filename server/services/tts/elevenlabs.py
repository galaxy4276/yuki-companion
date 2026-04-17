import httpx

from .base import SpeechSynthesizer


class ElevenLabsTTS(SpeechSynthesizer):
    """ElevenLabs Text-to-Speech.

    multilingual_v2 / turbo_v2_5 모델은 한국어 자연스럽게 합성.
    output_format=pcm_24000 → 24kHz 16-bit PCM, WAV 헤더 추가해 반환.
    """

    name = "elevenlabs"
    BASE = "https://api.elevenlabs.io/v1"

    def __init__(self, api_key: str, voice_id: str, model_id: str = "eleven_multilingual_v2",
                 stability: float = 0.5, similarity: float = 0.75, style: float = 0.0,
                 timeout: float = 30.0):
        self._api_key = api_key
        self._voice_id = voice_id
        self._model_id = model_id
        self._voice_settings = {
            "stability": stability,
            "similarity_boost": similarity,
            "style": style,
            "use_speaker_boost": True,
        }
        self._client = httpx.AsyncClient(timeout=timeout)

    async def synthesize(self, text: str) -> bytes | None:
        try:
            resp = await self._client.post(
                f"{self.BASE}/text-to-speech/{self._voice_id}",
                params={"output_format": "pcm_24000"},
                headers={
                    "xi-api-key": self._api_key,
                    "Content-Type": "application/json",
                    "Accept": "audio/pcm",
                },
                json={
                    "text": text,
                    "model_id": self._model_id,
                    "voice_settings": self._voice_settings,
                },
            )
            if resp.status_code == 200:
                return _wrap_pcm_as_wav(resp.content, sample_rate=24000)
        except Exception:
            return None
        return None


def _wrap_pcm_as_wav(pcm: bytes, sample_rate: int = 24000, channels: int = 1, sample_width: int = 2) -> bytes:
    """raw PCM16 → WAV (RIFF). 클라이언트 audioCtx.decodeAudioData가 WAV만 받음."""
    import struct
    byte_rate = sample_rate * channels * sample_width
    block_align = channels * sample_width
    data_size = len(pcm)
    return (
        b"RIFF"
        + struct.pack("<I", 36 + data_size)
        + b"WAVEfmt "
        + struct.pack("<IHHIIHH", 16, 1, channels, sample_rate, byte_rate, block_align, sample_width * 8)
        + b"data"
        + struct.pack("<I", data_size)
        + pcm
    )
