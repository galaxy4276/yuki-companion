import io
import config

_model = None

def load_whisper():
    global _model
    from faster_whisper import WhisperModel
    _model = WhisperModel(
        config.WHISPER_MODEL,
        device=config.WHISPER_DEVICE,
        compute_type=config.WHISPER_COMPUTE,
    )
    print(f"[STT] Whisper {config.WHISPER_MODEL} 로드 완료 ({config.WHISPER_DEVICE})")

def transcribe(audio_bytes: bytes) -> str:
    if _model is None:
        return ""
    segments, _ = _model.transcribe(io.BytesIO(audio_bytes), language="ko", beam_size=5)
    return "".join(s.text for s in segments).strip()
