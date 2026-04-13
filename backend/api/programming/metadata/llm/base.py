"""LLM 프로바이더 추상 기반 클래스"""

from abc import ABC, abstractmethod


class AbstractLLMProvider(ABC):
    """모든 LLM 프로바이더의 공통 인터페이스"""

    @property
    @abstractmethod
    def engine_name(self) -> str:
        """ContentAIResult.engine 컬럼에 저장될 식별자 (예: 'gemini-1.5-flash')"""
        ...

    @abstractmethod
    async def generate(self, prompt: str, system: str = "") -> str:
        """
        프롬프트를 받아 텍스트 응답 반환.
        실패 시 예외 raise — 폴백 로직은 호출측에서 처리.
        """
        ...
