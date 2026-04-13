"""Google Gemini 2.0 Flash 프로바이더 (google-genai SDK)"""

import logging
from shared.config import settings
from .base import AbstractLLMProvider

logger = logging.getLogger(__name__)


class GeminiProvider(AbstractLLMProvider):
    MODEL_ID = "gemini-2.5-flash-lite"

    def __init__(self):
        api_key = getattr(settings, "GOOGLE_API_KEY", "")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY가 설정되지 않았습니다")
        try:
            from google import genai
            self._client = genai.Client(api_key=api_key)
        except ImportError:
            raise ImportError("google-genai 패키지가 설치되지 않았습니다. pip install google-genai")

    @property
    def engine_name(self) -> str:
        return self.MODEL_ID  # "gemini-2.0-flash"

    async def generate(self, prompt: str, system: str = "") -> str:
        from google import genai
        from google.genai import types

        contents = []
        if system:
            # system instruction을 첫 번째 user turn으로 전달
            contents.append(f"{system}\n\n{prompt}")
        else:
            contents.append(prompt)

        response = await self._client.aio.models.generate_content(
            model=self.MODEL_ID,
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=2048,
            ),
        )
        return response.text
