import httpx

from .base import SpeechSynthesizer


class QwenTTS(SpeechSynthesizer):
    name = "qwen"

    def __init__(self, url: str, voice: str, username: str, password: str, timeout: float = 60.0):
        self._url = url
        self._voice = voice
        self._client = httpx.AsyncClient(timeout=timeout, auth=httpx.BasicAuth(username, password))

    async def synthesize(self, text: str) -> bytes | None:
        try:
            resp = await self._client.post(
                f"{self._url}/v1/audio/speech",
                json={"input": text, "voice": self._voice, "response_format": "wav"},
            )
            if resp.status_code == 200:
                return resp.content
        except Exception:
            return None
        return None
