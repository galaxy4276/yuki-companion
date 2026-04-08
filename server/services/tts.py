import base64
import httpx
import config

_client = httpx.AsyncClient(timeout=60.0)

async def synthesize(text: str) -> bytes | None:
    try:
        resp = await _client.post(
            f"{config.TTS_URL}/v1/audio/speech",
            json={"input": text, "voice": "Sohee", "response_format": "wav"},
        )
        if resp.status_code == 200:
            return resp.content
    except Exception as e:
        print(f"[TTS] 오류: {e}")
    return None

def to_base64(wav_bytes: bytes) -> str:
    return base64.b64encode(wav_bytes).decode()
