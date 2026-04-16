import shutil
import subprocess
import numpy as np
import config

_model = None

def load_whisper():
    global _model
    if not shutil.which("ffmpeg"):
        print("[STT] WARNING: ffmpeg 미설치. webm 디코딩 실패 예상")
    from faster_whisper import WhisperModel
    _model = WhisperModel(
        config.WHISPER_MODEL, device=config.WHISPER_DEVICE, compute_type=config.WHISPER_COMPUTE,
    )
    print(f"[STT] Whisper {config.WHISPER_MODEL} 로드 완료 ({config.WHISPER_DEVICE})")

def _decode_to_pcm(audio_bytes: bytes) -> np.ndarray | None:
    try:
        proc = subprocess.run(
            ["ffmpeg", "-i", "pipe:0", "-ar", "16000", "-ac", "1", "-f", "s16le", "-loglevel", "error", "pipe:1"],
            input=audio_bytes, capture_output=True, timeout=15,
        )
        if proc.returncode != 0:
            print(f"[STT] ffmpeg 실패: {proc.stderr.decode()[:200]}")
            return None
        return np.frombuffer(proc.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    except Exception as e:
        print(f"[STT] 디코드 오류: {e}")
        return None

def transcribe(audio_bytes: bytes) -> str:
    if _model is None:
        return ""
    pcm = _decode_to_pcm(audio_bytes)
    if pcm is None or len(pcm) == 0:
        return ""
    segments, _info = _model.transcribe(pcm, language="ko", beam_size=5)
    return "".join(s.text for s in segments).strip()
