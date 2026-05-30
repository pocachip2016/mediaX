"""
LLM 멀티 프로바이더 패키지

AI_ENGINE 환경변수로 사용 엔진 선택:
  gemini  → Gemini 1.5 Flash (기본값, 한국어 최적)
  groq    → llama-3.3-70b-versatile (빠른 무료 추론)
  ollama  → llama3.2:3b 로컬 (Docker 필요)

폴백 순서: 지정 엔진 → 나머지 2개 순서대로
"""

from .base import AbstractLLMProvider
from .gemini import GeminiProvider
from .groq import GroqProvider
from .ollama import OllamaProvider, OllamaTaskProvider

# AI_ENGINE 값 → 프로바이더 클래스 우선순위 목록
_PROVIDER_ORDER: dict[str, list[type[AbstractLLMProvider]]] = {
    "gemini": [GeminiProvider, GroqProvider, OllamaProvider],
    "groq":   [GroqProvider, GeminiProvider, OllamaProvider],
    "ollama": [OllamaProvider, GeminiProvider, GroqProvider],
}


def get_provider_chain(engine: str) -> list[type[AbstractLLMProvider]]:
    """AI_ENGINE 값에 따른 프로바이더 클래스 목록 반환 (폴백 순서)"""
    return _PROVIDER_ORDER.get(engine.lower(), _PROVIDER_ORDER["gemini"])


def get_task_provider_chain() -> list[type[AbstractLLMProvider]]:
    """
    AI Task(번역/요약/분류) 전용 프로바이더 체인.
    로컬 경량 instruct 모델(OllamaTaskProvider) 우선 → 클라우드 폴백.
    """
    return [OllamaTaskProvider, GeminiProvider, GroqProvider]


__all__ = [
    "AbstractLLMProvider",
    "GeminiProvider",
    "GroqProvider",
    "OllamaProvider",
    "OllamaTaskProvider",
    "get_provider_chain",
    "get_task_provider_chain",
]
