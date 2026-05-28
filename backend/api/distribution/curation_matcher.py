"""
큐레이션 워크벤치 — 보유 콘텐츠 매칭 알고리즘 (결정적, LLM 미사용)

theme_features 스키마:
  {
    "genres": ["코미디", "드라마"],
    "moods": ["가벼운"],
    "runtime_min": 80, "runtime_max": 120,
    "era_from": 2000,  "era_to": 2026,
    "free_keywords": ["퇴근", "위로"],
    "target": "30s_adults",   # 미사용 (향후 확장)
    "occasion": "weekday_evening",
  }

가중치 합계 = 1.0 (genre 0.30 + mood 0.15 + runtime 0.20 + era 0.10 + external 0.15 + keywords 0.10)
외부 참고 섹션의 아이템 제목 집합은 호출자가 전달 (DB/HTTP 접근 격리).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session, joinedload

from api.programming.metadata.models.content import Content, ContentMetadata
from api.programming.metadata.models.taxonomy import ContentGenre, GenreCode


# ── 가중치 상수 ───────────────────────────────────────────────────────────────

_W_GENRE    = 0.30
_W_MOOD     = 0.15
_W_RUNTIME  = 0.20
_W_ERA      = 0.10
_W_EXTERNAL = 0.15
_W_KEYWORDS = 0.10


@dataclass
class ContentMatchResult:
    content_id: int
    title: str
    content_type: str
    production_year: int | None
    runtime_minutes: int | None
    score: float
    score_breakdown: dict[str, float] = field(default_factory=dict)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip()).lower()


def _genre_score(
    genre_names: list[str],
    ai_genre_primary: str | None,
    ai_genre_secondary: str | None,
    target_genres: list[str],
) -> float:
    if not target_genres:
        return 1.0  # 제약 없음 → 최대
    targets = {_normalize(g) for g in target_genres}
    content_genres: set[str] = set()
    for g in genre_names:
        content_genres.add(_normalize(g))
    if ai_genre_primary:
        content_genres.add(_normalize(ai_genre_primary))
    if ai_genre_secondary:
        content_genres.add(_normalize(ai_genre_secondary))
    if not content_genres:
        return 0.0
    matched = len(targets & content_genres)
    return min(1.0, matched / len(targets) + matched * 0.1)  # 다중 일치 가산


def _mood_score(ai_mood_tags: list[str] | None, target_moods: list[str]) -> float:
    if not target_moods:
        return 1.0
    if not ai_mood_tags:
        return 0.0
    targets = {_normalize(m) for m in target_moods}
    content_moods = {_normalize(m) for m in ai_mood_tags}
    matched = len(targets & content_moods)
    return min(1.0, matched / len(targets))


def _runtime_score(runtime_minutes: int | None, runtime_min: int | None, runtime_max: int | None) -> float:
    if runtime_min is None and runtime_max is None:
        return 1.0
    if runtime_minutes is None:
        return 0.5  # 런타임 정보 없음 → 중립
    lo = runtime_min if runtime_min is not None else 0
    hi = runtime_max if runtime_max is not None else 9999
    if lo <= runtime_minutes <= hi:
        return 1.0
    # 범위 벗어난 정도에 비례해 감점 (최대 절반까지)
    distance = max(lo - runtime_minutes, runtime_minutes - hi)
    penalty = min(0.5, distance / max(hi - lo + 1, 1) * 0.5)
    return max(0.0, 1.0 - penalty)


def _era_score(production_year: int | None, era_from: int | None, era_to: int | None) -> float:
    if era_from is None and era_to is None:
        return 1.0
    if production_year is None:
        return 0.5
    lo = era_from if era_from is not None else 0
    hi = era_to if era_to is not None else 9999
    return 1.0 if lo <= production_year <= hi else 0.0


def _external_score(title: str, external_titles: set[str]) -> float:
    if not external_titles:
        return 0.0
    return 1.0 if _normalize(title) in external_titles else 0.0


def _keyword_score(title: str, synopsis: str | None, free_keywords: list[str]) -> float:
    if not free_keywords:
        return 1.0
    haystack = _normalize(title + " " + (synopsis or ""))
    matched = sum(1 for kw in free_keywords if _normalize(kw) in haystack)
    return min(1.0, matched / len(free_keywords))


def score_content(
    *,
    content: Content,
    metadata: ContentMetadata | None,
    genre_names: list[str],
    theme_features: dict[str, Any],
    external_titles: set[str],
) -> tuple[float, dict[str, float]]:
    """콘텐츠 1건을 theme_features로 채점 → (total_score, breakdown)"""
    tf = theme_features or {}

    g_score = _genre_score(
        genre_names,
        metadata.ai_genre_primary if metadata else None,
        metadata.ai_genre_secondary if metadata else None,
        tf.get("genres") or [],
    )
    m_score = _mood_score(
        metadata.ai_mood_tags if metadata else None,
        tf.get("moods") or [],
    )
    r_score = _runtime_score(
        content.runtime_minutes,
        tf.get("runtime_min"),
        tf.get("runtime_max"),
    )
    e_score = _era_score(
        content.production_year,
        tf.get("era_from"),
        tf.get("era_to"),
    )
    x_score = _external_score(content.title or "", external_titles)
    k_score = _keyword_score(
        content.title or "",
        metadata.ai_synopsis if metadata else None,
        tf.get("free_keywords") or [],
    )

    total = (
        g_score * _W_GENRE
        + m_score * _W_MOOD
        + r_score * _W_RUNTIME
        + e_score * _W_ERA
        + x_score * _W_EXTERNAL
        + k_score * _W_KEYWORDS
    )

    breakdown = {
        "genre": round(g_score, 3),
        "mood": round(m_score, 3),
        "runtime": round(r_score, 3),
        "era": round(e_score, 3),
        "external": round(x_score, 3),
        "keywords": round(k_score, 3),
    }
    return round(total, 4), breakdown


def match_contents(
    db: Session,
    theme_features: dict[str, Any],
    external_titles: set[str] | None = None,
    limit: int = 20,
) -> list[ContentMatchResult]:
    """DB에서 is_deleted=False 콘텐츠를 채점해 상위 limit개 반환."""
    ext_titles = external_titles or set()

    # 단일 쿼리로 contents + metadata + genres 로드
    contents = (
        db.query(Content)
        .filter(Content.is_deleted == False)  # noqa: E712
        .options(
            joinedload(Content.metadata_record),
            joinedload(Content.genres).joinedload(ContentGenre.genre),
        )
        .all()
    )

    results: list[ContentMatchResult] = []
    for content in contents:
        meta = content.metadata_record
        genre_names = [
            cg.genre.name_ko
            for cg in content.genres
            if cg.genre and cg.genre.name_ko
        ]
        total, breakdown = score_content(
            content=content,
            metadata=meta,
            genre_names=genre_names,
            theme_features=theme_features,
            external_titles=ext_titles,
        )
        results.append(ContentMatchResult(
            content_id=content.id,
            title=content.title or "",
            content_type=content.content_type.value if content.content_type else "movie",
            production_year=content.production_year,
            runtime_minutes=content.runtime_minutes,
            score=total,
            score_breakdown=breakdown,
        ))

    results.sort(key=lambda r: r.score, reverse=True)
    return results[:limit]
