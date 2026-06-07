from collections import deque

from sqlalchemy.orm import Session
from sqlalchemy import func

from api.programming.catalog.models import Category, ContentCategory


def _max_sibling_sort(db: Session, parent_id: int | None) -> int:
    result = db.query(func.max(Category.sort_order)).filter(
        Category.parent_id == parent_id
    ).scalar()
    return (result or 0) + 1


def create_category(
    db: Session,
    name: str,
    parent_id: int | None = None,
    sort_order: int | None = None,
) -> Category:
    depth = 0
    if parent_id is not None:
        parent = db.query(Category).filter(Category.id == parent_id).first()
        if parent is None:
            raise ValueError(f"parent_id={parent_id} not found")
        depth = parent.depth + 1

    if sort_order is None:
        sort_order = _max_sibling_sort(db, parent_id)

    cat = Category(name=name, parent_id=parent_id, depth=depth, sort_order=sort_order)
    db.add(cat)
    db.flush()
    return cat


def bulk_create_categories(
    db: Session,
    nodes: list[dict],
    parent_id: int | None = None,
) -> tuple[int, int]:
    """정규화된 nested 구조를 DFS로 생성. 동일 parent_id+name 존재 시 해당 노드는
    skip하되 children 탐색은 기존 노드 밑에서 계속. (created, skipped) 카운트 반환.

    nodes: [{"name": str, "children": [...]}, ...]
    """
    created = 0
    skipped = 0

    def _walk(items: list[dict], pid: int | None) -> None:
        nonlocal created, skipped
        for item in items:
            name = (item.get("name") or "").strip()
            if not name:
                continue
            existing = (
                db.query(Category)
                .filter(Category.parent_id == pid, Category.name == name)
                .first()
            )
            if existing is not None:
                skipped += 1
                node = existing
            else:
                node = create_category(db, name=name, parent_id=pid)
                created += 1
            children = item.get("children") or []
            if children:
                _walk(children, node.id)

    if parent_id is not None:
        if db.query(Category).filter(Category.id == parent_id).first() is None:
            raise ValueError(f"parent_id={parent_id} not found")

    _walk(nodes, parent_id)
    db.flush()
    return created, skipped


def rename_category(db: Session, category_id: int, name: str) -> Category:
    cat = db.query(Category).filter(Category.id == category_id).first()
    if cat is None:
        raise ValueError(f"category_id={category_id} not found")
    cat.name = name
    db.flush()
    return cat


def set_active(db: Session, category_id: int, is_active: bool) -> Category:
    cat = db.query(Category).filter(Category.id == category_id).first()
    if cat is None:
        raise ValueError(f"category_id={category_id} not found")
    cat.is_active = is_active
    db.flush()
    return cat


def get_subtree_ids(db: Session, category_id: int) -> set[int]:
    """BFS로 category_id를 포함한 모든 자손 id 반환."""
    visited: set[int] = set()
    queue = deque([category_id])
    while queue:
        current = queue.popleft()
        if current in visited:
            continue
        visited.add(current)
        children = db.query(Category.id).filter(Category.parent_id == current).all()
        queue.extend(c[0] for c in children)
    return visited


def _recalculate_depth(db: Session, category_id: int, new_depth: int) -> None:
    """category_id 노드와 모든 자손의 depth를 BFS로 재계산."""
    queue = deque([(category_id, new_depth)])
    while queue:
        cid, depth = queue.popleft()
        db.query(Category).filter(Category.id == cid).update({"depth": depth})
        children = db.query(Category.id).filter(Category.parent_id == cid).all()
        queue.extend((c[0], depth + 1) for c in children)


def move_category(
    db: Session,
    category_id: int,
    new_parent_id: int | None,
    new_sort_order: int | None = None,
) -> Category:
    cat = db.query(Category).filter(Category.id == category_id).first()
    if cat is None:
        raise ValueError(f"category_id={category_id} not found")

    # 사이클 가드: new_parent_id가 자기 자신 또는 자손이면 거부
    if new_parent_id is not None:
        subtree = get_subtree_ids(db, category_id)
        if new_parent_id in subtree:
            raise ValueError(
                f"move_category: new_parent_id={new_parent_id} is self or descendant of {category_id}"
            )

    if new_parent_id is not None:
        parent = db.query(Category).filter(Category.id == new_parent_id).first()
        if parent is None:
            raise ValueError(f"new_parent_id={new_parent_id} not found")
        new_depth = parent.depth + 1
    else:
        new_depth = 0

    cat.parent_id = new_parent_id
    if new_sort_order is None:
        new_sort_order = _max_sibling_sort(db, new_parent_id)
    cat.sort_order = new_sort_order
    db.flush()

    _recalculate_depth(db, category_id, new_depth)
    db.flush()
    db.refresh(cat)
    return cat


def merge_category(db: Session, source_id: int, target_id: int) -> Category:
    """source의 자식을 target으로 reparent, content_categories를 dedupe 이전, source 삭제."""
    source = db.query(Category).filter(Category.id == source_id).first()
    target = db.query(Category).filter(Category.id == target_id).first()
    if source is None:
        raise ValueError(f"source_id={source_id} not found")
    if target is None:
        raise ValueError(f"target_id={target_id} not found")
    if source_id == target_id:
        raise ValueError("source_id and target_id must differ")

    # 자식 reparent
    children = db.query(Category).filter(Category.parent_id == source_id).all()
    for child in children:
        child.parent_id = target_id
        child.depth = target.depth + 1
        _recalculate_depth(db, child.id, target.depth + 1)
    db.flush()

    # content_categories dedupe 이전
    source_mappings = db.query(ContentCategory).filter(
        ContentCategory.category_id == source_id
    ).all()
    existing_target = {
        row.content_id
        for row in db.query(ContentCategory).filter(
            ContentCategory.category_id == target_id
        ).all()
    }
    for mapping in source_mappings:
        if mapping.content_id not in existing_target:
            mapping.category_id = target_id
        else:
            db.delete(mapping)
    db.flush()

    db.delete(source)
    db.flush()
    db.refresh(target)
    return target


def delete_category(db: Session, category_id: int, cascade: bool = False) -> None:
    cat = db.query(Category).filter(Category.id == category_id).first()
    if cat is None:
        raise ValueError(f"category_id={category_id} not found")

    if not cascade:
        child_count = db.query(Category).filter(Category.parent_id == category_id).count()
        content_count = db.query(ContentCategory).filter(
            ContentCategory.category_id == category_id
        ).count()
        if child_count > 0 or content_count > 0:
            raise ValueError(
                f"category_id={category_id} has children or contents — use cascade=True"
            )

    db.delete(cat)
    db.flush()


def list_tree(
    db: Session,
    root_id: int | None = None,
    include_counts: bool = False,
) -> list[dict]:
    """중첩 트리 반환. root_id=None이면 최상위(parent_id=None) 노드들부터."""
    def _to_dict(cat: Category) -> dict:
        d: dict = {
            "id": cat.id,
            "name": cat.name,
            "slug": cat.slug,
            "depth": cat.depth,
            "sort_order": cat.sort_order,
            "is_active": cat.is_active,
            "parent_id": cat.parent_id,
            "children": [],
        }
        if include_counts:
            d["content_count"] = category_content_count(db, cat.id, recursive=False)
        return d

    def _build(parent_id: int | None) -> list[dict]:
        nodes = (
            db.query(Category)
            .filter(Category.parent_id == parent_id, Category.set_id.is_(None))
            .order_by(Category.sort_order)
            .all()
        )
        result = []
        for node in nodes:
            d = _to_dict(node)
            d["children"] = _build(node.id)
            result.append(d)
        return result

    return _build(root_id)


def list_tree_by_set(db: Session, set_id: int) -> list[dict]:
    """특정 세트 소속 카테고리를 중첩 트리로 반환."""
    id_map: dict[int, dict] = {}
    all_cats = (
        db.query(Category)
        .filter(Category.set_id == set_id)
        .order_by(Category.sort_order)
        .all()
    )
    for cat in all_cats:
        id_map[cat.id] = {
            "id": cat.id,
            "name": cat.name,
            "slug": cat.slug,
            "depth": cat.depth,
            "sort_order": cat.sort_order,
            "is_active": cat.is_active,
            "parent_id": cat.parent_id,
            "children": [],
        }
    roots = []
    for node in id_map.values():
        pid = node["parent_id"]
        if pid is None or pid not in id_map:
            roots.append(node)
        else:
            id_map[pid]["children"].append(node)
    return roots


def map_content(
    db: Session,
    content_id: int,
    category_ids: list[int],
    primary_id: int | None = None,
) -> list[ContentCategory]:
    """콘텐츠↔카테고리 매핑 (멱등). 이미 있는 (content_id, category_id) 쌍은 skip."""
    existing = {
        row.category_id
        for row in db.query(ContentCategory).filter(
            ContentCategory.content_id == content_id
        ).all()
    }
    result = []
    for cat_id in category_ids:
        if cat_id in existing:
            row = db.query(ContentCategory).filter(
                ContentCategory.content_id == content_id,
                ContentCategory.category_id == cat_id,
            ).first()
        else:
            row = ContentCategory(
                content_id=content_id,
                category_id=cat_id,
                is_primary=(cat_id == primary_id),
            )
            db.add(row)
        result.append(row)
    db.flush()
    return result


def unmap_content(db: Session, content_id: int, category_id: int) -> None:
    row = db.query(ContentCategory).filter(
        ContentCategory.content_id == content_id,
        ContentCategory.category_id == category_id,
    ).first()
    if row is None:
        raise ValueError(f"mapping content_id={content_id} category_id={category_id} not found")
    db.delete(row)
    db.flush()


def category_content_count(db: Session, category_id: int, recursive: bool = False) -> int:
    if not recursive:
        return db.query(ContentCategory).filter(
            ContentCategory.category_id == category_id
        ).count()

    ids = get_subtree_ids(db, category_id)
    return db.query(ContentCategory).filter(
        ContentCategory.category_id.in_(ids)
    ).count()
