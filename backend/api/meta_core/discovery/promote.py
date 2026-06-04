"""
promote_seed — SEED → Content 승격

흐름:
  1. SEED row 조회 + 상태 검증
  2. 잠금 확인 (TTL 15분)
  3. dedup 재확인 (발굴 시점 이후 Content 추가 가능)
  4. Content + ExternalMetaSource INSERT
  5. SEED status='accepted' 기록
  6. Celery enqueue (Phase B aggregator)

참조: docs/dev/phase-c/promotion-guard.md
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from api.meta_core.discovery.dedup import _find_matching_content
from api.meta_core.discovery.base import DiscoveryResult
from api.meta_core.models.seed import ContentSeed

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_PROMOTABLE_STATUSES = {"discovered", "candidate", "under_review"}
_LOCK_TTL = timedelta(minutes=15)


class SeedNotFound(Exception):
    pass


class SeedAlreadyProcessed(Exception):
    pass


class SeedLockedByOther(Exception):
    def __init__(self, locked_by: str, locked_at: datetime):
        self.locked_by = locked_by
        self.locked_at = locked_at


class PossibleDuplicate(Exception):
    def __init__(self, content_id: int, score: float):
        self.content_id = content_id
        self.score = score


def promote_seed(
    db: "Session",
    seed_id: int,
    actor: str,
    override_dup: bool = False,
) -> "Content":  # noqa: F821
    """
    SEED → Content 승격. 성공 시 생성된 Content 반환.

    Raises:
        SeedNotFound: seed_id 미존재
        SeedAlreadyProcessed: status 가 accepted/rejected
        SeedLockedByOther: 다른 사용자 lock (TTL 유효)
        PossibleDuplicate: dedup 재확인에서 매칭 ≥ 0.85 발견, override_dup=False
    """
    from api.programming.metadata.models.content import Content
    from api.programming.metadata.models.external import ExternalMetaSource, ExternalSourceType

    now = datetime.now(tz=timezone.utc)

    # ── 1. SEED 조회 ───────────────────────────────────────────────────────────
    seed = db.query(ContentSeed).filter_by(id=seed_id).first()
    if seed is None:
        raise SeedNotFound(f"ContentSeed id={seed_id} 없음")

    # ── 2. 상태 체크 ───────────────────────────────────────────────────────────
    if seed.status not in _PROMOTABLE_STATUSES:
        raise SeedAlreadyProcessed(
            f"SEED status={seed.status!r} — 승격 불가 (이미 처리됨)"
        )

    # ── 3. 잠금 확인 ───────────────────────────────────────────────────────────
    if seed.locked_by and seed.locked_by != actor:
        lock_age = now - seed.locked_at.replace(tzinfo=timezone.utc) if seed.locked_at else timedelta(hours=99)
        if lock_age < _LOCK_TTL:
            raise SeedLockedByOther(seed.locked_by, seed.locked_at)

    # ── 4. dedup 재확인 ────────────────────────────────────────────────────────
    result_stub = DiscoveryResult(
        source_type=seed.source_type,
        external_id=seed.external_id,
        title=seed.title,
        content_type=seed.content_type or "movie",
        original_title=seed.original_title,
        production_year=seed.production_year,
    )
    matched_content, score = _find_matching_content(db, result_stub)
    if matched_content is not None and not override_dup:
        raise PossibleDuplicate(matched_content.id, score)

    # ── 5. Content INSERT ──────────────────────────────────────────────────────
    content = Content(
        title=seed.title,
        original_title=seed.original_title,
        content_type=seed.content_type or "movie",
        production_year=seed.production_year,
        status="raw",
    )
    db.add(content)
    db.flush()  # content.id 확보

    # ── 6. ExternalMetaSource INSERT ──────────────────────────────────────────
    try:
        src_type = ExternalSourceType(seed.source_type)
    except ValueError:
        src_type = ExternalSourceType.other

    ext_src = ExternalMetaSource(
        content_id=content.id,
        source_type=src_type,
        external_id=seed.external_id,
        title_on_source=seed.title,
        raw_json=seed.raw_payload,
        match_confidence=1.0,
        matched_at=now,
    )
    db.add(ext_src)

    # ── 7. SEED 갱신 ───────────────────────────────────────────────────────────
    seed.status = "accepted"
    seed.promoted_to_content_id = content.id
    seed.locked_by = None
    seed.locked_at = None

    db.flush()

    # ── 8. Celery enqueue ────────────────────────────────────────────────────
    _enqueue_aggregate(content.id)

    logger.info("[promote] seed_id=%d → content_id=%d (actor=%s)", seed_id, content.id, actor)
    return content


def _enqueue_aggregate(content_id: int) -> None:
    """Phase B aggregator Celery task 비동기 enqueue. Redis 미연결 시 skip."""
    try:
        from workers.tasks.metadata import process_content_metadata
        process_content_metadata.delay(content_id)
    except Exception as exc:
        logger.warning("[promote] aggregator enqueue 실패 (content_id=%d): %s", content_id, exc)
