"""
Field Strategy Catalog — 필드별 결정 정책 단일 카탈로그

FIELD_STRATEGIES[field_name] → FieldStrategy
Aggregator(step7) 와 검수 백엔드(step9) 가 이 카탈로그만 참조.

DB 접근 없음 — 순수 Python.
임계 env override: META_FIELD_THRESHOLD__<FIELD_NAME_UPPER> (agree_threshold int)
                  META_WEIGHT_THRESHOLD__<FIELD_NAME_UPPER>  (weight_threshold float)
참조: docs/dev/meta-intelligence.md §2, §5
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


class FieldType(str, Enum):
    A_SINGLE = "A_SINGLE"       # 단일값·이산 — 2+ 소스 일치 → 자동 확정
    B_MULTI = "B_MULTI"         # 다중값·이산 — 멤버별 출현 빈도 기준
    C_TEXT = "C_TEXT"           # 자유 텍스트 — 항상 pending, 검수자 pick/LLM merge
    D_ASSET = "D_ASSET"         # 자산 URL — source_priority 1위 자동 채택
    E_EXTERNAL_ID = "E_EXTERNAL_ID"  # 외부 ID — 모든 소스 항상 보존


@dataclass
class FieldStrategy:
    type: FieldType
    # A/B: 자동 확정에 필요한 동의 소스 수 (env override 가능)
    agree_threshold: int = 2
    # A: 동의 소스들의 신뢰도 합 최솟값 (§5.1)
    weight_threshold: float = 1.5
    # A: 값 동등 판정 정규화 함수
    normalizer: Callable[[str], str] | None = None
    # A: 수치 필드 허용 오차 (예: runtime ±5분)
    tolerance: int | None = None
    # B: 자동 채택 최대 멤버 수 (cap)
    max_auto: int | None = None
    # D: 소스 우선순위 리스트
    source_priority: list[str] = field(default_factory=list)
    # C: LLM merge 허용 여부
    allow_llm_merge: bool = False


# ── 정규화 함수 ──────────────────────────────────────────────────────────────

def _lower_strip(s: str) -> str:
    return s.strip().lower()


def _genre_norm(s: str) -> str:
    return s.strip().lower().replace(" ", "").replace("-", "")


def _country_norm(s: str) -> str:
    # ISO 3166-1 alpha-2 정규화 (대문자)
    s = s.strip().upper()
    _aliases = {"KOREA": "KR", "SOUTH KOREA": "KR", "JAPAN": "JP", "USA": "US",
                "US": "US", "CHINA": "CN", "UK": "GB"}
    return _aliases.get(s, s)


def _runtime_norm(s: str) -> str:
    # 분 단위 숫자만 추출 (tolerance 는 FieldStrategy.tolerance 로 처리)
    digits = "".join(c for c in s if c.isdigit())
    return digits if digits else s


def _content_type_norm(s: str) -> str:
    return s.strip().lower().replace(" ", "_")


def _person_norm(s: str) -> str:
    # scoring.py 의 normalize_person_name 과 동일 로직 인라인
    return s.strip().lower().replace(" ", "")


# ── 임계 env override 헬퍼 ────────────────────────────────────────────────────

def _agree(field_name: str, default: int) -> int:
    key = f"META_FIELD_THRESHOLD__{field_name.upper()}"
    val = os.environ.get(key, "")
    try:
        return int(val) if val else default
    except ValueError:
        return default


def _weight(field_name: str, default: float) -> float:
    key = f"META_WEIGHT_THRESHOLD__{field_name.upper()}"
    val = os.environ.get(key, "")
    try:
        return float(val) if val else default
    except ValueError:
        return default


def _a(field_name: str, normalizer=_lower_strip, tolerance=None) -> FieldStrategy:
    return FieldStrategy(
        type=FieldType.A_SINGLE,
        agree_threshold=_agree(field_name, 2),
        weight_threshold=_weight(field_name, 1.5),
        normalizer=normalizer,
        tolerance=tolerance,
    )


def _b(field_name: str, max_auto: int) -> FieldStrategy:
    return FieldStrategy(
        type=FieldType.B_MULTI,
        agree_threshold=_agree(field_name, 2),
        max_auto=max_auto,
    )


def _c(allow_llm_merge: bool = False) -> FieldStrategy:
    return FieldStrategy(type=FieldType.C_TEXT, allow_llm_merge=allow_llm_merge)


def _d(source_priority: list[str]) -> FieldStrategy:
    return FieldStrategy(type=FieldType.D_ASSET, source_priority=source_priority)


def _e() -> FieldStrategy:
    return FieldStrategy(type=FieldType.E_EXTERNAL_ID)


# ── 카탈로그 ─────────────────────────────────────────────────────────────────

FIELD_STRATEGIES: dict[str, FieldStrategy] = {
    # A. 단일값·이산
    "director":         _a("director", normalizer=_person_norm),
    "primary_genre":    _a("primary_genre", normalizer=_genre_norm),
    "release_year":     _a("release_year", normalizer=_lower_strip),
    "runtime":          _a("runtime", normalizer=_runtime_norm, tolerance=5),
    "country":          _a("country", normalizer=_country_norm),
    "content_type":     _a("content_type", normalizer=_content_type_norm),

    # B. 다중값·이산
    "cast":             _b("cast", max_auto=20),
    "secondary_genres": _b("secondary_genres", max_auto=3),
    "mood_tags":        _b("mood_tags", max_auto=10),

    # C. 자유 텍스트
    "synopsis":         _c(allow_llm_merge=True),
    "description":      _c(allow_llm_merge=True),

    # D. 자산 URL
    "poster":           _d(["tmdb", "kmdb", "kobis", "cp"]),
    "backdrop":         _d(["tmdb", "kmdb", "kobis", "cp"]),
    "logo":             _d(["cp", "tmdb", "kmdb"]),
    "stillcut":         _d(["cp", "tmdb", "kmdb"]),

    # E. 외부 ID
    "external_id":      _e(),   # enrich 단계에서 복합 ID dict 로 전달되는 통합 키
    "tmdb_id":          _e(),
    "kobis_id":         _e(),
    "kmdb_id":          _e(),
}


def get_strategy(field_name: str) -> FieldStrategy | None:
    """카탈로그에서 전략을 반환. 미등록 필드는 None."""
    return FIELD_STRATEGIES.get(field_name)
