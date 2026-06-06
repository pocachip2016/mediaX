from sqlalchemy.orm import Session
from sqlalchemy import func

from api.programming.catalog.models import Category, CategorySet


def list_sets(db: Session) -> list[dict]:
    sets = db.query(CategorySet).order_by(CategorySet.id).all()
    result = []
    for s in sets:
        count = db.query(func.count(Category.id)).filter(
            Category.set_id == s.id
        ).scalar() or 0
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
    s = CategorySet(name=name, description=description)
    db.add(s)
    db.flush()
    loaded = _copy_tree(db, src_set_id=None, dst_set_id=s.id)
    db.flush()
    count = db.query(func.count(Category.id)).filter(Category.set_id == s.id).scalar() or 0
    return {
        "id": s.id,
        "name": s.name,
        "description": s.description,
        "category_count": count,
        "created_at": s.created_at,
        "updated_at": s.updated_at,
        "_loaded": loaded,
    }


def load_set(db: Session, set_id: int) -> tuple[int, int]:
    s = db.query(CategorySet).filter(CategorySet.id == set_id).first()
    if s is None:
        raise ValueError(f"set_id={set_id} not found")
    cleared = clear_draft(db)
    db.flush()
    loaded = _copy_tree(db, src_set_id=set_id, dst_set_id=None)
    db.flush()
    return cleared, loaded


def clear_draft(db: Session) -> int:
    count = db.query(Category).filter(Category.set_id.is_(None)).delete(synchronize_session=False)
    db.flush()
    return count


def update_set(
    db: Session,
    set_id: int,
    name: str | None = None,
    description: str | None = None,
) -> dict:
    s = db.query(CategorySet).filter(CategorySet.id == set_id).first()
    if s is None:
        raise ValueError(f"set_id={set_id} not found")
    if name is not None:
        s.name = name
    if description is not None:
        s.description = description
    db.flush()
    count = db.query(func.count(Category.id)).filter(Category.set_id == set_id).scalar() or 0
    return {
        "id": s.id,
        "name": s.name,
        "description": s.description,
        "category_count": count,
        "created_at": s.created_at,
        "updated_at": s.updated_at,
    }


def delete_set(db: Session, set_id: int) -> None:
    s = db.query(CategorySet).filter(CategorySet.id == set_id).first()
    if s is None:
        raise ValueError(f"set_id={set_id} not found")
    db.delete(s)
    db.flush()


def _copy_tree(db: Session, src_set_id: int | None, dst_set_id: int | None) -> int:
    """src 세트의 카테고리 트리를 dst 세트로 복사. depth 오름차순 처리로 부모 보장."""
    nodes = (
        db.query(Category)
        .filter(Category.set_id.is_(src_set_id) if src_set_id is None else Category.set_id == src_set_id)
        .order_by(Category.depth, Category.sort_order)
        .all()
    )
    old_to_new: dict[int, int] = {}
    for node in nodes:
        new_parent_id = old_to_new.get(node.parent_id) if node.parent_id is not None else None
        new_node = Category(
            name=node.name,
            slug=node.slug,
            depth=node.depth,
            sort_order=node.sort_order,
            is_active=node.is_active,
            parent_id=new_parent_id,
            set_id=dst_set_id,
        )
        db.add(new_node)
        db.flush()
        old_to_new[node.id] = new_node.id
    return len(nodes)
