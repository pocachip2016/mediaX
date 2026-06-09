"""Ollama 로컬 LLM 프로바이더"""

import httpx
from shared.config import settings
from .base import AbstractLLMProvider


class OllamaProvider(AbstractLLMProvider):

    def __init__(self, model: str | None = None):
        self._url = getattr(settings, "OLLAMA_URL", "http://localhost:11434")
        self._model = model or getattr(settings, "OLLAMA_MODEL", "llama3.2:3b")

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


class OllamaEmbeddingsProvider:
    """Ollama /api/embeddings 호출 — bge-m3 1024-dim 벡터 반환."""

    EMBED_MODEL = "bge-m3"

    def __init__(self):
        self._url = getattr(settings, "OLLAMA_URL", "http://localhost:11434")

    async def embed(self, text: str) -> list[float]:
        """텍스트를 1024-dim float 벡터로 반환. Ollama 미응답 시 빈 리스트."""
        if not text or not text.strip():
            return []
        payload = {"model": self.EMBED_MODEL, "prompt": text}
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(f"{self._url}/api/embeddings", json=payload)
                resp.raise_for_status()
                return resp.json().get("embedding", [])
        except Exception:
            return []


class OllamaTaskProvider(OllamaProvider):
    """
    AI Task(번역/요약/분류) 전용 Ollama 프로바이더.
    OLLAMA_TASK_MODEL(경량 instruct, 예: qwen2.5:3b)을 사용 —
    reasoning 모델(qwen3:4b)이 단순 작업에서 추론을 출력에 흘리는 문제 회피.
    """

    def __init__(self):
        super().__init__(model=getattr(settings, "OLLAMA_TASK_MODEL", "qwen2.5:3b"))
