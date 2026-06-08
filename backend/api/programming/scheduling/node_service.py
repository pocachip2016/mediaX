"""ProgrammingNodeSet / ProgrammingNode CRUD + 사이클 가드 + read-time 멤버 산출."""
from collections import deque
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from .models import (
    LinkStatus,
    NodeKind,
    ProgrammingLink,
    ProgrammingNode,
    ProgrammingNodeSet,
)


# ── NodeSet CRUD ───────────────────────────────────────────────────────────────

def create_node_set(db: Session, name: str, description: str | None = None) -> ProgrammingNodeSet:
    ns = ProgrammingNodeSet(name=name, description=description, status="draft")
    db.add(ns)
    db.flush()
    return ns


def get_node_set(db: Session, set_id: int) -> ProgrammingNodeSet | None:
    return db.query(ProgrammingNodeSet).filter(ProgrammingNodeSet.id == set_id).first()


def list_node_sets(db: Session, status: str | None = None) -> list[ProgrammingNodeSet]:
    q = db.query(ProgrammingNodeSet)
    if status:
        q = q.filter(ProgrammingNodeSet.status == status)
    return q.order_by(ProgrammingNodeSet.id).all()


def publish_node_set(db: Session, set_id: int) -> ProgrammingNodeSet:
    from datetime import datetime, timezone
    ns = db.query(ProgrammingNodeSet).filter(ProgrammingNodeSet.id == set_id).first()
    if ns is None:
        raise ValueError(f"node_set {set_id} not found")
    ns.status = "published"
    ns.published_at = datetime.now(timezone.utc)
    db.flush()
    return ns


def delete_node_set(db: Session, set_id: int) -> None:
    ns = db.query(ProgrammingNodeSet).filter(ProgrammingNodeSet.id == set_id).first()
    if ns is None:
        raise ValueError(f"node_set {set_id} not found")
    db.delete(ns)
    db.flush()


# ── Node CRUD ──────────────────────────────────────────────────────────────────

def create_node(
    db: Session,
    kind: NodeKind,
    name: str,
    *,
    set_id: int | None = None,
    slug: str | None = None,
    headline_copy: str | None = None,
    sub_copy: str | None = None,
    theme_features: dict | None = None,
    rule_query: dict | None = None,
    rank_source: str | None = None,
    rank_limit: int | None = None,
    is_draft: bool = False,
) -> ProgrammingNode:
    node = ProgrammingNode(
        kind=kind,
        name=name,
        set_id=set_id,
        slug=slug,
        headline_copy=headline_copy,
        sub_copy=sub_copy,
        theme_features=theme_features,
        rule_query=rule_query,
        rank_source=rank_source,
        rank_limit=rank_limit,
        is_draft=is_draft,
    )
    db.add(node)
    db.flush()
    return node


def get_node(db: Session, node_id: int) -> ProgrammingNode | None:
    return db.query(ProgrammingNode).filter(ProgrammingNode.id == node_id).first()


def list_nodes(
    db: Session,
    set_id: int | None = None,
    kind: NodeKind | None = None,
    is_draft: bool | None = None,
) -> list[ProgrammingNode]:
    q = db.query(ProgrammingNode)
    if set_id is not None:
        q = q.filter(ProgrammingNode.set_id == set_id)
    if kind is not None:
        q = q.filter(ProgrammingNode.kind == kind)
    if is_draft is not None:
        q = q.filter(ProgrammingNode.is_draft == is_draft)
    return q.order_by(ProgrammingNode.id).all()


def update_node(db: Session, node_id: int, **fields: Any) -> ProgrammingNode:
    node = db.query(ProgrammingNode).filter(ProgrammingNode.id == node_id).first()
    if node is None:
        raise ValueError(f"node {node_id} not found")
    allowed = {
        "name", "slug", "headline_copy", "sub_copy", "theme_features",
        "rule_query", "rank_source", "rank_limit", "window_start", "window_end",
        "is_active", "is_draft", "set_id",
    }
    for k, v in fields.items():
        if k not in allowed:
            raise ValueError(f"field '{k}' not updatable via update_node")
        setattr(node, k, v)
    db.flush()
    return node


def delete_node(db: Session, node_id: int) -> None:
    """노드 삭제 — 연결된 링크(부모·자식 모두)도 cascade 삭제됨."""
    node = db.query(ProgrammingNode).filter(ProgrammingNode.id == node_id).first()
    if node is None:
        raise ValueError(f"node {node_id} not found")
    db.delete(node)
    db.flush()


# ── 사이클 가드 ────────────────────────────────────────────────────────────────

def _ancestor_ids(db: Session, node_id: int) -> set[int]:
    """node_id의 모든 조상 node_id 집합을 BFS로 반환."""
    visited: set[int] = set()
    queue = deque([node_id])
    while queue:
        cur = queue.popleft()
        if cur in visited:
            continue
        visited.add(cur)
        parents = (
            db.query(ProgrammingLink.parent_node_id)
            .filter(
                ProgrammingLink.child_node_id == cur,
                ProgrammingLink.status != LinkStatus.rejected,
            )
            .all()
        )
        queue.extend(p[0] for p in parents)
    return visited


def would_create_cycle(db: Session, parent_node_id: int, child_node_id: int) -> bool:
    """child_node_id를 parent_node_id의 자식으로 추가하면 사이클이 생기는지 확인."""
    if parent_node_id == child_node_id:
        return True
    ancestors = _ancestor_ids(db, parent_node_id)
    return child_node_id in ancestors


# ── read-time 멤버 산출 ────────────────────────────────────────────────────────

@dataclass
class NodeMember:
    content_id: int
    sort_order: int
    is_pinned: bool
    source: str
    reason: str | None = None


def compute_members(db: Session, node: ProgrammingNode) -> list[NodeMember]:
    """
    노드의 최종 노출 멤버 = rule 산출(Tier 0) ∪ active 링크(manual/ai-confirmed).
    - suggested/rejected 링크 제외
    - is_pinned 우선, 이후 sort_order
    - child_content_id 기준 dedupe (is_pinned=True 우선)
    """
    members: dict[int, NodeMember] = {}

    # 1. active content links
    links = (
        db.query(ProgrammingLink)
        .filter(
            ProgrammingLink.parent_node_id == node.id,
            ProgrammingLink.child_type == "content",
            ProgrammingLink.status == LinkStatus.active,
        )
        .order_by(
            ProgrammingLink.is_pinned.desc(),
            ProgrammingLink.sort_order,
        )
        .all()
    )
    for lnk in links:
        cid = lnk.child_content_id
        if cid is None:
            continue
        if cid not in members or (lnk.is_pinned and not members[cid].is_pinned):
            members[cid] = NodeMember(
                content_id=cid,
                sort_order=lnk.sort_order,
                is_pinned=lnk.is_pinned,
                source=lnk.source.value if hasattr(lnk.source, "value") else str(lnk.source),
            )

    # 2. rule 산출 (kind=rule → Tier 0 rule_query 기반)
    if node.kind == NodeKind.rule and node.rule_query:
        rule_results = _apply_rule_query(db, node.rule_query)
        for i, result in enumerate(rule_results):
            cid = result if isinstance(result, int) else result.content_id
            reason = None if isinstance(result, int) else result.reason
            if cid not in members:
                members[cid] = NodeMember(
                    content_id=cid,
                    sort_order=i,
                    is_pinned=False,
                    source="rule",
                    reason=reason,
                )

    # 3. rank 산출 (kind=rank → sort by popularity/recency, limit N)
    if node.kind == NodeKind.rank:
        rank_ids = _apply_rank(db, node.rank_source, node.rank_limit)
        for i, cid in enumerate(rank_ids):
            if cid not in members:
                members[cid] = NodeMember(
                    content_id=cid,
                    sort_order=i,
                    is_pinned=False,
                    source="rule",
                )

    return sorted(
        members.values(),
        key=lambda m: (not m.is_pinned, m.sort_order),
    )


def _apply_rule_query(db: Session, rule_query: dict):
    """Tier 0 규칙 필터 — rule_engine.apply_rule_query 위임."""
    from .rule_engine import apply_rule_query
    return apply_rule_query(db, rule_query)


def _apply_rank(db: Session, rank_source: str | None, limit: int | None) -> list[int]:
    """rank 노드 멤버 산출 stub — 인기순 content_id 반환."""
    from api.programming.metadata.models import Content
    q = db.query(Content.id).filter(Content.current_stage >= 4)
    if rank_source == "recency":
        q = q.order_by(Content.id.desc())
    else:
        q = q.order_by(Content.id.desc())
    if limit:
        q = q.limit(limit)
    return [row[0] for row in q.all()]
