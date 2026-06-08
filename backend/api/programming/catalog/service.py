from collections import deque
from types import SimpleNamespace

from sqlalchemy.orm import Session
from sqlalchemy import func

from api.programming.scheduling.models import (
    ChildType,
    LinkSource,
    LinkStatus,
    NodeKind,
    ProgrammingLink,
    ProgrammingNode,
)
from api.programming.scheduling.node_service import (
    list_node_tree as _list_node_tree,
    list_node_tree_by_set as _list_node_tree_by_set,
)


# ── 내부 헬퍼 ─────────────────────────────────────────────────────────────────

def _cat_view(
    node: ProgrammingNode,
    *,
    depth: int,
    sort_order: int,
    parent_id: int | None,
) -> SimpleNamespace:
    """ProgrammingNode + 파생 필드를 CategoryOut 형태로 래핑."""
    return SimpleNamespace(
        id=node.id,
        name=node.name,
        slug=node.slug,
        depth=depth,
        sort_order=sort_order,
        is_active=node.is_active,
        parent_id=parent_id,
        created_at=node.created_at,
        updated_at=node.updated_at,
    )


def _get_node_depth(db: Session, node_id: int) -> int:
    """링크 체인을 역방향으로 올라가며 depth 계산."""
    depth = 0
    current = node_id
    while True:
        link = (
            db.query(ProgrammingLink)
            .filter(
                ProgrammingLink.child_node_id == current,
                ProgrammingLink.child_type == ChildType.node,
            )
            .first()
        )
        if link is None:
            break
        depth += 1
        current = link.parent_node_id
    return depth


def _max_sibling_sort(db: Session, parent_id: int | None) -> int:
    """부모 노드 아래 node-type 링크의 최대 sort_order + 1."""
    if parent_id is None:
        return 0
    result = (
        db.query(func.max(ProgrammingLink.sort_order))
        .filter(
            ProgrammingLink.parent_node_id == parent_id,
            ProgrammingLink.child_type == ChildType.node,
        )
        .scalar()
    )
    return (result or 0) + 1


def _get_node_or_raise(db: Session, node_id: int) -> ProgrammingNode:
    node = (
        db.query(ProgrammingNode)
        .filter(
            ProgrammingNode.id == node_id,
            ProgrammingNode.kind == NodeKind.container,
        )
        .first()
    )
    if node is None:
        raise ValueError(f"category_id={node_id} not found")
    return node


def _incoming_link(db: Session, node_id: int) -> ProgrammingLink | None:
    return (
        db.query(ProgrammingLink)
        .filter(
            ProgrammingLink.child_node_id == node_id,
            ProgrammingLink.child_type == ChildType.node,
        )
        .first()
    )


# ── 카테고리 CRUD ──────────────────────────────────────────────────────────────

def create_category(
    db: Session,
    name: str,
    parent_id: int | None = None,
    sort_order: int | None = None,
) -> SimpleNamespace:
    if parent_id is not None:
        _get_node_or_raise(db, parent_id)

    node = ProgrammingNode(
        kind=NodeKind.container,
        name=name,
        is_active=True,
        is_draft=False,
    )
    db.add(node)
    db.flush()

    if parent_id is not None:
        if sort_order is None:
            sort_order = _max_sibling_sort(db, parent_id)
        link = ProgrammingLink(
            parent_node_id=parent_id,
            child_type=ChildType.node,
            child_node_id=node.id,
            sort_order=sort_order,
            status=LinkStatus.active,
            source=LinkSource.manual,
        )
        db.add(link)
        db.flush()
        depth = _get_node_depth(db, node.id)
    else:
        sort_order = sort_order or 0
        depth = 0

    return _cat_view(node, depth=depth, sort_order=sort_order, parent_id=parent_id)


def _find_conflicts(
    db: Session,
    nodes: list[dict],
    parent_id: int | None,
    path_prefix: list[str],
) -> list[str]:
    """입력 트리를 DFS하며 동일 (parent, name) 경로 충돌을 수집."""
    conflicts: list[str] = []
    for item in nodes:
        name = (item.get("name") or "").strip()
        if not name:
            continue
        path = path_prefix + [name]
        if parent_id is not None:
            existing = (
                db.query(ProgrammingNode)
                .join(
                    ProgrammingLink,
                    (ProgrammingLink.child_node_id == ProgrammingNode.id)
                    & (ProgrammingLink.parent_node_id == parent_id)
                    & (ProgrammingLink.child_type == ChildType.node),
                )
                .filter(
                    ProgrammingNode.name == name,
                    ProgrammingNode.set_id.is_(None),
                )
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
            conflicts.append("/".join(path))
            conflicts.extend(
                _find_conflicts(db, item.get("children") or [], existing.id, path)
            )
    return conflicts


def bulk_create_categories(
    db: Session,
    nodes: list[dict],
    parent_id: int | None = None,
    dup_policy: str = "merge",
) -> tuple[int, int, int]:
    """정규화된 nested 구조를 DFS로 생성. dup_policy로 동일 (parent, name) 충돌 처리.

    - merge: 기존 노드 유지, children 탐색은 기존 노드 밑에서 계속 (skip 카운트)
    - overwrite: 기존 노드 유지하되 입력에 children이 있으면 기존 직속 자식
      서브트리를 cascade 삭제 후 입력 구조로 재생성 (overwritten 카운트)
    - reject: 충돌이 하나라도 있으면 ValueError (아무것도 생성 안 함)
    """
    if parent_id is not None:
        _get_node_or_raise(db, parent_id)

    if dup_policy == "reject":
        conflicts = _find_conflicts(db, nodes, parent_id, [])
        if conflicts:
            raise ValueError("duplicate categories: " + ", ".join(conflicts))

    created = 0
    skipped = 0
    overwritten = 0

    def _find_existing(name: str, pid: int | None) -> ProgrammingNode | None:
        if pid is not None:
            return (
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
        child_ids_q = db.query(ProgrammingLink.child_node_id).filter(
            ProgrammingLink.child_type == ChildType.node,
            ProgrammingLink.child_node_id.isnot(None),
        )
        return (
            db.query(ProgrammingNode)
            .filter(
                ProgrammingNode.name == name,
                ProgrammingNode.kind == NodeKind.container,
                ProgrammingNode.set_id.is_(None),
                ~ProgrammingNode.id.in_(child_ids_q),
            )
            .first()
        )

    def _walk(items: list[dict], pid: int | None) -> None:
        nonlocal created, skipped, overwritten
        for item in items:
            name = (item.get("name") or "").strip()
            if not name:
                continue
            existing = _find_existing(name, pid)
            children = item.get("children") or []
            if existing is not None:
                node_id = existing.id
                if dup_policy == "overwrite" and children:
                    old_children = (
                        db.query(ProgrammingLink)
                        .filter(
                            ProgrammingLink.parent_node_id == existing.id,
                            ProgrammingLink.child_type == ChildType.node,
                        )
                        .all()
                    )
                    for lnk in old_children:
                        if lnk.child_node_id:
                            delete_category(db, lnk.child_node_id, cascade=True)
                    overwritten += 1
                else:
                    skipped += 1
            else:
                view = create_category(db, name=name, parent_id=pid)
                node_id = view.id
                created += 1
            if children:
                _walk(children, node_id)

    _walk(nodes, parent_id)
    db.flush()
    return created, skipped, overwritten


def rename_category(db: Session, category_id: int, name: str) -> SimpleNamespace:
    node = _get_node_or_raise(db, category_id)
    node.name = name
    db.flush()
    lnk = _incoming_link(db, category_id)
    return _cat_view(
        node,
        depth=_get_node_depth(db, category_id),
        sort_order=lnk.sort_order if lnk else 0,
        parent_id=lnk.parent_node_id if lnk else None,
    )


def set_active(db: Session, category_id: int, is_active: bool) -> SimpleNamespace:
    node = _get_node_or_raise(db, category_id)
    node.is_active = is_active
    db.flush()
    lnk = _incoming_link(db, category_id)
    return _cat_view(
        node,
        depth=_get_node_depth(db, category_id),
        sort_order=lnk.sort_order if lnk else 0,
        parent_id=lnk.parent_node_id if lnk else None,
    )


def get_subtree_ids(db: Session, node_id: int) -> set[int]:
    """BFS로 node_id를 포함한 모든 자손 id 반환 (programming_links 기반)."""
    visited: set[int] = set()
    queue = deque([node_id])
    while queue:
        current = queue.popleft()
        if current in visited:
            continue
        visited.add(current)
        children = (
            db.query(ProgrammingLink.child_node_id)
            .filter(
                ProgrammingLink.parent_node_id == current,
                ProgrammingLink.child_type == ChildType.node,
                ProgrammingLink.child_node_id.isnot(None),
            )
            .all()
        )
        queue.extend(c[0] for c in children)
    return visited


def move_category(
    db: Session,
    category_id: int,
    new_parent_id: int | None,
    new_sort_order: int | None = None,
) -> SimpleNamespace:
    node = _get_node_or_raise(db, category_id)

    if new_parent_id is not None:
        subtree = get_subtree_ids(db, category_id)
        if new_parent_id in subtree:
            raise ValueError(
                f"move_category: new_parent_id={new_parent_id} is self or descendant of {category_id}"
            )
        _get_node_or_raise(db, new_parent_id)

    # 기존 incoming link 제거
    old_link = _incoming_link(db, category_id)
    if old_link is not None:
        db.delete(old_link)
        db.flush()

    sort_order = new_sort_order
    if new_parent_id is not None:
        if sort_order is None:
            sort_order = _max_sibling_sort(db, new_parent_id)
        link = ProgrammingLink(
            parent_node_id=new_parent_id,
            child_type=ChildType.node,
            child_node_id=category_id,
            sort_order=sort_order,
            status=LinkStatus.active,
            source=LinkSource.manual,
        )
        db.add(link)
        db.flush()
    else:
        sort_order = sort_order or 0

    db.refresh(node)
    return _cat_view(
        node,
        depth=_get_node_depth(db, category_id),
        sort_order=sort_order,
        parent_id=new_parent_id,
    )


def merge_category(db: Session, source_id: int, target_id: int) -> SimpleNamespace:
    """source의 자식 노드와 content 링크를 target으로 이전 후 source 삭제."""
    source = _get_node_or_raise(db, source_id)
    target = _get_node_or_raise(db, target_id)
    if source_id == target_id:
        raise ValueError("source_id and target_id must differ")

    target_depth = _get_node_depth(db, target_id)

    # 자식 node-link를 source→target으로 교체
    child_links = (
        db.query(ProgrammingLink)
        .filter(
            ProgrammingLink.parent_node_id == source_id,
            ProgrammingLink.child_type == ChildType.node,
        )
        .all()
    )
    for lnk in child_links:
        lnk.parent_node_id = target_id
    db.flush()

    # content-link dedupe 이전 (programming_links)
    existing_target_contents = {
        row.child_content_id
        for row in db.query(ProgrammingLink)
        .filter(
            ProgrammingLink.parent_node_id == target_id,
            ProgrammingLink.child_type == ChildType.content,
        )
        .all()
    }
    content_links = (
        db.query(ProgrammingLink)
        .filter(
            ProgrammingLink.parent_node_id == source_id,
            ProgrammingLink.child_type == ChildType.content,
        )
        .all()
    )
    for lnk in content_links:
        if lnk.child_content_id not in existing_target_contents:
            lnk.parent_node_id = target_id
        else:
            db.delete(lnk)
    db.flush()

    # source incoming link 삭제 후 source 노드 삭제
    src_link = _incoming_link(db, source_id)
    if src_link is not None:
        db.delete(src_link)
        db.flush()
    db.delete(source)
    db.flush()

    db.refresh(target)
    tgt_link = _incoming_link(db, target_id)
    return _cat_view(
        target,
        depth=target_depth,
        sort_order=tgt_link.sort_order if tgt_link else 0,
        parent_id=tgt_link.parent_node_id if tgt_link else None,
    )


def delete_category(db: Session, category_id: int, cascade: bool = False) -> None:
    node = _get_node_or_raise(db, category_id)

    if not cascade:
        child_count = (
            db.query(ProgrammingLink)
            .filter(
                ProgrammingLink.parent_node_id == category_id,
                ProgrammingLink.child_type == ChildType.node,
            )
            .count()
        )
        content_count = (
            db.query(ProgrammingLink)
            .filter(
                ProgrammingLink.parent_node_id == category_id,
                ProgrammingLink.child_type == ChildType.content,
            )
            .count()
        )
        if child_count > 0 or content_count > 0:
            raise ValueError(
                f"category_id={category_id} has children or contents — use cascade=True"
            )
        db.delete(node)
        db.flush()
    else:
        # BFS로 자손 모두 삭제 (DB CASCADE가 링크 정리)
        all_ids = get_subtree_ids(db, category_id)
        for nid in all_ids:
            n = db.query(ProgrammingNode).filter(ProgrammingNode.id == nid).first()
            if n is not None:
                db.delete(n)
        db.flush()


# ── 트리 조회 (Step 1에서 전환 완료) ──────────────────────────────────────────

def list_tree(
    db: Session,
    root_id: int | None = None,
    include_counts: bool = False,
) -> list[dict]:
    """중첩 트리 반환 — programming_nodes(kind=container) 기반. API 계약 유지."""
    return _list_node_tree(db, root_id=root_id, include_counts=include_counts)


def list_tree_by_set(db: Session, set_id: int) -> list[dict]:
    """특정 NodeSet 소속 카테고리를 중첩 트리로 반환 — programming_nodes 기반."""
    return _list_node_tree_by_set(db, set_id=set_id)


# ── 콘텐츠 매핑 (programming_links child_type=content 기반) ───────────────────

def map_content(
    db: Session,
    content_id: int,
    category_ids: list[int],
    primary_id: int | None = None,
) -> list[ProgrammingLink]:
    """콘텐츠↔카테고리 매핑 (멱등). programming_links(child_type=content) 사용."""
    result = []
    for cat_id in category_ids:
        existing = (
            db.query(ProgrammingLink)
            .filter(
                ProgrammingLink.parent_node_id == cat_id,
                ProgrammingLink.child_type == ChildType.content,
                ProgrammingLink.child_content_id == content_id,
            )
            .first()
        )
        if existing is None:
            lnk = ProgrammingLink(
                parent_node_id=cat_id,
                child_type=ChildType.content,
                child_content_id=content_id,
                sort_order=0,
                status=LinkStatus.active,
                source=LinkSource.manual,
            )
            db.add(lnk)
            db.flush()
            result.append(lnk)
        else:
            result.append(existing)
    return result


def unmap_content(db: Session, content_id: int, category_id: int) -> None:
    lnk = (
        db.query(ProgrammingLink)
        .filter(
            ProgrammingLink.parent_node_id == category_id,
            ProgrammingLink.child_type == ChildType.content,
            ProgrammingLink.child_content_id == content_id,
        )
        .first()
    )
    if lnk is None:
        raise ValueError(f"mapping content_id={content_id} category_id={category_id} not found")
    db.delete(lnk)
    db.flush()


def category_content_count(db: Session, category_id: int, recursive: bool = False) -> int:
    if not recursive:
        return (
            db.query(ProgrammingLink)
            .filter(
                ProgrammingLink.parent_node_id == category_id,
                ProgrammingLink.child_type == ChildType.content,
            )
            .count()
        )
    ids = get_subtree_ids(db, category_id)
    return (
        db.query(ProgrammingLink)
        .filter(
            ProgrammingLink.parent_node_id.in_(ids),
            ProgrammingLink.child_type == ChildType.content,
        )
        .count()
    )
