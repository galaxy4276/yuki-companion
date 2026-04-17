from abc import ABC, abstractmethod


class SpeechSynthesizer(ABC):
    """단일 책임: 텍스트 → wav bytes. 실패 시 None.

    구현체는 외부 API/모델 차이를 캡슐화한다. 호출자는 실패 처리만 신경쓴다
    (best-effort 계약: 예외 던지지 않음).
    """

    name: str = "base"

    @abstractmethod
    async def synthesize(self, text: str) -> bytes | None:
        ...
