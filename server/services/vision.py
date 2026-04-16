import base64
import shutil
import subprocess
import config
from core.logging import logger
from core import context

def _ocr(image_bytes: bytes) -> str:
    if not shutil.which("tesseract"):
        logger.warning("[Vision] tesseract 미설치")
        return ""
    try:
        proc = subprocess.run(
            ["tesseract", "stdin", "stdout", "-l", config.OCR_LANGUAGES],
            input=image_bytes, capture_output=True, timeout=30,
        )
        return proc.stdout.decode("utf-8", errors="ignore").strip()
    except Exception as e:
        logger.warning(f"[Vision] OCR 오류: {e}")
        return ""

def prepare(messages: list[dict]) -> list[dict]:
    """최신 스크린샷 있으면 messages에 주입. 호출 직후 clear."""
    img = context.get_screenshot()
    if not img:
        return messages
    try:
        if config.VISION_MODEL_CAPABLE:
            b64 = base64.b64encode(img).decode()
            messages = messages + [{
                "role": "user",
                "content": [
                    {"type": "text", "text": "아래 화면을 참고해서 답해."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                ],
            }]
        else:
            text = _ocr(img)
            if text:
                messages = messages + [{
                    "role": "system",
                    "content": f"[SCREEN OCR]\n{text[:2000]}\n[/SCREEN]"
                }]
    finally:
        context.clear_screenshot()
    return messages
