from collections import deque

from sqlalchemy.orm import Session
from sqlalchemy import func

from api.programming.catalog import service
from api.programming.scheduling.models import (
    ChildType,
    LinkSource,
    LinkStatus,
    NodeKind,
    ProgrammingLink,
    ProgrammingNode,
    ProgrammingNodeSet,
)


def list_sets(db: Session) -> list[dict]:
    sets = db.query(ProgrammingNodeSet).order_by(ProgrammingNodeSet.id).all()
    result = []
    for s in sets:
        count = (
            db.query(func.count(ProgrammingNode.id))
            .filter(ProgrammingNode.set_id == s.id, ProgrammingNode.kind == NodeKind.container)
            .scalar()
            or 0
        )
        result.append({
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "category_count": count,
            "created_at": s.created_at,
            "updated_at": s.updated_at,
        })
    return result


def commit_draft(db: Session, name: str, description: str | None = None) -> dict:
    s = ProgrammingNodeSet(name=name, description=description)
    db.add(s)
    db.flush()
    loaded = _copy_tree(db, src_set_id=None, dst_set_id=s.id)
    db.flush()
    count = (
        db.query(func.count(ProgrammingNode.id))
        .filter(ProgrammingNode.set_id == s.id, ProgrammingNode.kind == NodeKind.container)
        .scalar()
        or 0
    )
    return {
        "id": s.id,
        "name": s.name,
        "description": s.description,
        "category_count": count,
        "created_at": s.created_at,
        "updated_at": s.updated_at,
        "_loaded": loaded,
    }


def preview_load_set(db: Session, set_id: int) -> dict:
    """병합 시 신규/중복 노드 수를 미리 계산 (DB 변경 없음)."""
    s = db.query(ProgrammingNodeSet).filter(ProgrammingNodeSet.id == set_id).first()
    if s is None:
        raise ValueError(f"set_id={set_id} not found")

    nodes = service.list_tree_by_set(db, set_id=set_id)
    dup_count = 0

    def _walk(items: list[dict], pid: int | None) -> None:
        nonlocal dup_count
        for item in items:
            name = (item.get("name") or "").strip()
            if not name:
                continue
            if pid is not None:
                existing = (
                    db.query(ProgrammingNode)
                    .join(
                        ProgrammingLink,
                        (ProgrammingLink.child_node_id == ProgrammingNode.id)
                        & (ProgrammingLink.parent_node_id == pid)
                        & (ProgrammingLink.child_type == ChildType.node),
                    )
                    .filter(ProgrammingNode.name == name, ProgrammingNode.set_id.is_(None))
                    .first()
                )
            else:
                child_ids_q = db.query(ProgrammingLink.child_node_id).filter(
                    ProgrammingLink.child_type == ChildType.node,
                    ProgrammingLink.child_node_id.isnot(None),
                )
                existing = (
                    db.query(ProgrammingNode)
                    .filter(
                        ProgrammingNode.name == name,
                        ProgrammingNode.kind == NodeKind.container,
                        ProgrammingNode.set_id.is_(None),
                        ~ProgrammingNode.id.in_(child_ids_q),
                    )
                    .first()
                )
            if existing is not None:
                dup_count += 1
                _walk(item.get("children") or [], existing.id)

    _walk(nodes, None)
    total = (
        db.query(func.count(ProgrammingNode.id))
        .filter(ProgrammingNode.set_id == set_id, ProgrammingNode.kind == NodeKind.container)
        .scalar()
        or 0
    )
    return {"new_count": total - dup_count, "dup_count": dup_count}


def load_set(
    db: Session,
    set_id: int,
    mode: str = "replace",
    dup_policy: str = "merge",
) -> tuple[int, int]:
    """세트를 draft로 불러오기.

    - replace: draft 전체 비우고 세트 트리 복사
    - merge: draft 유지하고 세트 트리를 dup_policy에 따라 병합
    반환: (cleared, loaded)  — merge 시 cleared=0
    """
    s = db.query(ProgrammingNodeSet).filter(ProgrammingNodeSet.id == set_id).first()
    if s is None:
        raise ValueError(f"set_id={set_id} not found")

    if mode == "merge":
        nodes = service.list_tree_by_set(db, set_id=set_id)
        created, _skipped, _overwritten = service.bulk_create_categories(
            db, nodes, parent_id=None, dup_policy=dup_policy
        )
        db.flush()
        return 0, created

    cleared = clear_draft(db)
    db.flush()
    loaded = _copy_tree(db, src_set_id=set_id, dst_set_id=None)
    db.flush()
    return cleared, loaded


def clear_draft(db: Session) -> int:
    """draft 노드(set_id=None, kind=container) 전체 삭제.

    SQLite FK CASCADE 비활성 환경이므로 링크를 먼저 명시적으로 삭제한다.
    """
    draft_ids = [
        r[0]
        for r in db.query(ProgrammingNode.id)
        .filter(ProgrammingNode.set_id.is_(None), ProgrammingNode.kind == NodeKind.container)
        .all()
    ]
    if not draft_ids:
        return 0

    db.query(ProgrammingLink).filter(
        ProgrammingLink.parent_node_id.in_(draft_ids)
    ).delete(synchronize_session=False)
    db.query(ProgrammingLink).filter(
        ProgrammingLink.child_node_id.in_(draft_ids)
    ).delete(synchronize_session=False)
    count = (
        db.query(ProgrammingNode)
        .filter(ProgrammingNode.set_id.is_(None), ProgrammingNode.kind == NodeKind.container)
        .delete(synchronize_session=False)
    )
    db.flush()
    return count


def update_set(
    db: Session,
    set_id: int,
    name: str | None = None,
    description: str | None = None,
) -> dict:
    s = db.query(ProgrammingNodeSet).filter(ProgrammingNodeSet.id == set_id).first()
    if s is None:
        raise ValueError(f"set_id={set_id} not found")
    if name is not None:
        s.name = name
    if description is not None:
        s.description = description
    db.flush()
    count = (
        db.query(func.count(ProgrammingNode.id))
        .filter(ProgrammingNode.set_id == set_id, ProgrammingNode.kind == NodeKind.container)
        .scalar()
        or 0
    )
    return {
        "id": s.id,
        "name": s.name,
        "description": s.description,
        "category_count": count,
        "created_at": s.created_at,
        "updated_at": s.updated_at,
    }


def delete_set(db: Session, set_id: int) -> None:
    s = db.query(ProgrammingNodeSet).filter(ProgrammingNodeSet.id == set_id).first()
    if s is None:
        raise ValueError(f"set_id={set_id} not found")
    db.delete(s)
    db.flush()


def _copy_tree(db: Session, src_set_id: int | None, dst_set_id: int | None) -> int:
    """src 세트(또는 draft)의 노드 트리를 dst 세트(또는 draft)로 복사.

    BFS로 부모→자식 순서 보장. ProgrammingNode/Link 기반.
    """
    if src_set_id is None:
        src_nodes = (
            db.query(ProgrammingNode)
            .filter(ProgrammingNode.set_id.is_(None), ProgrammingNode.kind == NodeKind.container)
            .all()
        )
    else:
        src_nodes = (
            db.query(ProgrammingNode)
            .filter(ProgrammingNode.set_id == src_set_id, ProgrammingNode.kind == NodeKind.container)
            .all()
        )

    src_ids = {n.id for n in src_nodes}
    if not src_ids:
        return 0

    # 소스 집합 내부 node-type 링크만 수집
    src_links = (
        db.query(ProgrammingLink)
        .filter(
            ProgrammingLink.child_type == ChildType.node,
            ProgrammingLink.child_node_id.in_(src_ids),
            ProgrammingLink.parent_node_id.in_(src_ids),
        )
        .all()
    )

    parent_of: dict[int, int] = {lnk.child_node_id: lnk.parent_node_id for lnk in src_links}
    sort_of: dict[int, int] = {lnk.child_node_id: lnk.sort_order for lnk in src_links}

    roots = [n for n in src_nodes if n.id not in parent_of]
    old_to_new: dict[int, int] = {}
    queue: deque[ProgrammingNode] = deque(roots)

    while queue:
        src_node = queue.popleft()
        src_parent_id = parent_of.get(src_node.id)
        new_parent_id = old_to_new.get(src_parent_id) if src_parent_id is not None else None

        new_node = ProgrammingNode(
            set_id=dst_set_id,
            kind=NodeKind.container,
            name=src_node.name,
            slug=src_node.slug,
            is_active=src_node.is_active,
            is_draft=False,
        )
        db.add(new_node)
        db.flush()
        old_to_new[src_node.id] = new_node.id

        if new_parent_id is not None:
            link = ProgrammingLink(
                parent_node_id=new_parent_id,
                child_type=ChildType.node,
                child_node_id=new_node.id,
                sort_order=sort_of.get(src_node.id, 0),
                status=LinkStatus.active,
                source=LinkSource.manual,
            )
            db.add(link)
            db.flush()

        children = [n for n in src_nodes if parent_of.get(n.id) == src_node.id]
        queue.extend(children)

    return len(old_to_new)
