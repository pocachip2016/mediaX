from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from shared.database import get_db
from api.programming.catalog import service
from api.programming.catalog.schemas import (
    CategoryCreate,
    CategoryUpdate,
    CategoryMoveRequest,
    CategoryMergeRequest,
    ContentMapRequest,
    CategoryOut,
    CategoryTreeNode,
    ContentCategoryOut,
)

router = APIRouter()


def _get_category_or_404(db: Session, category_id: int):
    from api.programming.catalog.models import Category
    cat = db.query(Category).filter(Category.id == category_id).first()
    if cat is None:
        raise HTTPException(status_code=404, detail=f"Category {category_id} not found")
    return cat


# ── 카테고리 트리 ──────────────────────────────────────────────────────────────

@router.get("/categories/tree", response_model=list[CategoryTreeNode])
def get_category_tree(
    root_id: int | None = Query(None, description="지정하면 해당 노드부터의 서브트리"),
    counts: bool = Query(False, description="콘텐츠 수 포함 여부"),
    db: Session = Depends(get_db),
):
    nodes = service.list_tree(db, root_id=root_id, include_counts=counts)
    return nodes


@router.post("/categories", response_model=CategoryOut, status_code=201)
def create_category(data: CategoryCreate, db: Session = Depends(get_db)):
    try:
        cat = service.create_category(
            db, name=data.name, parent_id=data.parent_id, sort_order=data.sort_order
        )
        if data.slug is not None:
            cat.slug = data.slug
            db.flush()
        db.commit()
        db.refresh(cat)
        return cat
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/categories/{category_id}", response_model=CategoryOut)
def update_category(category_id: int, data: CategoryUpdate, db: Session = Depends(get_db)):
    _get_category_or_404(db, category_id)
    try:
        if data.name is not None:
            service.rename_category(db, category_id, data.name)
        if data.is_active is not None:
            service.set_active(db, category_id, data.is_active)
        from api.programming.catalog.models import Category
        cat = db.query(Category).filter(Category.id == category_id).first()
        if data.slug is not None:
            cat.slug = data.slug
        if data.sort_order is not None:
            cat.sort_order = data.sort_order
        db.commit()
        db.refresh(cat)
        return cat
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/categories/{category_id}/move", response_model=CategoryOut)
def move_category(
    category_id: int, data: CategoryMoveRequest, db: Session = Depends(get_db)
):
    _get_category_or_404(db, category_id)
    try:
        cat = service.move_category(
            db,
            category_id,
            new_parent_id=data.new_parent_id,
            new_sort_order=data.new_sort_order,
        )
        db.commit()
        db.refresh(cat)
        return cat
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/categories/{category_id}/merge", response_model=CategoryOut)
def merge_category(
    category_id: int, data: CategoryMergeRequest, db: Session = Depends(get_db)
):
    _get_category_or_404(db, category_id)
    try:
        cat = service.merge_category(db, category_id, data.target_id)
        db.commit()
        db.refresh(cat)
        return cat
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/categories/{category_id}", status_code=204)
def delete_category(
    category_id: int,
    cascade: bool = Query(False),
    db: Session = Depends(get_db),
):
    _get_category_or_404(db, category_id)
    try:
        service.delete_category(db, category_id, cascade=cascade)
        db.commit()
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


# ── 콘텐츠-카테고리 매핑 ──────────────────────────────────────────────────────

@router.post("/contents/{content_id}/categories", response_model=list[ContentCategoryOut])
def map_content_categories(
    content_id: int, data: ContentMapRequest, db: Session = Depends(get_db)
):
    rows = service.map_content(
        db, content_id, data.category_ids, primary_id=data.primary_id
    )
    db.commit()
    for r in rows:
        db.refresh(r)
    return rows


@router.delete("/contents/{content_id}/categories/{category_id}", status_code=204)
def unmap_content_category(
    content_id: int, category_id: int, db: Session = Depends(get_db)
):
    try:
        service.unmap_content(db, content_id, category_id)
        db.commit()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/categories/{category_id}/contents", response_model=list[ContentCategoryOut])
def get_category_contents(category_id: int, db: Session = Depends(get_db)):
    _get_category_or_404(db, category_id)
    from api.programming.catalog.models import ContentCategory
    rows = db.query(ContentCategory).filter(
        ContentCategory.category_id == category_id
    ).all()
    return rows
