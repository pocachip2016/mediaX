from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from shared.database import get_db
from .models import ProgrammingLink, ProgrammingNode
from . import node_service, link_service
from .schemas import (
    BackrefOut,
    LinkBatchRequest,
    LinkCreate,
    LinkMoveRequest,
    LinkOut,
    LinkReorderRequest,
    LinkUpdate,
    NodeCreate,
    NodeOut,
    NodeSetCreate,
    NodeSetOut,
    NodeTreeItem,
    NodeUpdate,
)

router = APIRouter()


def _node_or_404(db: Session, node_id: int) -> ProgrammingNode:
    node = node_service.get_node(db, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"node {node_id} not found")
    return node


def _link_or_404(db: Session, link_id: int) -> ProgrammingLink:
    lnk = db.query(ProgrammingLink).filter(ProgrammingLink.id == link_id).first()
    if lnk is None:
        raise HTTPException(status_code=404, detail=f"link {link_id} not found")
    return lnk


# ── NodeSet ────────────────────────────────────────────────────────────────────

@router.get("/sets", response_model=list[NodeSetOut])
def list_sets(status: str | None = Query(None), db: Session = Depends(get_db)):
    return node_service.list_node_sets(db, status=status)


@router.post("/sets", response_model=NodeSetOut, status_code=201)
def create_set(data: NodeSetCreate, db: Session = Depends(get_db)):
    ns = node_service.create_node_set(db, name=data.name, description=data.description)
    db.commit()
    db.refresh(ns)
    return ns


@router.post("/sets/{set_id}/publish", response_model=NodeSetOut)
def publish_set(set_id: int, db: Session = Depends(get_db)):
    try:
        ns = node_service.publish_node_set(db, set_id)
        db.commit()
        db.refresh(ns)
        return ns
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/sets/{set_id}", status_code=204)
def delete_set(set_id: int, db: Session = Depends(get_db)):
    try:
        node_service.delete_node_set(db, set_id)
        db.commit()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Node CRUD ──────────────────────────────────────────────────────────────────

@router.get("/nodes", response_model=list[NodeOut])
def list_nodes(
    set_id: int | None = Query(None),
    kind: str | None = Query(None),
    is_draft: bool | None = Query(None),
    db: Session = Depends(get_db),
):
    from .models import NodeKind
    kind_enum = NodeKind(kind) if kind else None
    return node_service.list_nodes(db, set_id=set_id, kind=kind_enum, is_draft=is_draft)


@router.post("/nodes", response_model=NodeOut, status_code=201)
def create_node(data: NodeCreate, db: Session = Depends(get_db)):
    node = node_service.create_node(
        db,
        kind=data.kind,
        name=data.name,
        set_id=data.set_id,
        slug=data.slug,
        headline_copy=data.headline_copy,
        sub_copy=data.sub_copy,
        theme_features=data.theme_features,
        rule_query=data.rule_query,
        rank_source=data.rank_source,
        rank_limit=data.rank_limit,
        is_draft=data.is_draft,
    )
    db.commit()
    db.refresh(node)
    return node


@router.get("/nodes/{node_id}", response_model=NodeOut)
def get_node(node_id: int, db: Session = Depends(get_db)):
    return _node_or_404(db, node_id)


@router.patch("/nodes/{node_id}", response_model=NodeOut)
def update_node(node_id: int, data: NodeUpdate, db: Session = Depends(get_db)):
    _node_or_404(db, node_id)
    fields = {k: v for k, v in data.model_dump().items() if v is not None}
    try:
        node = node_service.update_node(db, node_id, **fields)
        db.commit()
        db.refresh(node)
        return node
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/nodes/{node_id}", status_code=204)
def delete_node(node_id: int, db: Session = Depends(get_db)):
    _node_or_404(db, node_id)
    node_service.delete_node(db, node_id)
    db.commit()


# ── Node tree ──────────────────────────────────────────────────────────────────

@router.get("/nodes/{node_id}/tree", response_model=NodeTreeItem)
def get_node_tree(node_id: int, db: Session = Depends(get_db)):
    """노드 기준 서브트리 — 직속 node 자식을 재귀적으로 반환."""
    root = _node_or_404(db, node_id)

    def _build(n: ProgrammingNode) -> NodeTreeItem:
        from .models import ChildType, LinkStatus
        child_links = (
            db.query(ProgrammingLink)
            .filter(
                ProgrammingLink.parent_node_id == n.id,
                ProgrammingLink.status != LinkStatus.rejected,
            )
            .order_by(ProgrammingLink.sort_order)
            .all()
        )
        child_nodes = []
        content_ids = []
        for lnk in child_links:
            if lnk.child_type == ChildType.node and lnk.child_node_id:
                child_node = node_service.get_node(db, lnk.child_node_id)
                if child_node:
                    child_nodes.append(_build(child_node))
            elif lnk.child_type == ChildType.content and lnk.child_content_id:
                content_ids.append(lnk.child_content_id)
        return NodeTreeItem(node=NodeOut.model_validate(n), children=child_nodes, content_ids=content_ids)

    return _build(root)


# ── Link CRUD ──────────────────────────────────────────────────────────────────

@router.get("/nodes/{node_id}/links", response_model=list[LinkOut])
def list_links(node_id: int, db: Session = Depends(get_db)):
    _node_or_404(db, node_id)
    return (
        db.query(ProgrammingLink)
        .filter(ProgrammingLink.parent_node_id == node_id)
        .order_by(ProgrammingLink.sort_order)
        .all()
    )


@router.post("/nodes/{node_id}/links", response_model=LinkOut, status_code=201)
def add_link(node_id: int, data: LinkCreate, db: Session = Depends(get_db)):
    _node_or_404(db, node_id)
    try:
        lnk = link_service.add_link(
            db,
            node_id,
            child_node_id=data.child_node_id,
            child_content_id=data.child_content_id,
            sort_order=data.sort_order,
            is_pinned=data.is_pinned,
            window_start=data.window_start,
            window_end=data.window_end,
            copy_override=data.copy_override,
            source=data.source,
            confidence=data.confidence,
            status=data.status,
        )
        db.commit()
        db.refresh(lnk)
        return lnk
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/nodes/{node_id}/links/batch", response_model=list[LinkOut], status_code=201)
def add_links_batch(node_id: int, data: LinkBatchRequest, db: Session = Depends(get_db)):
    _node_or_404(db, node_id)
    children = [item.model_dump() for item in data.children]
    added = link_service.add_links_batch(db, node_id, children)
    db.commit()
    for lnk in added:
        db.refresh(lnk)
    return added


@router.post("/nodes/{node_id}/links/reorder", status_code=204)
def reorder_links(node_id: int, data: LinkReorderRequest, db: Session = Depends(get_db)):
    _node_or_404(db, node_id)
    try:
        link_service.reorder_links(db, node_id, data.ordered_link_ids)
        db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/links/{link_id}", response_model=LinkOut)
def update_link(link_id: int, data: LinkUpdate, db: Session = Depends(get_db)):
    _link_or_404(db, link_id)
    fields = {k: v for k, v in data.model_dump().items() if v is not None}
    try:
        lnk = link_service.update_link(db, link_id, **fields)
        db.commit()
        db.refresh(lnk)
        return lnk
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/links/{link_id}/move", response_model=LinkOut)
def move_link(link_id: int, data: LinkMoveRequest, db: Session = Depends(get_db)):
    _link_or_404(db, link_id)
    try:
        lnk = link_service.move_link(db, link_id, data.new_parent_node_id)
        db.commit()
        db.refresh(lnk)
        return lnk
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/links/{link_id}", status_code=204)
def delete_link(link_id: int, db: Session = Depends(get_db)):
    _link_or_404(db, link_id)
    link_service.remove_link(db, link_id)
    db.commit()


# ── Backref ────────────────────────────────────────────────────────────────────

@router.get("/backref/content/{content_id}", response_model=list[BackrefOut])
def get_content_backrefs(
    content_id: int,
    include_rejected: bool = Query(False),
    db: Session = Depends(get_db),
):
    refs = link_service.get_backrefs(
        db, child_content_id=content_id, include_rejected=include_rejected
    )
    return [BackrefOut(**vars(r)) for r in refs]


@router.get("/backref/node/{node_id}", response_model=list[BackrefOut])
def get_node_backrefs(
    node_id: int,
    include_rejected: bool = Query(False),
    db: Session = Depends(get_db),
):
    refs = link_service.get_backrefs(
        db, child_node_id=node_id, include_rejected=include_rejected
    )
    return [BackrefOut(**vars(r)) for r in refs]
