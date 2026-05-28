"""
큐레이션 카피 LLM 제안 모듈.

theme_features + OTT 섹션명을 바탕으로 Gemini→Groq→Ollama 폴백 체인으로
마케팅 카피(headline_copy/sub_copy) 후보를 생성한다.

LLM 전체 실패 시 섹션명을 external_imported 후보로 반환 (graceful degradation).
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from shared.config import settings
from api.programming.metadata.llm import get_provider_chain

logger = logging.getLogger(__name__)

AI_ENGINE: str = getattr(settings, "AI_ENGINE", "gemini")

_SYSTEM_PROMPT = (
    "당신은 한국 VOD 플랫폼의 큐레이션 카피라이터입니다. "
    "주어진 테마 특징과 외부 참고 섹션명을 바탕으로 "
    "매력적인 한국어 마케팅 카피를 작성하세요."
)


def _build_prompt(
    theme_features: dict[str, Any],
    section_names: list[str],
    limit: int,
) -> str:
    genres = theme_features.get("genres") or []
    moods = theme_features.get("moods") or []
    keywords = theme_features.get("free_keywords") or []
    era = ""
    if theme_features.get("era_from") or theme_features.get("era_to"):
        era = f"{theme_features.get('era_from', '?')}~{theme_features.get('era_to', '?')}년대"
    runtime = ""
    if theme_features.get("runtime_min") or theme_features.get("runtime_max"):
        runtime = f"{theme_features.get('runtime_min', '?')}~{theme_features.get('runtime_max', '?')}분"

    lines = ["테마 특징:"]
    if genres:
        lines.append(f"  장르: {', '.join(genres)}")
    if moods:
        lines.append(f"  무드: {', '.join(moods)}")
    if era:
        lines.append(f"  시대: {era}")
    if runtime:
        lines.append(f"  런타임: {runtime}")
    if keywords:
        lines.append(f"  키워드: {', '.join(keywords)}")

    refs_line = ""
    if section_names:
        refs_line = "\n외부 참고 섹션명:\n" + "\n".join(f"  - {n}" for n in section_names)

    return f"""\
{chr(10).join(lines)}{refs_line}

위 정보를 바탕으로 마케팅 카피 후보를 {limit}개 생성하세요.
반드시 아래 JSON 배열 형식으로만 응답하세요:

```json
[
  {{
    "headline_copy": "짧고 강렬한 헤드라인 카피 (30자 이내)",
    "sub_copy": "부가 설명 한 줄 (60자 이내, 선택)",
    "reasoning": "이 카피를 선택한 이유 (선택)"
  }}
]
```

- 한국어로 작성
- 콘텐츠 특성이 느껴지는 자연스러운 문장
- 각 후보는 서로 다른 스타일(감성적/액션/호기심 유발 등)"""


def _extract_json_array(text: str) -> list[dict]:
    """LLM 응답 텍스트에서 JSON 배열 추출."""
    match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    return []


def _section_names_as_fallback(section_names: list[str], limit: int) -> list[dict]:
    """LLM 실패 시 OTT 섹션명을 external_imported 후보로 반환."""
    candidates = []
    for i, name in enumerate(section_names[:limit], start=1):
        candidates.append({
            "rank": i,
            "headline_copy": name,
            "sub_copy": None,
            "source": "external_imported",
            "reasoning": None,
        })
    return candidates


async def propose_copy(
    theme_features: dict[str, Any],
    selected_section_names: list[str],
    limit: int = 3,
) -> tuple[list[dict], str]:
    """
    LLM 폴백 체인으로 카피 후보를 생성한다.

    반환: (candidates_list, engine_used)
      - candidates_list: [{rank, headline_copy, sub_copy, source, reasoning}, ...]
      - engine_used: 실제 사용된 엔진명 ("gemini-2.5-flash-lite", "llama3.2:3b" 등)
                     LLM 전체 실패 시 "external_fallback", 후보 없으면 "none"
    """
    if not theme_features and not selected_section_names:
        return [], "none"

    prompt = _build_prompt(theme_features, selected_section_names, limit)
    chain = get_provider_chain(AI_ENGINE)

    for ProviderClass in chain:
        try:
            provider = ProviderClass()
            raw = await provider.generate(prompt, _SYSTEM_PROMPT)
            parsed = _extract_json_array(raw)
            if not parsed:
                logger.warning("[copy_proposer] %s: JSON 파싱 실패", ProviderClass.__name__)
                continue

            candidates = []
            for i, item in enumerate(parsed[:limit], start=1):
                candidates.append({
                    "rank": i,
                    "headline_copy": str(item.get("headline_copy", "")).strip(),
                    "sub_copy": item.get("sub_copy") or None,
                    "source": "ai_proposed",
                    "reasoning": item.get("reasoning") or None,
                })
            if candidates:
                logger.info("[copy_proposer] 엔진 사용: %s, 후보 %d개", provider.engine_name, len(candidates))
                return candidates, provider.engine_name

        except Exception as exc:
            logger.warning("[copy_proposer] %s 실패 → 폴백: %s", ProviderClass.__name__, exc)

    # 모든 LLM 실패 → OTT 섹션명으로 대체
    fallback = _section_names_as_fallback(selected_section_names, limit)
    if fallback:
        logger.info("[copy_proposer] LLM 전체 실패 → external_fallback %d개", len(fallback))
        return fallback, "external_fallback"

    return [], "none"
