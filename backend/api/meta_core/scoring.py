"""
match_score — candidate ↔ Content 동일성 판정 (0.0~1.0)

콘텐츠 메타 완성도(quality_score, 0~100)와 다름.
완성도는 api.programming.metadata.ai_engine._calculate_quality_score 참조.

가중치: title 0.30 + year 0.20 + cast 0.15 + multi_source 0.15
        + external_id 0.10 + source_reliability 0.05 + image 0.05

참조: docs/dev/meta-intelligence.md §3, §4
"""

import os
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Literal

# ──────────────────────────── 소스 신뢰도 ────────────────────────────

_DEFAULT_WEIGHTS: dict[str, float] = {
    "tmdb": 1.00,
    "kobis": 0.95,
    "kmdb": 0.95,
    "watcha": 0.80,
    "naver": 0.70,
    "daum": 0.70,
    "websearch": 0.50,
    "other": 0.50,
}


def source_reliability(source_type: str) -> float:
    """env META_SOURCE_WEIGHT__<SOURCE> 우선, 없으면 기본값."""
    env_key = f"META_SOURCE_WEIGHT__{source_type.upper()}"
    raw = os.environ.get(env_key)
    if raw is not None:
        try:
            return float(raw)
        except ValueError:
            pass
    return _DEFAULT_WEIGHTS.get(source_type.lower(), 0.50)


# ──────────────────────────── 정규화 ────────────────────────────

def normalize_title(s: str) -> str:
    """소문자 + 한글/영문/숫자/공백만 유지. 시즌·연도 표기 제거."""
    if not s:
        return ""
    s = s.lower()
    s = re.sub(r'\s*\(?\s*(시즌|season|s)\s*\d+\s*\)?', '', s, flags=re.IGNORECASE)
    s = re.sub(r'\s*\(?\s*\d{4}\s*\)?', '', s)
    s = re.sub(r'[^\w\s가-힣]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def normalize_person_name(s: str) -> str:
    """성명 정규화 — 공백 제거 소문자화. 영문 KMDb/TMDB 표기 차이 흡수."""
    if not s:
        return ""
    return re.sub(r'\s+', '', s.lower())


# ──────────────────────────── 서브 스코어 ────────────────────────────

def title_score(a: str, b: str) -> float:
    """제목 유사도 0.0~1.0. exact=1.0, 정규화 후 SequenceMatcher 기반."""
    na = normalize_title(a)
    nb = normalize_title(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    seq_ratio = SequenceMatcher(None, na, nb).ratio()
    # token overlap (공백 기준 분리 — 한글 단어 단위)
    ta = set(na.split())
    tb = set(nb.split())
    if ta and tb:
        token_overlap = len(ta & tb) / max(len(ta), len(tb))
        seq_ratio = max(seq_ratio, token_overlap * 0.9)
    return round(min(seq_ratio, 1.0), 4)


def year_score(a: int | None, b: int | None) -> float:
    """연도 일치 점수. 동일=1.0, ±1년=0.7, 둘 중 하나 None=0.5, 그 외=0.0."""
    if a is None or b is None:
        return 0.5
    if a == b:
        return 1.0
    if abs(a - b) == 1:
        return 0.7
    return 0.0


def cast_overlap_score(cast_a: list[str], cast_b: list[str]) -> float:
    """출연진 Jaccard 유사도. 최대 top-10 비교. 빈 리스트 한쪽이면 0.0."""
    if not cast_a or not cast_b:
        return 0.0
    norm_a = {normalize_person_name(n) for n in cast_a[:10]}
    norm_b = {normalize_person_name(n) for n in cast_b[:10]}
    if not norm_a or not norm_b:
        return 0.0
    intersection = len(norm_a & norm_b)
    union = len(norm_a | norm_b)
    return round(intersection / union, 4)


def external_id_score(ids_a: dict, ids_b: dict) -> float:
    """동일 source 의 id 일치 시 1.0, 충돌 시 0.0, 비교 불가 시 0.0."""
    if not ids_a or not ids_b:
        return 0.0
    for source, val in ids_a.items():
        if source in ids_b:
            return 1.0 if str(ids_b[source]) == str(val) else 0.0
    return 0.0


# ──────────────────────────── 메인 함수 ────────────────────────────

@dataclass
class MatchScoreBreakdown:
    title: float
    year: float
    cast: float
    multi_source: float
    external_id: float
    source_reliability: float
    image: float


@dataclass
class MatchScoreResult:
    score: float
    breakdown: MatchScoreBreakdown
    reasons: list[str] = field(default_factory=list)


def compute_match_score(
    candidate: dict,
    content: dict,
    *,
    other_candidates: list[dict] | None = None,
) -> MatchScoreResult:
    """
    candidate(MetadataCandidate row → dict) 와 content(Content+ContentMetadata → dict) 의
    동일성 점수를 계산한다.

    other_candidates: 같은 content_id 를 향해 이미 계산된 다른 소스 candidate 목록.
                      multi_source 항 산정에 사용. None 이면 0 처리.
    """
    # title (0.30)
    cand_title = candidate.get("title_norm") or candidate.get("title") or ""
    cont_title = content.get("title") or content.get("title_norm") or ""
    t = title_score(cand_title, cont_title)

    # year (0.20)
    y = year_score(
        candidate.get("year"),
        content.get("production_year") or content.get("year"),
    )

    # cast (0.15)
    def _extract_names(lst: list) -> list[str]:
        return [c.get("name", c) if isinstance(c, dict) else c for c in (lst or [])]

    c = cast_overlap_score(
        _extract_names(candidate.get("cast_json")),
        _extract_names(content.get("cast")),
    )

    # multi_source (0.15) — 다른 소스의 candidate 가 같은 content 를 가리키는지
    ms = 0.0
    if other_candidates:
        other_sources = {
            oc.get("source_type")
            for oc in other_candidates
            if oc.get("source_type") != candidate.get("source_type")
        }
        ms = round(min(len(other_sources) / 2, 1.0), 4)

    # external_id (0.10)
    e = external_id_score(
        candidate.get("external_ids_json") or {},
        content.get("external_ids") or {},
    )

    # source_reliability (0.05)
    sr = source_reliability(candidate.get("source_type", "other"))

    # image (0.05)
    img = 1.0 if (candidate.get("poster_url") and content.get("poster_url")) else 0.0

    score = round(
        0.30 * t + 0.20 * y + 0.15 * c + 0.15 * ms
        + 0.10 * e + 0.05 * sr + 0.05 * img,
        4,
    )
    score = min(max(score, 0.0), 1.0)

    reasons: list[str] = []
    if t >= 0.95:
        reasons.append("title_exact")
    elif t >= 0.70:
        reasons.append("title_similar")
    if y >= 0.9:
        reasons.append("year_match")
    if c >= 0.5:
        reasons.append("cast_overlap")
    if ms > 0:
        reasons.append("multi_source")
    if e >= 1.0:
        reasons.append("external_id_match")

    return MatchScoreResult(
        score=score,
        breakdown=MatchScoreBreakdown(t, y, c, ms, e, sr, img),
        reasons=reasons,
    )


def classify_match(score: float) -> Literal["auto", "review", "hold", "drop"]:
    """
    score >= 0.90 → auto   (자동 매칭)
    0.70 ~ 0.89  → review  (검수 큐)
    0.50 ~ 0.69  → hold    (보류)
    < 0.50       → drop    (폐기)
    """
    if score >= 0.90:
        return "auto"
    if score >= 0.70:
        return "review"
    if score >= 0.50:
        return "hold"
    return "drop"
