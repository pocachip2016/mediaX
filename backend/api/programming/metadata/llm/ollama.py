"""Ollama 로컬 LLM 프로바이더"""

import httpx
from shared.config import settings
from .base import AbstractLLMProvider


class OllamaProvider(AbstractLLMProvider):

    def __init__(self):
        self._url = getattr(settings, "OLLAMA_URL", "http://localhost:11434")
        self._model = getattr(settings, "OLLAMA_MODEL", "llama3.2:3b")

    @property
    def engine_name(self) -> str:
        return self._model  # 예: "llama3.2:3b"

    async def generate(self, prompt: str, system: str = "") -> str:
        payload = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 800},
        }
        if system:
            payload["system"] = system

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{self._url}/api/generate", json=payload)
            resp.raise_for_status()
            return resp.json().get("response", "")
