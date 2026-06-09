import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, CheckConstraint, Column, Date, DateTime,
    Enum as SAEnum, Float, ForeignKey, Index, Integer,
    String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.sql import func

from shared.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class NodeKind(str, enum.Enum):
    container = "container"
    rule = "rule"
    rank = "rank"
    manual = "manual"


class AutoStage(str, enum.Enum):
    P1_DEFINE      = "p1_define"       # 조건정의 (rule_query+headline+window) = intake
    P2_CANDIDATE   = "p2_candidate"    # Tier0 후보생성 (read-time, 저장 안 함)
    P3_MATCH       = "p3_match"        # Tier1+2 AI매칭 → suggested 링크 저장
    P4_AUTOCONFIRM = "p4_autoconfirm"  # confidence ≥ threshold → active, 미달 잔류
    P5_CONFLICT    = "p5_conflict"     # 노출 window 충돌 검사
    P6_PUBLISH     = "p6_publish"      # NodeSet status=published


class AutoEventType(str, enum.Enum):
    ENTERED    = "entered"
    COMPLETED  = "completed"
    SKIPPED    = "skipped"
    FAILED     = "failed"
    ADVANCED   = "advanced"
    REJECTED   = "rejected"


class ChildType(str, enum.Enum):
    node = "node"
    content = "content"


class LinkSource(str, enum.Enum):
    manual = "manual"
    ai = "ai"
    rule = "rule"


class LinkStatus(str, enum.Enum):
    active = "active"
    suggested = "suggested"
    rejected = "rejected"


class ProgrammingNodeSet(Base):
    __tablename__ = "programming_node_sets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(String(1000), nullable=True)
    status = Column(String(20), nullable=False, server_default="draft")
    published_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ProgrammingNode(Base):
    __tablename__ = "programming_nodes"

    id = Column(Integer, primary_key=True, index=True)
    set_id = Column(Integer, ForeignKey("programming_node_sets.id", ondelete="SET NULL"), nullable=True)
    kind = Column(SAEnum(NodeKind, name="node_kind"), nullable=False)
    name = Column(String(200), nullable=False)
    slug = Column(String(220), nullable=True)
    headline_copy = Column(String(200), nullable=True)
    sub_copy = Column(String(300), nullable=True)
    theme_features = Column(JSON, nullable=True)
    rule_query = Column(JSON, nullable=True)
    rank_source = Column(String(50), nullable=True)
    rank_limit = Column(Integer, nullable=True)
    window_start = Column(Date, nullable=True)
    window_end = Column(Date, nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="true")
    is_draft = Column(Boolean, nullable=False, server_default="false")
    # bge-m3 1024-dim 벡터 캐시 (theme_features + headline_copy 임베딩, ingest/edit-time precompute)
    embed_theme = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # ── 자동편성 파이프라인 추적 필드 (ADR-012) ───────────────────────────────
    auto_enabled    = Column(Boolean, nullable=False, default=False, server_default="false")  # 자동편성 파이프라인 대상 여부
    auto_stage      = Column(SAEnum(AutoStage, name="auto_stage"), nullable=True)             # 현재 P-stage (None=미시작)
    auto_hold       = Column(Boolean, nullable=False, default=False, server_default="false")  # AUTO claim 제외 (재검수·hold)
    auto_claimed_at = Column(DateTime(timezone=True), nullable=True)                         # in-flight 마킹 (visibility_timeout 기준)
    auto_skipped_at = Column(DateTime(timezone=True), nullable=True)                         # P4 잔류: threshold 미달, 임계값 변경 전까지 재진입 안 함
    schedule_score  = Column(Float, nullable=True)                                            # 편성 완성도 0~100 (P5 진입 시 갱신)

    __table_args__ = (
        Index("ix_programming_nodes_set_id", "set_id"),
        Index("ix_programming_nodes_kind", "kind"),
        Index("ix_programming_nodes_auto_enabled", "auto_enabled"),
        Index("ix_programming_nodes_auto_stage", "auto_stage"),
    )


class ProgrammingLink(Base):
    __tablename__ = "programming_links"

    id = Column(Integer, primary_key=True, index=True)
    parent_node_id = Column(Integer, ForeignKey("programming_nodes.id", ondelete="CASCADE"), nullable=False)
    child_type = Column(SAEnum(ChildType, name="child_type"), nullable=False)
    child_node_id = Column(Integer, ForeignKey("programming_nodes.id", ondelete="CASCADE"), nullable=True)
    child_content_id = Column(Integer, ForeignKey("contents.id", ondelete="CASCADE"), nullable=True)
    sort_order = Column(Integer, nullable=False, server_default="0")
    is_pinned = Column(Boolean, nullable=False, server_default="false")
    window_start = Column(Date, nullable=True)
    window_end = Column(Date, nullable=True)
    copy_override = Column(JSON, nullable=True)
    source = Column(SAEnum(LinkSource, name="link_source"), nullable=False, server_default="manual")
    confidence = Column(Float, nullable=True)
    status = Column(SAEnum(LinkStatus, name="link_status"), nullable=False, server_default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        # 정확히 하나의 child만 가져야 함
        CheckConstraint(
            "(child_node_id IS NULL) != (child_content_id IS NULL)",
            name="ck_programming_links_child_xor",
        ),
        UniqueConstraint("parent_node_id", "child_node_id", name="uq_link_parent_child_node"),
        UniqueConstraint("parent_node_id", "child_content_id", name="uq_link_parent_child_content"),
        Index("ix_programming_links_parent_node_id", "parent_node_id"),
        Index("ix_programming_links_child_content_id", "child_content_id"),
        Index("ix_programming_links_parent_sort", "parent_node_id", "sort_order"),
    )


class SchedulingStageEvent(Base):
    """자동편성 파이프라인 노드 단계 전이 SSOT — ADR-012. StageEvent 패턴 복제."""
    __tablename__ = "scheduling_stage_events"

    id           = Column(Integer, primary_key=True)
    node_id      = Column(Integer, ForeignKey("programming_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    stage        = Column(SAEnum(AutoStage,     name="auto_stage",     create_type=False, values_callable=lambda x: [e.value for e in x]), nullable=False, index=True)
    event_type   = Column(SAEnum(AutoEventType, name="auto_event_type",                  values_callable=lambda x: [e.value for e in x]), nullable=False, index=True)
    source       = Column(String(100), nullable=True)   # beat/event/user/system
    started_at   = Column(DateTime(timezone=True), default=_utcnow, index=True)
    ended_at     = Column(DateTime(timezone=True), nullable=True)
    latency_ms   = Column(Integer, nullable=True)
    payload_json = Column(JSON, nullable=True)           # 단계별 부가 정보 (후보 수, 링크 수 등) ≤4KB
    error_text   = Column(Text, nullable=True)
    actor        = Column(String(100), nullable=False, default="system")

    __table_args__ = (
        Index("ix_scheduling_stage_event_node_stage",   "node_id", "stage"),
        Index("ix_scheduling_stage_event_type_started", "event_type", "started_at"),
    )


class ScheduleAutoPolicy(Base):
    """자동편성 정책 — ADR-012. 싱글톤(id=1)."""
    __tablename__ = "schedule_auto_policy"

    id = Column(Integer, primary_key=True, default=1)
    # per-stage AUTO 토글 (False = 해당 단계에서 자동 전이 안 함)
    p2_auto = Column(Boolean, nullable=False, default=True,  server_default="true")
    p3_auto = Column(Boolean, nullable=False, default=True,  server_default="true")
    p4_auto = Column(Boolean, nullable=False, default=True,  server_default="true")
    p5_auto = Column(Boolean, nullable=False, default=True,  server_default="true")
    p6_auto = Column(Boolean, nullable=False, default=False, server_default="false")  # 최종 발행은 기본 수동
    # P4 자동확정 임계값 (confidence ≥ 이 값인 suggested 링크만 auto-active)
    confidence_threshold = Column(Float,    nullable=False, default=0.5,   server_default="0.5")
    # AUTO tick 마스터 스위치 (기본 꺼짐 — 운영자 명시 활성)
    auto_tick_enabled  = Column(Boolean, nullable=False, default=False, server_default="false")
    batch_size         = Column(Integer, nullable=False, default=20,    server_default="20")    # tick 당 claim 상한
    visibility_timeout = Column(Integer, nullable=False, default=300,   server_default="300")  # stuck 재claim 초
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
