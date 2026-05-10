"""
Phase C SEED 모델 — 신규 콘텐츠 발굴 라이프사이클

테이블:
  - content_seeds       : SEED 5상태 (discovered→candidate→under_review→accepted/rejected)
  - seed_discovery_log  : 소스별 발굴 회차 통계

참조: docs/dev/phase-c/lifecycle.md, docs/dev/phase-c/dedup.md
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from shared.database import Base

_KST = timezone(timedelta(hours=9))
_LOCK_TTL_MINUTES = 15


class ContentSeed(Base):
    """SEED 라이프사이클 메인 테이블.
    Phase B 의 SeedCandidate(스텁)와 다름 — 이쪽이 Phase C 의 본격 구현."""
    __tablename__ = "content_seeds"
    __table_args__ = (
        UniqueConstraint("source_type", "external_id", name="uq_content_seed_source"),
        Index("ix_content_seeds_status_discovered", "status", "discovered_at"),
        Index("ix_content_seeds_content_type_year", "content_type", "production_year"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_type = Column(String(30), nullable=False)       # ExternalSourceType 값 + 'omdb'
    external_id = Column(String(64), nullable=False)       # TMDB id, KOBIS movieCd, KMDb DOCID, IMDb tt…
    title = Column(String(500), nullable=False)
    original_title = Column(String(500), nullable=True)
    content_type = Column(String(20), nullable=True)       # movie | series | season | episode
    production_year = Column(Integer, nullable=True)
    poster_url = Column(Text, nullable=True)
    synopsis = Column(Text, nullable=True)
    raw_payload = Column(JSON, nullable=False)              # 원본 API 응답 보관 (감사·재처리)

    status = Column(String(30), nullable=False, server_default="candidate")
    # status: discovered | candidate | under_review | accepted | rejected

    locked_by = Column(String(64), nullable=True)          # 검토 잠금 사용자 ID
    locked_at = Column(DateTime(timezone=True), nullable=True)

    discovered_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at = Column(DateTime(timezone=True), nullable=True)  # 재발굴 시 갱신
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    promoted_to_content_id = Column(Integer, ForeignKey("contents.id", ondelete="SET NULL"), nullable=True)
    suspected_match_content_id = Column(Integer, ForeignKey("contents.id", ondelete="SET NULL"), nullable=True)
    # dedup §4.1: 0.70~0.85 구간 매칭 시 검수자 힌트

    alt_external_ids = Column(JSON, nullable=False, default=dict)
    # dedup §4.3: [{"source": "omdb", "id": "tt1234567", "score": 0.94}]

    promoted_content = relationship("Content", foreign_keys=[promoted_to_content_id])
    suspected_content = relationship("Content", foreign_keys=[suspected_match_content_id])

    @property
    def is_locked(self) -> bool:
        """locked_at + 15분 TTL 이내이면 잠긴 상태."""
        if self.locked_at is None:
            return False
        locked_at = self.locked_at
        # SQLite는 naive datetime 저장 — timezone 없으면 UTC로 간주
        if locked_at.tzinfo is None:
            locked_at = locked_at.replace(tzinfo=timezone.utc)
        expiry = locked_at + timedelta(minutes=_LOCK_TTL_MINUTES)
        return datetime.now(tz=timezone.utc) < expiry


class SeedDiscoveryLog(Base):
    """소스별 발굴 회차 통계 — 운영 진단·dedup 효율 지표."""
    __tablename__ = "seed_discovery_log"
    __table_args__ = (
        Index("ix_seed_discovery_log_source_fetched", "source_type", "fetched_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_type = Column(String(30), nullable=False)
    discovery_mode = Column(String(30), nullable=False)
    # discovery_mode: trending_day | trending_week | upcoming | discover
    #                 new_release | box_office | other

    fetched_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    total_fetched = Column(Integer, nullable=False, server_default="0")
    new_seeds = Column(Integer, nullable=False, server_default="0")
    matched_existing = Column(Integer, nullable=False, server_default="0")  # SEED 미적재, MatchEdge만 추가
    duplicates = Column(Integer, nullable=False, server_default="0")        # SEED 간 UPSERT
    errors = Column(Integer, nullable=False, server_default="0")
    duration_ms = Column(Integer, nullable=True)

    dedup_decision = Column(String(30), nullable=True)
    # dedup_decision: appended_to_content | appended_to_seed | created_seed

    discovery_params = Column(JSON, nullable=True)         # region, page, query 등 호출 파라미터
