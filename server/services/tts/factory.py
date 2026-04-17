import config
from core.logging import logger

from .base import SpeechSynthesizer
from .qwen import QwenTTS
from .elevenlabs import ElevenLabsTTS


def create_synthesizer() -> SpeechSynthesizer:
    provider = (config.TTS_PROVIDER or "qwen").lower()
    if provider == "elevenlabs":
        if not config.ELEVENLABS_API_KEY:
            logger.warning("[TTS] ELEVENLABS_API_KEY 없음 → Qwen 폴백")
            return _qwen()
        logger.info(f"[TTS] provider=elevenlabs voice={config.ELEVENLABS_VOICE_ID} model={config.ELEVENLABS_MODEL_ID}")
        return ElevenLabsTTS(
            api_key=config.ELEVENLABS_API_KEY,
            voice_id=config.ELEVENLABS_VOICE_ID,
            model_id=config.ELEVENLABS_MODEL_ID,
        )
    return _qwen()


def _qwen() -> SpeechSynthesizer:
    logger.info(f"[TTS] provider=qwen voice={config.TTS_VOICE}")
    return QwenTTS(
        url=config.TTS_URL,
        voice=config.TTS_VOICE,
        username=config.TTS_USERNAME,
        password=config.TTS_PASSWORD,
    )
