"""
TranslateSynopsisTask — 줄거리 ko↔en 번역 (ADR-007 Phase1 첫 task)

동작:
  - cp_synopsis 또는 ai_synopsis에서 소스 텍스트 확인
  - 한국어 문자 비율로 언어 감지 (>20% CJK → ko, 나머지 → en)
  - synopsis_ko/synopsis_en 중 미채워진 방향으로 번역
  - 둘 다 이미 채워져 있으면 None 반환 → Runner skip
"""

from __future__ import annotations

import re
import logging
from typing import TYPE_CHECKING

from api.programming.metadata.ai_tasks.base import AiTask, TaskInput, TaskOutput

if TYPE_CHECKING:
    from api.programming.metadata.models import ContentMetadata

logger = logging.getLogger(__name__)

_CJK_RANGE = re.compile(r"[぀-ヿ㐀-䶿一-鿿가-퟿]")

_SYSTEM_PROMPT = (
    "You are a professional translator. Translate the given text accurately and naturally. "
    "Return ONLY the translated text with no explanation or commentary."
)


def _detect_language(text: str) -> str:
    """'ko' 또는 'en' 반환. CJK 문자 비율 20% 초과 시 ko."""
    if not text:
        return "en"
    cjk_count = len(_CJK_RANGE.findall(text))
    return "ko" if cjk_count / len(text) > 0.2 else "en"


def _get_source_synopsis(meta: "ContentMetadata") -> str | None:
    """우선순위: cp_synopsis → ai_synopsis → None."""
    return meta.cp_synopsis or meta.ai_synopsis or None


class TranslateSynopsisTask(AiTask):
    name = "translate_synopsis"

    def build_input(self, meta: "ContentMetadata") -> TaskInput | None:
        source = _get_source_synopsis(meta)
        if not source or len(source.strip()) < 10:
            return None

        lang = _detect_language(source)

        if lang == "ko":
            if meta.synopsis_ko and meta.synopsis_en:
                return None  # 이미 양쪽 채워짐
            if not meta.synopsis_ko:
                # 원본을 synopsis_ko에 세팅 (번역 전 메모)
                pass
            target_lang = "English"
            direction = "ko_to_en"
        else:
            if meta.synopsis_ko and meta.synopsis_en:
                return None
            target_lang = "Korean"
            direction = "en_to_ko"

        return TaskInput(
            content_id=meta.content_id,
            task_name=self.name,
            payload={
                "source_text": source[:2000],  # 최대 2000자 (토큰 절약)
                "source_lang": lang,
                "target_lang": target_lang,
                "direction": direction,
            },
        )

    async def run(self, task_input: TaskInput, provider_chain: list) -> TaskOutput:
        payload = task_input.payload
        prompt = (
            f"Translate the following text to {payload['target_lang']}:\n\n"
            f"{payload['source_text']}"
        )

        last_exc: Exception | None = None
        for ProviderClass in provider_chain:
            try:
                provider = ProviderClass()
                translated = await provider.generate(prompt, _SYSTEM_PROMPT)
                translated = translated.strip()
                return TaskOutput(
                    result={
                        "translated": translated,
                        "direction": payload["direction"],
                        "source_lang": payload["source_lang"],
                    },
                    engine=provider.engine_name,
                )
            except Exception as exc:
                logger.warning("[translate_synopsis] %s 실패: %s", ProviderClass.__name__, exc)
                last_exc = exc

        raise ValueError(f"translate_synopsis: 모든 LLM 엔진 실패: {last_exc}")

    def apply(self, meta: "ContentMetadata", output: TaskOutput) -> None:
        result = output.result
        direction = result.get("direction", "")
        translated = result.get("translated", "")

        source = _get_source_synopsis(meta)
        source_lang = result.get("source_lang", "en")

        if direction == "ko_to_en":
            if not meta.synopsis_ko:
                meta.synopsis_ko = source
            meta.synopsis_en = translated
        else:  # en_to_ko
            if not meta.synopsis_en:
                meta.synopsis_en = source
            meta.synopsis_ko = translated

        logger.info("[translate_synopsis] content_id=%d direction=%s", meta.content_id, direction)


translate_synopsis_task = TranslateSynopsisTask()
