import enum

from sqlalchemy import (
    Boolean, CheckConstraint, Column, Date, DateTime,
    Enum as SAEnum, Float, ForeignKey, Index, Integer,
    String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.sql import func

from shared.database import Base


class NodeKind(str, enum.Enum):
    container = "container"
    rule = "rule"
    rank = "rank"
    manual = "manual"


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

    __table_args__ = (
        Index("ix_programming_nodes_set_id", "set_id"),
        Index("ix_programming_nodes_kind", "kind"),
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
