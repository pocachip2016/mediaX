"""Groq 프로바이더 — llama-3.3-70b-versatile (무료 티어)"""

import logging
from shared.config import settings
from .base import AbstractLLMProvider

logger = logging.getLogger(__name__)


class GroqProvider(AbstractLLMProvider):
    MODEL_ID = "llama-3.3-70b-versatile"

    def __init__(self):
        api_key = getattr(settings, "GROQ_API_KEY", "")
        if not api_key:
            raise ValueError("GROQ_API_KEY가 설정되지 않았습니다")
        try:
            from groq import AsyncGroq
            self._client = AsyncGroq(api_key=api_key)
        except ImportError:
            raise ImportError("groq 패키지가 설치되지 않았습니다. pip install groq")

    @property
    def engine_name(self) -> str:
        return self.MODEL_ID  # "llama-3.3-70b-versatile"

    async def generate(self, prompt: str, system: str = "") -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        chat = await self._client.chat.completions.create(
            model=self.MODEL_ID,
            messages=messages,
            temperature=0.3,
            max_tokens=1000,
        )
        return chat.choices[0].message.content or ""
