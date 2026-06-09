"""match_service.py — Tier2 의미매칭 계산 레이어.

노드 theme 벡터 + facet ↔ 콘텐츠 CUP(embed_synopsis + facets)를 비교해
confidence + reason을 산출한다. IO/저장(suggested 링크 insert)은 다음 step(3.4) 범위.

설계 원칙 (ADR-011-03/05):
  - Tier0 후보축소 우선: apply_rule_query로 후보를 먼저 좁힌 뒤 벡터연산.
  - 프로파일 없는 후보 제외(근거 없음).
  - graceful degrade: 벡터 누락 시 cosine=0, facet-overlap만으로 confidence.
  - 설명가능성: 모든 결과에 reason 문자열 필수.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from sqlalchemy.orm import Session

from api.programming.scheduling.facets import facet_overlap_score
from api.programming.scheduling.models import ProgrammingNode
from api.programming.scheduling.profile_models import ContentSemanticProfile
from api.programming.scheduling.rule_engine import apply_rule_query


@dataclass
class MatchResult:
    content_id: int
    confidence: float   # 0~1 가중합
    cosine: float       # 0~1
    facet_overlap: float  # 0~1
    reason: str


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """pure-python 코사인 유사도. 빈/길이불일치/zero-norm → 0.0."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def match_node_to_contents(
    db: Session,
    node: ProgrammingNode,
    *,
    limit: int = 50,
    candidate_limit: int = 200,
    cosine_weight: float = 0.7,
    facet_weight: float = 0.3,
    min_confidence: float = 0.0,
) -> list[MatchResult]:
    """Tier2 의미매칭 — Tier0 후보축소 → cosine + facet overlap 가중합 → MatchResult 목록.

    반환값은 confidence 내림차순, 동률 시 content_id 오름차순.
    """
    # 1. Tier0 후보축소
    rule_results = apply_rule_query(db, node.rule_query or {}, limit=candidate_limit)
    candidate_ids = [r.content_id for r in rule_results]
    if not candidate_ids:
        return []

    # 2. 프로파일 일괄 조회 (N+1 금지)
    profiles = (
        db.query(ContentSemanticProfile)
        .filter(ContentSemanticProfile.content_id.in_(candidate_ids))
        .all()
    )
    profile_map: dict[int, ContentSemanticProfile] = {p.content_id: p for p in profiles}

    # 3. 노드 측 입력
    node_vec: list[float] = node.embed_theme or []
    tf = node.theme_features or {}
    node_facets: dict = tf.get("facets", {}) if isinstance(tf, dict) else {}

    # 4. 매칭 계산
    results: list[MatchResult] = []
    for cid in candidate_ids:
        profile = profile_map.get(cid)
        if profile is None:
            continue  # 프로파일 없는 후보 제외

        content_vec: list[float] = profile.embed_synopsis or []
        content_facets: dict = profile.facets or {}

        cos = cosine_similarity(node_vec, content_vec) if node_vec and content_vec else 0.0
        fov = facet_overlap_score(node_facets, content_facets)
        confidence = cosine_weight * cos + facet_weight * fov
        reason = (
            f"tier2: cosine={cos:.3f}(w={cosine_weight}) "
            f"+ facet={fov:.3f}(w={facet_weight}) → {confidence:.3f}"
        )
        results.append(MatchResult(
            content_id=cid,
            confidence=confidence,
            cosine=cos,
            facet_overlap=fov,
            reason=reason,
        ))

    # 5. 필터 + 정렬 + 상한
    results = [r for r in results if r.confidence >= min_confidence]
    results.sort(key=lambda r: (-r.confidence, r.content_id))
    return results[:limit]
