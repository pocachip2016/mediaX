import re
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from api.programming.metadata.models import Content
from api.programming.scheduling.models import (
    ChildType,
    LinkSource,
    LinkStatus,
    NodeKind,
    ProgrammingLink,
    ProgrammingNode,
)
from .models import ContentDistribution, DeviceVariant, Service
from .schemas import ServiceCategoryCreate, ServiceCategoryUpdate, ServiceCategoryItemCreate, ReorderRequest

_OTT_CHANNELS = ["ott_watcha", "ott_netflix", "ott_wave", "ott_tving"]

# service_categories.category_type 중 rank 종류
_RANK_CATEGORY_TYPES = {"top", "rank", "top10", "popular", "trending"}

# 큐레이션 노드 식별 술어: kind∈{manual,rank} AND set_id IS NULL
_CURATION_KINDS = (NodeKind.manual, NodeKind.rank)


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "node"


def _unique_slug(db: Session, base: str) -> str:
    slug = f"svc_{base}"
    if not db.query(ProgrammingNode).filter(ProgrammingNode.slug == slug).first():
        return slug
    n = 1
    while True:
        candidate = f"svc_{base}_{n}"
        if not db.query(ProgrammingNode).filter(ProgrammingNode.slug == candidate).first():
            return candidate
        n += 1


def _kind_from_category_type(category_type: str) -> NodeKind:
    return NodeKind.rank if category_type.lower() in _RANK_CATEGORY_TYPES else NodeKind.manual


def _node_to_category_view(node: ProgrammingNode) -> SimpleNamespace:
    """ProgrammingNode → ServiceCategoryOut 형태 SimpleNamespace."""
    meta = (node.theme_features or {}).get("_curation", {}) if node.theme_features else {}
    # theme_features는 _curation 제외한 실제 사용자 지정 값
    user_features = {k: v for k, v in (node.theme_features or {}).items() if not k.startswith("_")} or None
    return SimpleNamespace(
        id=node.id,
        name=node.name,
        category_type=meta.get("category_type", node.kind.value),
        platform=meta.get("platform", ""),
        position=meta.get("position", 0),
        is_active=node.is_active,
        headline_copy=node.headline_copy,
        sub_copy=node.sub_copy,
        theme_features=user_features,
        source_mode=meta.get("source_mode", "manual"),
        reference_external_id=meta.get("reference_external_id"),
        is_draft=node.is_draft,
        created_at=node.created_at,
        updated_at=node.updated_at,
    )


def _update_curation_meta(node: ProgrammingNode, updates: dict) -> None:
    """theme_features["_curation"] 메타를 병합."""
    tf = dict(node.theme_features) if node.theme_features else {}
    meta = dict(tf.get("_curation") or {})
    meta.update({k: v for k, v in updates.items() if v is not None})
    tf["_curation"] = meta
    node.theme_features = tf


def get_services(db: Session, kind: str | None = None) -> list[Service]:
    q = db.query(Service).filter(Service.is_active == True)  # noqa: E712
    if kind:
        q = q.filter(Service.kind == kind)
    return q.order_by(Service.position).all()


def get_service_by_code(db: Session, code: str) -> Service | None:
    return db.query(Service).filter(Service.code == code).first()


def get_channels_for_content(db: Session, content_id: int) -> list[ContentDistribution]:
    return (
        db.query(ContentDistribution)
        .filter(ContentDistribution.content_id == content_id)
        .order_by(ContentDistribution.channel)
        .all()
    )


def get_categories(db: Session, platform: str | None = None, is_active: bool | None = None):
    nodes = (
        db.query(ProgrammingNode)
        .filter(
            ProgrammingNode.kind.in_(_CURATION_KINDS),
            ProgrammingNode.set_id.is_(None),
        )
        .all()
    )
    views = [_node_to_category_view(n) for n in nodes]
    if platform:
        views = [v for v in views if v.platform == platform]
    if is_active is not None:
        views = [v for v in views if v.is_active == is_active]
    views.sort(key=lambda v: v.position)
    return views


def get_devices_for_content(db: Session, content_id: int) -> list[DeviceVariant]:
    return (
        db.query(DeviceVariant)
        .filter(DeviceVariant.content_id == content_id)
        .order_by(DeviceVariant.device_type)
        .all()
    )


def create_category(db: Session, data: ServiceCategoryCreate) -> SimpleNamespace:
    kind = _kind_from_category_type(data.category_type)
    user_features = data.theme_features
    tf: dict = dict(user_features) if user_features else {}
    tf["_curation"] = {
        "category_type": data.category_type,
        "platform": data.platform,
        "position": data.position,
        "source_mode": data.source_mode,
        "reference_external_id": data.reference_external_id,
    }
    slug = _unique_slug(db, _slugify(data.name))
    node = ProgrammingNode(
        kind=kind,
        name=data.name,
        slug=slug,
        headline_copy=data.headline_copy,
        sub_copy=data.sub_copy,
        theme_features=tf,
        is_active=data.is_active,
        is_draft=data.is_draft,
        set_id=None,
    )
    db.add(node)
    db.commit()
    db.refresh(node)
    return _node_to_category_view(node)


def get_category_or_404(db: Session, category_id: int) -> ProgrammingNode:
    node = (
        db.query(ProgrammingNode)
        .filter(
            ProgrammingNode.id == category_id,
            ProgrammingNode.kind.in_(_CURATION_KINDS),
            ProgrammingNode.set_id.is_(None),
        )
        .first()
    )
    if not node:
        raise HTTPException(status_code=404, detail="Category not found")
    return node


def get_category_with_items(db: Session, category_id: int) -> SimpleNamespace:
    node = get_category_or_404(db, category_id)
    rows = (
        db.query(ProgrammingLink, Content.title)
        .join(Content, ProgrammingLink.child_content_id == Content.id)
        .filter(
            ProgrammingLink.parent_node_id == category_id,
            ProgrammingLink.child_type == ChildType.content,
            ProgrammingLink.status != LinkStatus.rejected,
        )
        .order_by(ProgrammingLink.sort_order)
        .all()
    )
    items = [
        SimpleNamespace(
            id=lnk.id,
            category_id=category_id,
            content_id=lnk.child_content_id,
            content_title=title,
            rank=lnk.sort_order,
            score=lnk.confidence,
            added_at=lnk.created_at,
        )
        for lnk, title in rows
    ]
    view = _node_to_category_view(node)
    view.items = items
    return view


def update_category(db: Session, category_id: int, data: ServiceCategoryUpdate) -> SimpleNamespace:
    node = get_category_or_404(db, category_id)
    patch = data.model_dump(exclude_unset=True)

    if "name" in patch:
        node.name = patch["name"]
    if "headline_copy" in patch:
        node.headline_copy = patch["headline_copy"]
    if "sub_copy" in patch:
        node.sub_copy = patch["sub_copy"]
    if "is_active" in patch:
        node.is_active = patch["is_active"]
    if "is_draft" in patch:
        node.is_draft = patch["is_draft"]

    # theme_features: 사용자 지정 키만 교체, _curation 유지
    if "theme_features" in patch:
        tf = dict(node.theme_features) if node.theme_features else {}
        meta = tf.get("_curation", {})
        tf = dict(patch["theme_features"]) if patch["theme_features"] else {}
        tf["_curation"] = meta
        node.theme_features = tf

    # category_type → kind 재파생
    if "category_type" in patch:
        node.kind = _kind_from_category_type(patch["category_type"])

    # _curation 메타 갱신
    curation_patch = {k: patch[k] for k in ("category_type", "platform", "position", "source_mode", "reference_external_id") if k in patch}
    if curation_patch:
        _update_curation_meta(node, curation_patch)

    db.commit()
    db.refresh(node)
    return _node_to_category_view(node)


def delete_category(db: Session, category_id: int) -> dict:
    node = get_category_or_404(db, category_id)
    db.delete(node)
    db.commit()
    return {"id": category_id, "deleted": True}


def add_item(db: Session, category_id: int, data: ServiceCategoryItemCreate) -> SimpleNamespace:
    get_category_or_404(db, category_id)
    existing = (
        db.query(ProgrammingLink)
        .filter(
            ProgrammingLink.parent_node_id == category_id,
            ProgrammingLink.child_type == ChildType.content,
            ProgrammingLink.child_content_id == data.content_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Item already in category")
    lnk = ProgrammingLink(
        parent_node_id=category_id,
        child_type=ChildType.content,
        child_content_id=data.content_id,
        sort_order=data.rank,
        confidence=data.score,
        source=LinkSource.manual,
        status=LinkStatus.active,
    )
    db.add(lnk)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Item already in category")
    db.refresh(lnk)
    content = db.query(Content).filter(Content.id == data.content_id).first()
    return SimpleNamespace(
        id=lnk.id,
        category_id=category_id,
        content_id=data.content_id,
        content_title=content.title if content else None,
        rank=lnk.sort_order,
        score=lnk.confidence,
        added_at=lnk.created_at,
    )


def remove_item(db: Session, category_id: int, item_id: int) -> dict:
    lnk = (
        db.query(ProgrammingLink)
        .filter(
            ProgrammingLink.id == item_id,
            ProgrammingLink.parent_node_id == category_id,
            ProgrammingLink.child_type == ChildType.content,
        )
        .first()
    )
    if not lnk:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(lnk)
    db.commit()
    return {"id": item_id, "deleted": True}


def reorder_items(db: Session, category_id: int, data: ReorderRequest) -> dict:
    get_category_or_404(db, category_id)
    updated = 0
    for entry in data.items:
        lnk = (
            db.query(ProgrammingLink)
            .filter(
                ProgrammingLink.id == entry.id,
                ProgrammingLink.parent_node_id == category_id,
                ProgrammingLink.child_type == ChildType.content,
            )
            .first()
        )
        if lnk:
            lnk.sort_order = entry.rank
            updated += 1
    db.commit()
    return {"updated": updated}




def get_sync_status(db: Session) -> list[dict]:
    """4개 OTT 채널의 동기화 현황. 빈 DB에서도 4 row 반환."""
    rows = (
        db.query(
            ContentDistribution.channel,
            func.count(ContentDistribution.id).label("total_rows"),
            func.max(ContentDistribution.synced_at).label("last_synced_at"),
        )
        .filter(ContentDistribution.channel.in_(_OTT_CHANNELS))
        .group_by(ContentDistribution.channel)
        .all()
    )
    result = {r.channel: r for r in rows}
    return [
        {
            "channel": ch,
            "total_rows": result[ch].total_rows if ch in result else 0,
            "last_synced_at": result[ch].last_synced_at if ch in result else None,
        }
        for ch in _OTT_CHANNELS
    ]
