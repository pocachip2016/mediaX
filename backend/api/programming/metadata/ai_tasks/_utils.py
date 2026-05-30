"""AI Task 공용 유틸리티"""

from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger(__name__)

_JSON_BLOCK = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)
_JSON_OBJ = re.compile(r"\{[\s\S]*\}", re.DOTALL)
_JSON_ARR = re.compile(r"\[[\s\S]*\]", re.DOTALL)


def extract_json(text: str) -> dict | list | None:
    """LLM 응답 텍스트에서 JSON 객체 또는 배열 추출."""
    # 1. 코드 블록 내 JSON
    m = _JSON_BLOCK.search(text)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 2. 객체 패턴
    m = _JSON_OBJ.search(text)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass

    # 3. 배열 패턴
    m = _JSON_ARR.search(text)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass

    return None


async def call_with_chain(
    prompt: str,
    system: str,
    provider_chain: list,
) -> tuple[str, str]:
    """
    provider_chain 순서대로 LLM 호출. 성공 시 (응답 텍스트, engine_name) 반환.
    모든 실패 시 ValueError raise.
    """
    last_exc: Exception | None = None
    for ProviderClass in provider_chain:
        try:
            provider = ProviderClass()
            text = await provider.generate(prompt, system)
            return text.strip(), provider.engine_name
        except Exception as exc:
            logger.warning("[ai_task] %s 실패: %s", ProviderClass.__name__, exc)
            last_exc = exc
    raise ValueError(f"모든 LLM 엔진 실패: {last_exc}")
