import shutil
import subprocess
import numpy as np
import config
from core.logging import logger

_model = None

# 한국어 구두점/띄어쓰기 스타일만 유도. 구체 문장 금지 — 무음 입력 시 환각으로 재생됨.
_KO_INITIAL_PROMPT = "한국어 대화. 구두점과 띄어쓰기 포함."

_HALLUCINATION_BLOCKLIST = {
    "안녕하세요.",
    "오늘 날씨가 좋네요.",
    "코드를 작성하고 있어요.",
    "잠시만요, 생각 좀 할게요.",
    "한국어 대화.",
    "구두점과 띄어쓰기 포함.",
}

_SENTENCE_ENDINGS = ("다.", "요.", "까?", "죠.", "네.", "군.", "!", "?", ".")


def load_whisper():
    global _model
    if not shutil.which("ffmpeg"):
        logger.warning("[STT] ffmpeg 미설치. webm 디코딩 실패 예상")
    from faster_whisper import WhisperModel
    _model = WhisperModel(
        config.WHISPER_MODEL, device=config.WHISPER_DEVICE, compute_type=config.WHISPER_COMPUTE,
    )
    logger.info(f"[STT] Whisper {config.WHISPER_MODEL} 로드 완료 ({config.WHISPER_DEVICE})")

def _decode_to_pcm(audio_bytes: bytes) -> np.ndarray | None:
    try:
        proc = subprocess.run(
            ["ffmpeg", "-i", "pipe:0", "-ar", "16000", "-ac", "1", "-f", "s16le", "-loglevel", "error", "pipe:1"],
            input=audio_bytes, capture_output=True, timeout=15,
        )
        if proc.returncode != 0:
            logger.warning(f"[STT] ffmpeg 실패: {proc.stderr.decode()[:200]}")
            return None
        return np.frombuffer(proc.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    except Exception as e:
        logger.warning(f"[STT] 디코드 오류: {e}")
        return None


def _polish_sentence(text: str) -> str:
    text = text.strip()
    if not text:
        return ""
    if not text.endswith(_SENTENCE_ENDINGS):
        text += "."
    return text


def transcribe(audio_bytes: bytes) -> str:
    """음성 → 문장 단위 정제 텍스트. 빈 결과면 빈 문자열."""
    if _model is None:
        return ""
    pcm = _decode_to_pcm(audio_bytes)
    if pcm is None or len(pcm) == 0:
        return ""

    duration_sec = len(pcm) / 16000.0
    if duration_sec < 0.4:
        logger.info(f"[STT] 너무 짧음 ({duration_sec:.2f}s) — 무시")
        return ""

    segments, info = _model.transcribe(
        pcm,
        language="ko",
        beam_size=5,
        vad_filter=True,
        vad_parameters=dict(
            min_silence_duration_ms=500,
            speech_pad_ms=200,
            threshold=0.5,
        ),
        condition_on_previous_text=False,
        no_speech_threshold=0.7,
        compression_ratio_threshold=2.4,
        log_prob_threshold=-1.0,
        initial_prompt=_KO_INITIAL_PROMPT,
        word_timestamps=False,
    )

    sentences = [_polish_sentence(s.text) for s in segments]
    sentences = [s for s in sentences if s and s not in _HALLUCINATION_BLOCKLIST]

    if not sentences:
        logger.info(f"[STT] VAD 후 문장 없음 또는 환각 필터링 (duration={info.duration:.2f}s)")
        return ""

    joined = " ".join(sentences)
    logger.info(f"[STT] 문장 {len(sentences)}개 인식: {joined!r}")
    return joined
