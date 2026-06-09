"""ProgrammingLink CRUD — 배치 추가/정렬/이동/override + 역참조."""
import logging
from dataclasses import dataclass
from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from .models import (
    ChildType,
    LinkSource,
    LinkStatus,
    ProgrammingLink,
    ProgrammingNode,
)
from .node_service import get_node, would_create_cycle

logger = logging.getLogger(__name__)


@dataclass
class Backref:
    parent_node_id: int
    parent_node_name: str
    link_id: int
    child_type: str
    sort_order: int
    is_pinned: bool
    status: str
    source: str
    window_start: date | None
    window_end: date | None


def check_window_within_node(
    node: ProgrammingNode,
    window_start: date | None,
    window_end: date | None,
) -> str | None:
    """배치 기간이 노드 기간을 벗어나면 경고 문자열 반환, 아니면 None."""
    if node.window_start is None and node.window_end is None:
        return None
    if window_start is None and window_end is None:
        return None
    if node.window_start and window_start and window_start < node.window_start:
        return (
            f"link window_start {window_start} < node window_start {node.window_start}"
        )
    if node.window_end and window_end and window_end > node.window_end:
        return f"link window_end {window_end} > node window_end {node.window_end}"
    return None


def _next_sort_order(db: Session, parent_node_id: int) -> int:
    result = (
        db.query(func.max(ProgrammingLink.sort_order))
        .filter(ProgrammingLink.parent_node_id == parent_node_id)
        .scalar()
    )
    return 0 if result is None else result + 1


def _assert_child_xor(child_node_id: int | None, child_content_id: int | None) -> None:
    if (child_node_id is None) == (child_content_id is None):
        raise ValueError(
            "child_node_id 또는 child_content_id 중 정확히 하나만 지정해야 합니다."
        )


def _check_duplicate(
    db: Session,
    parent_node_id: int,
    child_node_id: int | None,
    child_content_id: int | None,
    exclude_link_id: int | None = None,
) -> None:
    q = db.query(ProgrammingLink).filter(
        ProgrammingLink.parent_node_id == parent_node_id
    )
    if child_node_id is not None:
        q = q.filter(ProgrammingLink.child_node_id == child_node_id)
    else:
        q = q.filter(ProgrammingLink.child_content_id == child_content_id)
    if exclude_link_id is not None:
        q = q.filter(ProgrammingLink.id != exclude_link_id)
    if q.first() is not None:
        raise ValueError(
            f"이미 동일한 (parent={parent_node_id}, "
            f"child_node={child_node_id}, child_content={child_content_id}) 링크가 존재합니다."
        )


def add_link(
    db: Session,
    parent_node_id: int,
    *,
    child_node_id: int | None = None,
    child_content_id: int | None = None,
    sort_order: int | None = None,
    is_pinned: bool = False,
    window_start: date | None = None,
    window_end: date | None = None,
    copy_override: dict | None = None,
    source: LinkSource = LinkSource.manual,
    confidence: float | None = None,
    status: LinkStatus = LinkStatus.active,
) -> ProgrammingLink:
    _assert_child_xor(child_node_id, child_content_id)
    _check_duplicate(db, parent_node_id, child_node_id, child_content_id)

    if child_node_id is not None and would_create_cycle(db, parent_node_id, child_node_id):
        raise ValueError(
            f"node {child_node_id}를 {parent_node_id}의 자식으로 추가하면 DAG 사이클이 발생합니다."
        )

    parent = get_node(db, parent_node_id)
    if parent is not None:
        warning = check_window_within_node(parent, window_start, window_end)
        if warning:
            logger.warning("window 범위 경고 (parent_node=%d): %s", parent_node_id, warning)

    if sort_order is None:
        sort_order = _next_sort_order(db, parent_node_id)

    child_type = ChildType.node if child_node_id is not None else ChildType.content
    lnk = ProgrammingLink(
        parent_node_id=parent_node_id,
        child_type=child_type,
        child_node_id=child_node_id,
        child_content_id=child_content_id,
        sort_order=sort_order,
        is_pinned=is_pinned,
        window_start=window_start,
        window_end=window_end,
        copy_override=copy_override,
        source=source,
        confidence=confidence,
        status=status,
    )
    db.add(lnk)
    db.flush()
    return lnk


def add_links_batch(
    db: Session,
    parent_node_id: int,
    children: list[dict],
) -> list[ProgrammingLink]:
    """다건 링크 추가 — 중복은 건너뜀(멱등)."""
    added: list[ProgrammingLink] = []
    for child in children:
        child_node_id = child.get("child_node_id")
        child_content_id = child.get("child_content_id")
        try:
            _assert_child_xor(child_node_id, child_content_id)
            _check_duplicate(db, parent_node_id, child_node_id, child_content_id)
        except ValueError:
            continue  # 중복/XOR 오류 — 멱등 건너뜀
        if child_node_id is not None and would_create_cycle(db, parent_node_id, child_node_id):
            continue
        lnk = add_link(
            db,
            parent_node_id,
            child_node_id=child_node_id,
            child_content_id=child_content_id,
            sort_order=child.get("sort_order"),
            is_pinned=child.get("is_pinned", False),
            window_start=child.get("window_start"),
            window_end=child.get("window_end"),
            copy_override=child.get("copy_override"),
            source=child.get("source", LinkSource.manual),
            confidence=child.get("confidence"),
            status=child.get("status", LinkStatus.active),
        )
        added.append(lnk)
    return added


def reorder_links(
    db: Session,
    parent_node_id: int,
    ordered_link_ids: list[int],
) -> None:
    """링크 순서 재배치 — ordered_link_ids 순서대로 sort_order 0,1,2… 재할당."""
    links = (
        db.query(ProgrammingLink)
        .filter(ProgrammingLink.id.in_(ordered_link_ids))
        .all()
    )
    link_map = {lnk.id: lnk for lnk in links}
    for lnk_id in ordered_link_ids:
        lnk = link_map.get(lnk_id)
        if lnk is None:
            raise ValueError(f"link {lnk_id} not found")
        if lnk.parent_node_id != parent_node_id:
            raise ValueError(
                f"link {lnk_id}는 parent_node_id={parent_node_id}에 속하지 않습니다."
            )
    for new_order, lnk_id in enumerate(ordered_link_ids):
        link_map[lnk_id].sort_order = new_order
    db.flush()


def move_link(
    db: Session,
    link_id: int,
    new_parent_node_id: int,
) -> ProgrammingLink:
    """링크를 다른 부모 노드로 이동."""
    lnk = db.query(ProgrammingLink).filter(ProgrammingLink.id == link_id).first()
    if lnk is None:
        raise ValueError(f"link {link_id} not found")

    _check_duplicate(
        db, new_parent_node_id, lnk.child_node_id, lnk.child_content_id,
        exclude_link_id=link_id,
    )
    if lnk.child_node_id is not None and would_create_cycle(
        db, new_parent_node_id, lnk.child_node_id
    ):
        raise ValueError(
            f"link {link_id}를 node {new_parent_node_id}로 이동하면 사이클이 발생합니다."
        )

    lnk.parent_node_id = new_parent_node_id
    lnk.sort_order = _next_sort_order(db, new_parent_node_id)
    db.flush()
    return lnk


_UPDATE_ALLOWED = {
    "sort_order", "is_pinned", "window_start", "window_end",
    "copy_override", "status", "confidence",
}


def update_link(db: Session, link_id: int, **fields) -> ProgrammingLink:
    lnk = db.query(ProgrammingLink).filter(ProgrammingLink.id == link_id).first()
    if lnk is None:
        raise ValueError(f"link {link_id} not found")
    for k, v in fields.items():
        if k not in _UPDATE_ALLOWED:
            raise ValueError(f"field '{k}' is not updatable via update_link")
        setattr(lnk, k, v)

    if "window_start" in fields or "window_end" in fields:
        parent = get_node(db, lnk.parent_node_id)
        if parent is not None:
            warning = check_window_within_node(
                parent,
                fields.get("window_start", lnk.window_start),
                fields.get("window_end", lnk.window_end),
            )
            if warning:
                logger.warning("window 범위 경고 (link=%d): %s", link_id, warning)

    db.flush()
    return lnk


def remove_link(db: Session, link_id: int) -> None:
    lnk = db.query(ProgrammingLink).filter(ProgrammingLink.id == link_id).first()
    if lnk is None:
        raise ValueError(f"link {link_id} not found")
    db.delete(lnk)
    db.flush()


def get_backrefs(
    db: Session,
    *,
    child_node_id: int | None = None,
    child_content_id: int | None = None,
    include_rejected: bool = False,
) -> list[Backref]:
    """콘텐츠/노드가 어떤 부모 노드에 배치됐는지 역참조 반환."""
    if (child_node_id is None) == (child_content_id is None):
        raise ValueError(
            "child_node_id 또는 child_content_id 중 정확히 하나만 지정해야 합니다."
        )

    q = db.query(ProgrammingLink, ProgrammingNode).join(
        ProgrammingNode, ProgrammingLink.parent_node_id == ProgrammingNode.id
    )
    if child_node_id is not None:
        q = q.filter(ProgrammingLink.child_node_id == child_node_id)
    else:
        q = q.filter(ProgrammingLink.child_content_id == child_content_id)
    if not include_rejected:
        q = q.filter(ProgrammingLink.status != LinkStatus.rejected)

    return [
        Backref(
            parent_node_id=parent.id,
            parent_node_name=parent.name,
            link_id=lnk.id,
            child_type=lnk.child_type.value if hasattr(lnk.child_type, "value") else str(lnk.child_type),
            sort_order=lnk.sort_order,
            is_pinned=lnk.is_pinned,
            status=lnk.status.value if hasattr(lnk.status, "value") else str(lnk.status),
            source=lnk.source.value if hasattr(lnk.source, "value") else str(lnk.source),
            window_start=lnk.window_start,
            window_end=lnk.window_end,
        )
        for lnk, parent in q.all()
    ]
