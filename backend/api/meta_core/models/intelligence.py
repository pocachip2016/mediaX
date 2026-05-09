"""
메타 인텔리전스 모델 — 후보·매칭·필드 제안·결정·SEED

5단계 흐름: metadata_candidate → match_edge → field_suggestion → field_resolution → seed_candidate
참조: docs/dev/meta-intelligence.md §1
"""

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Index, Integer,
    JSON, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from shared.database import Base


class MetadataCandidate(Base):
    """정규화된 외부 후보 메타 — source_item 을 내부 스키마로 파싱한 결과.
    ExternalMetaSource 와 다름: 이쪽은 아직 매칭 미확정 상태."""
    __tablename__ = "metadata_candidates"
    __table_args__ = (
        UniqueConstraint("source_type", "source_external_id", name="uq_candidate_source"),
        Index("ix_metadata_candidates_title_year", "title_norm", "year"),
        Index("ix_metadata_candidates_fetched_at", "fetched_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    source_type = Column(String(30), nullable=False, index=True)   # ExternalSourceType 값
    source_external_id = Column(String(255), nullable=False)       # TMDB id, KOBIS movieCd, KMDb DOCID
    source_url = Column(String(2000))
    raw_payload = Column(JSON, nullable=False)
    title_norm = Column(String(500), nullable=False)               # 소문자+특수문자제거 정규화 제목
    original_title = Column(String(500))
    year = Column(Integer)
    content_type = Column(String(20))
    synopsis = Column(Text)
    poster_url = Column(String(2000))
    cast_json = Column(JSON)                                       # [{name, role, order}, ...]
    director_json = Column(JSON)                                   # [{name}, ...]
    genre_json = Column(JSON)                                      # ["드라마", "스릴러"]
    external_ids_json = Column(JSON)                               # {tmdb: 12345, kobis: "20231234"}
    fetched_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    status = Column(String(20), nullable=False, server_default="active", index=True)
    # status: active | expired | rejected

    match_edges = relationship("MatchEdge", back_populates="candidate",
                               cascade="all, delete-orphan")
    seed_candidates = relationship("SeedCandidate", back_populates="candidate",
                                   cascade="all, delete-orphan")


class MatchEdge(Base):
    """candidate ↔ 내부 Content 매칭 — 점수 + 사유.
    decided=True 가 되어야 매칭 확정 → ExternalMetaSource 생성."""
    __tablename__ = "match_edges"
    __table_args__ = (
        UniqueConstraint("candidate_id", "content_id", name="uq_match_edge"),
        Index("ix_match_edges_score", "score"),
    )

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("metadata_candidates.id", ondelete="CASCADE"),
                          nullable=False, index=True)
    content_id = Column(Integer, ForeignKey("contents.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    score = Column(Float, nullable=False)                          # 0.0~1.0 (match_score)
    reasons_json = Column(JSON, nullable=False)                    # ["title_exact", "year_match"]
    sub_scores_json = Column(JSON)                                 # {title:0.3, year:0.2, ...}
    decided = Column(Boolean, nullable=False, server_default="false")
    decided_at = Column(DateTime(timezone=True))
    decided_by = Column(String(100))                               # "system" | username
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    candidate = relationship("MetadataCandidate", back_populates="match_edges")
    content = relationship("Content")


class FieldSuggestion(Base):
    """필드 단위 raw 후보값 — candidate 에서 1 필드를 떼어낸 제안.
    동일 (content_id, field_name) 에 여러 소스의 suggestion 이 공존 가능."""
    __tablename__ = "field_suggestions"
    __table_args__ = (
        Index("ix_field_suggestions_content_field", "content_id", "field_name"),
    )

    id = Column(Integer, primary_key=True, index=True)
    content_id = Column(Integer, ForeignKey("contents.id", ondelete="CASCADE"), nullable=False)
    field_name = Column(String(50), nullable=False)                # synopsis | poster | director | cast | ...
    value_json = Column(JSON, nullable=False)                      # 단일값/리스트/URL 모두 JSON
    source_candidate_id = Column(Integer, ForeignKey("metadata_candidates.id", ondelete="SET NULL"))
    source_type = Column(String(30), nullable=False)
    confidence = Column(Float, nullable=False, server_default="0.0")
    status = Column(String(20), nullable=False, server_default="pending", index=True)
    # status: pending | applied | rejected | superseded
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    content = relationship("Content")
    source_candidate = relationship("MetadataCandidate")


class FieldResolution(Base):
    """(content_id, field_name) 당 결정 1행 — audit trail.
    applied_to_content=True 인 행이 ContentMetadata 에 실제 반영된 상태."""
    __tablename__ = "field_resolutions"
    __table_args__ = (
        UniqueConstraint("content_id", "field_name", name="uq_field_resolution"),
        Index("ix_field_resolutions_decision", "decision"),
    )

    id = Column(Integer, primary_key=True, index=True)
    content_id = Column(Integer, ForeignKey("contents.id", ondelete="CASCADE"), nullable=False,
                        index=True)
    field_name = Column(String(50), nullable=False)
    decision = Column(String(30), nullable=False)
    # decision: auto_agreement | auto_quality | manual_pick | manual_merge | pending | rejected
    chosen_value_json = Column(JSON)
    chosen_suggestion_ids = Column(JSON)                           # [12, 17] — merge 면 N개
    agreement_count = Column(Integer, nullable=False, server_default="0")
    agreeing_sources_json = Column(JSON)                          # ["tmdb", "kmdb"]
    merge_method = Column(String(20))                              # pick | union | llm_merge | quality_pick
    applied_to_content = Column(Boolean, nullable=False, server_default="false", index=True)
    decided_by = Column(String(100))                               # "system" | username
    decided_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    content = relationship("Content")


class SeedCandidate(Base):
    """신규 콘텐츠 후보 — 매칭 실패 candidate 의 신규 Content 후보화.
    Phase C 에서 본격 사용. 본 phase 에서는 테이블만 준비."""
    __tablename__ = "seed_candidates"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("metadata_candidates.id", ondelete="CASCADE"),
                          nullable=False)
    title = Column(String(500), nullable=False)
    content_type = Column(String(20))
    evidence_urls_json = Column(JSON)
    confidence = Column(Float, nullable=False, server_default="0.0")
    reason_json = Column(JSON)                                     # ["not_found_in_internal_db", ...]
    status = Column(String(20), nullable=False, server_default="pending_review", index=True)
    # status: pending_review | approved | rejected | duplicate
    created_content_id = Column(Integer, ForeignKey("contents.id", ondelete="SET NULL"))
    decided_by = Column(String(100))
    decided_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False,
                        index=True)

    candidate = relationship("MetadataCandidate", back_populates="seed_candidates")
    created_content = relationship("Content")
