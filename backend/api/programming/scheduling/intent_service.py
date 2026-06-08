"""intent_service.py — Tier1 자연어 의도 해석.

interpret_intent(text) → IntentResult(rule_query, facets)

- provider chain으로 LLM 호출 → 통제어휘 facets + rule_query 출력
- 자유서술 금지: facets는 반드시 scheduling/facets.py VOCAB 기준 검증
- LLM 완전 실패 시 Tier0 폴백 (빈 rule_query + 빈 facets)
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from api.programming.metadata.llm import get_task_provider_chain
from api.programming.scheduling.facets import validate_facets

logger = logging.getLogger(__name__)

_INTENT_SYSTEM = """\
당신은 한국 VOD 편성 기획 AI입니다.
운영자의 의도 설명을 읽고, 아래 JSON 스키마에 맞게만 응답하세요.
다른 텍스트는 절대 출력하지 마세요.

[rule_query 필드 (Tier0 필터)]
- genre: GenreCode.code 문자열 또는 배열 (예: "DRM", ["ROM","COM"])
- year_gte / year_lte: 연도 정수
- country: 국가 부분 일치 문자열 (예: "한국", "미국")
- content_type: "movie" | "series" | "season" | "episode"
- approved_only: true/false
해당 없으면 해당 키 생략.

[facets 필드 (통제어휘 — 이 목록 외 값 사용 금지)]
- mood: 경쾌|감성|긴장|따뜻|어두움|코믹|로맨틱|비장
- occasion: 주말|가족시청|심야|명절|연말|비오는날|몰아보기
- audience: 아동|청소년|성인|가족|시니어
- tempo: 느림|보통|빠름
- tone: 진지|가벼움|풍자|다큐멘터리
- themes: 성장|복수|우정|가족|생존|범죄|사랑|전쟁|음모
- setting.era: 현대|시대극|근미래|중세|고대
- setting.place: 한국|미국|일본|유럽|가상

[출력 형식]
{"rule_query": {...}, "facets": {"mood": [...], "occasion": [...], "audience": [...], "tempo": [...], "tone": [...], "themes": [...], "setting": {"era": [...], "place": [...]}}}
"""


@dataclass
class IntentResult:
    rule_query: dict = field(default_factory=dict)
    facets: dict = field(default_factory=dict)
    provider_used: str = "tier0_fallback"
    raw_llm: str = ""


async def interpret_intent(text: str) -> IntentResult:
    """자연어 의도 → IntentResult(rule_query, facets).

    LLM 파싱 실패 시 Tier0 폴백(빈 rule_query, 빈 facets) 반환.
    """
    if not text or not text.strip():
        return IntentResult()

    providers = get_task_provider_chain()
    prompt = (
        f"운영자 의도: {text.strip()}\n\n"
        "위 의도를 분석해 아래 형식의 JSON만 출력 (다른 텍스트 없이):\n"
        '{"rule_query": {"genre": "...", "country": "...", "year_gte": 0, "approved_only": true}, '
        '"facets": {"mood": ["..."], "occasion": ["..."], "audience": ["..."], "tempo": ["..."], "tone": ["..."], "themes": ["..."], "setting": {"era": ["..."], "place": ["..."]}}}'
    )

    for ProviderClass in providers:
        try:
            provider = ProviderClass()
            raw = await provider.generate(prompt=prompt, system=_INTENT_SYSTEM)
            raw = raw.strip()

            # JSON 블록 추출
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start < 0 or end <= start:
                continue

            parsed = json.loads(raw[start:end])
            rule_query = parsed.get("rule_query", {})
            raw_facets = parsed.get("facets", {})

            # 통제어휘 강제
            facets = validate_facets(raw_facets)

            logger.info(
                "[intent] provider=%s rule_query=%s facets_keys=%s",
                ProviderClass.__name__, list(rule_query.keys()), list(facets.keys()),
            )
            return IntentResult(
                rule_query=rule_query,
                facets=facets,
                provider_used=ProviderClass.__name__,
                raw_llm=raw[start:end],
            )
        except Exception as e:
            logger.debug("[intent] provider %s failed: %s", ProviderClass.__name__, e)
            continue

    # 모든 provider 실패 → Tier0 폴백
    logger.warning("[intent] 모든 LLM provider 실패, Tier0 폴백 반환")
    return IntentResult()


def apply_intent_to_node(node, result: IntentResult) -> None:
    """IntentResult를 ProgrammingNode.rule_query / theme_features에 반영 (in-place)."""
    if result.rule_query:
        existing = node.rule_query or {}
        existing.update(result.rule_query)
        node.rule_query = existing
    if result.facets:
        existing_tf = node.theme_features or {}
        existing_tf["facets"] = result.facets
        node.theme_features = existing_tf
