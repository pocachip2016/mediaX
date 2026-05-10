"""
match_or_create_seed — 발굴 결과를 Content·SEED 와 대조해 중복 처리

우선순위:
  1. 동일 source_type + external_id SEED 존재 → UPDATE (duplicate)
  2. 기존 Content 와 title+year 매칭 ≥ 0.85 → SEED 미적재, MatchEdge 기록 (matched_existing)
  3. 다른 SEED 와 title+year 매칭 ≥ 0.92 → alt_external_ids 누적 (alt_id_added)
  4. 위 모두 미해당 → 신규 SEED 생성 (created)

참조: docs/dev/phase-c/dedup.md
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from api.meta_core.discovery.base import DiscoveryResult
from api.meta_core.models.seed import ContentSeed
from api.meta_core.scoring import title_score, year_score

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_CONTENT_MATCH_THRESHOLD = 0.85
_SEED_DEDUP_THRESHOLD = 0.92


def _title_year_score(title_a: str, year_a: int | None,
                      title_b: str, year_b: int | None) -> float:
    """title 0.6 + year 0.4 가중 합산 — dedup 전용 단순 점수."""
    t = title_score(title_a or "", title_b or "")
    y = year_score(year_a, year_b)
    return round(t * 0.6 + y * 0.4, 4)


def _find_matching_content(db: "Session", result: DiscoveryResult):
    """title+year 후보 검색 후 최고 점수 Content 반환. 없으면 None."""
    from api.programming.metadata.models.content import Content

    year = result.production_year
    # production_year ±1 범위 SQL 필터 (None 이면 연도 무관 전체)
    if year is not None:
        candidates = (
            db.query(Content)
            .filter(
                Content.title.ilike(f"%{result.title[:10]}%"),
                Content.production_year.between(year - 1, year + 1),
            )
            .limit(20)
            .all()
        )
    else:
        candidates = (
            db.query(Content)
            .filter(Content.title.ilike(f"%{result.title[:10]}%"))
            .limit(20)
            .all()
        )

    best_score = 0.0
    best_content = None
    for c in candidates:
        score = _title_year_score(result.title, result.production_year,
                                  c.title, c.production_year)
        if score > best_score:
            best_score = score
            best_content = c

    if best_score >= _CONTENT_MATCH_THRESHOLD:
        return best_content, best_score
    return None, 0.0


def _find_matching_seed(db: "Session", result: DiscoveryResult,
                        exclude_source_type: str) -> ContentSeed | None:
    """다른 source_type 의 SEED 중 title+year 유사도 ≥ 0.92 인 것 반환."""
    year = result.production_year
    if year is not None:
        seeds = (
            db.query(ContentSeed)
            .filter(
                ContentSeed.source_type != exclude_source_type,
                ContentSeed.title.ilike(f"%{result.title[:10]}%"),
                ContentSeed.production_year.between(year - 1, year + 1),
            )
            .limit(20)
            .all()
        )
    else:
        seeds = (
            db.query(ContentSeed)
            .filter(
                ContentSeed.source_type != exclude_source_type,
                ContentSeed.title.ilike(f"%{result.title[:10]}%"),
            )
            .limit(20)
            .all()
        )

    for seed in seeds:
        score = _title_year_score(result.title, result.production_year,
                                  seed.title, seed.production_year)
        if score >= _SEED_DEDUP_THRESHOLD:
            return seed
    return None


def _add_match_edge(db: "Session", content_id: int,
                    source_type: str, external_id: str,
                    title: str, score: float) -> None:
    """Content ↔ SEED 매칭 결과를 MetadataCandidate + MatchEdge 로 기록."""
    from api.meta_core.models.intelligence import MetadataCandidate, MatchEdge
    from api.meta_core.scoring import normalize_title

    # MetadataCandidate — SEED 발굴 소스용 최소 레코드
    candidate = (
        db.query(MetadataCandidate)
        .filter_by(source_type=source_type, source_external_id=external_id,
                   target_type="content_seed")
        .first()
    )
    if not candidate:
        candidate = MetadataCandidate(
            source_type=source_type,
            source_external_id=external_id,
            title_norm=normalize_title(title),
            raw_payload={},
            target_type="content_seed",
        )
        db.add(candidate)
        db.flush()

    # MatchEdge — 중복 없으면 추가
    existing_edge = (
        db.query(MatchEdge)
        .filter_by(candidate_id=candidate.id, content_id=content_id)
        .first()
    )
    if not existing_edge:
        edge = MatchEdge(
            candidate_id=candidate.id,
            content_id=content_id,
            score=score,
            reasons_json=["seed_discovery_dedup"],
            sub_scores_json={"title_year_combined": score},
            decided=False,
        )
        db.add(edge)


def match_or_create_seed(
    db: "Session", result: DiscoveryResult
) -> tuple[ContentSeed | None, str]:
    """
    발굴 결과 1건을 DB 와 대조해 처리.

    Returns:
        (seed_or_None, action) where action is one of:
          "duplicate"        — 동일 source+id SEED 존재 → 업데이트
          "matched_existing" — 기존 Content 와 매칭 ≥ 0.85 → SEED 미적재
          "alt_id_added"     — 다른 SEED 와 매칭 ≥ 0.92 → alt_external_ids 누적
          "created"          — 신규 SEED 생성
    """
    now = datetime.now(tz=timezone.utc)

    # ── 1. 동일 source_type + external_id SEED ─────────────────────────────
    existing = (
        db.query(ContentSeed)
        .filter_by(source_type=result.source_type, external_id=result.external_id)
        .first()
    )
    if existing:
        existing.title = result.title
        existing.original_title = result.original_title
        existing.production_year = result.production_year
        existing.poster_url = result.poster_url
        existing.synopsis = result.synopsis
        existing.raw_payload = result.raw
        existing.last_seen_at = now
        logger.debug("[dedup] duplicate: %s/%s", result.source_type, result.external_id)
        return existing, "duplicate"

    # ── 2. 기존 Content 매칭 ≥ 0.85 ─────────────────────────────────────────
    matched_content, score = _find_matching_content(db, result)
    if matched_content is not None:
        _add_match_edge(db, matched_content.id,
                        result.source_type, result.external_id,
                        result.title, score)
        logger.debug("[dedup] matched_existing: %s/%s → content_id=%d (score=%.3f)",
                     result.source_type, result.external_id, matched_content.id, score)
        return None, "matched_existing"

    # ── 3. 다른 SEED 와 fuzzy match ≥ 0.92 ───────────────────────────────────
    sibling = _find_matching_seed(db, result, exclude_source_type=result.source_type)
    if sibling is not None:
        alt = sibling.alt_external_ids or {}
        alt[result.source_type] = result.external_id
        sibling.alt_external_ids = alt
        sibling.last_seen_at = now
        logger.debug("[dedup] alt_id_added: %s/%s → seed_id=%d",
                     result.source_type, result.external_id, sibling.id)
        return sibling, "alt_id_added"

    # ── 4. 신규 SEED 생성 ───────────────────────────────────────────────────
    seed = ContentSeed(
        source_type=result.source_type,
        external_id=result.external_id,
        title=result.title,
        original_title=result.original_title,
        content_type=result.content_type,
        production_year=result.production_year,
        poster_url=result.poster_url,
        synopsis=result.synopsis,
        raw_payload=result.raw,
        status="candidate",
        last_seen_at=now,
    )
    db.add(seed)
    logger.debug("[dedup] created: %s/%s", result.source_type, result.external_id)
    return seed, "created"
