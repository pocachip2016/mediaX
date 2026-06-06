from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from shared.database import get_db
from api.programming.catalog import service
from api.programming.catalog import pricing_service, holdback_service
from api.programming.catalog.schemas import (
    CategoryCreate,
    CategoryUpdate,
    CategoryMoveRequest,
    CategoryMergeRequest,
    BulkCategoryCreate,
    BulkCategoryResult,
    ContentMapRequest,
    CategoryOut,
    CategoryTreeNode,
    ContentCategoryOut,
    PricingSet,
    PricingOut,
    BulkPricingRequest,
    PriceChangeLogOut,
    HoldbackPolicyCreate,
    HoldbackPolicyOut,
    HoldbackApplyRequest,
    HoldbackScheduleOut,
    ActivateWindowRequest,
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


@router.post("/categories/bulk", response_model=BulkCategoryResult, status_code=201)
def bulk_create_categories(data: BulkCategoryCreate, db: Session = Depends(get_db)):
    try:
        created, skipped = service.bulk_create_categories(
            db,
            nodes=[n.model_dump() for n in data.nodes],
            parent_id=data.parent_id,
        )
        db.commit()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    tree = service.list_tree(db, root_id=data.parent_id, include_counts=True)
    return {"created": created, "skipped": skipped, "tree": tree}


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


# ── 가격 정책 ─────────────────────────────────────────────────────────────────

@router.get("/contents/{content_id}/pricing", response_model=dict)
def get_price_matrix(content_id: int, db: Session = Depends(get_db)):
    return pricing_service.get_price_matrix(db, content_id)


@router.put("/contents/{content_id}/pricing", response_model=PricingOut)
def set_price(content_id: int, data: PricingSet, db: Session = Depends(get_db)):
    try:
        row = pricing_service.set_price(
            db,
            content_id=content_id,
            quality=data.quality,
            purchase_type=data.purchase_type,
            price=data.price,
            changed_by=data.changed_by,
            reason=data.reason,
        )
        db.commit()
        db.refresh(row)
        return row
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/pricing/bulk", response_model=list[PricingOut])
def bulk_update_pricing(data: BulkPricingRequest, db: Session = Depends(get_db)):
    rows = pricing_service.bulk_update(
        db,
        items=[i.model_dump() for i in data.items],
        changed_by=data.changed_by,
        reason=data.reason,
    )
    db.commit()
    for r in rows:
        db.refresh(r)
    return rows


@router.get("/contents/{content_id}/price-changes", response_model=list[PriceChangeLogOut])
def list_price_changes(
    content_id: int,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return pricing_service.list_price_changes(db, content_id, limit=limit)


@router.delete("/contents/{content_id}/pricing", status_code=204)
def delete_price(
    content_id: int,
    quality: str = Query(...),
    purchase_type: str = Query(...),
    db: Session = Depends(get_db),
):
    try:
        pricing_service.delete_price(db, content_id, quality, purchase_type)
        db.commit()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── 홀드백 ────────────────────────────────────────────────────────────────────

@router.get("/holdback/policies", response_model=list[HoldbackPolicyOut])
def list_holdback_policies(
    cp_name: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return holdback_service.list_policies(db, cp_name=cp_name)


@router.put("/holdback/policies", response_model=HoldbackPolicyOut)
def upsert_holdback_policy(data: HoldbackPolicyCreate, db: Session = Depends(get_db)):
    policy = holdback_service.upsert_policy(
        db,
        cp_name=data.cp_name,
        window_no=data.window_no,
        name=data.name,
        offset_days_start=data.offset_days_start,
        offset_days_end=data.offset_days_end,
        price_rule=data.price_rule,
        is_active=data.is_active,
    )
    db.commit()
    db.refresh(policy)
    return policy


@router.delete("/holdback/policies/{policy_id}", status_code=204)
def delete_holdback_policy(policy_id: int, db: Session = Depends(get_db)):
    try:
        holdback_service.delete_policy(db, policy_id)
        db.commit()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/contents/{content_id}/holdback/apply", response_model=list[HoldbackScheduleOut])
def apply_holdback(
    content_id: int,
    data: HoldbackApplyRequest,
    db: Session = Depends(get_db),
):
    try:
        schedules = holdback_service.apply_policy_to_content(db, content_id, base_date=data.base_date)
        db.commit()
        for s in schedules:
            db.refresh(s)
        return schedules
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/contents/{content_id}/holdback", response_model=list[HoldbackScheduleOut])
def list_holdback_schedules(content_id: int, db: Session = Depends(get_db)):
    return holdback_service.list_schedules(db, content_id)


@router.post("/contents/{content_id}/holdback/{window_no}/activate", response_model=HoldbackScheduleOut)
def activate_holdback_window(
    content_id: int,
    window_no: int,
    data: ActivateWindowRequest,
    db: Session = Depends(get_db),
):
    try:
        s = holdback_service.activate_window(
            db,
            content_id=content_id,
            window_no=window_no,
            quality=data.quality,
            purchase_type=data.purchase_type,
            price=data.price,
            changed_by=data.changed_by,
        )
        db.commit()
        db.refresh(s)
        return s
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/holdback/calendar", response_model=list[HoldbackScheduleOut])
def holdback_calendar(
    start: date = Query(..., description="시작일 (YYYY-MM-DD)"),
    end: date = Query(..., description="종료일 (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
):
    return holdback_service.calendar(db, start_date=start, end_date=end)
