from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from shared.database import get_db
from api.programming.catalog import service
from api.programming.catalog import pricing_service, holdback_service, set_service
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
    CategorySetOut,
    CategorySetCommit,
    CategorySetUpdate,
    LoadSetRequest,
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
    from api.programming.scheduling.models import NodeKind, ProgrammingNode
    node = db.query(ProgrammingNode).filter(
        ProgrammingNode.id == category_id,
        ProgrammingNode.kind == NodeKind.container,
    ).first()
    if node is None:
        raise HTTPException(status_code=404, detail=f"Category {category_id} not found")
    return node


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
        created, skipped, overwritten = service.bulk_create_categories(
            db,
            nodes=[n.model_dump() for n in data.nodes],
            parent_id=data.parent_id,
            dup_policy=data.dup_policy,
        )
        db.commit()
    except ValueError as e:
        # reject 정책의 중복 충돌 → 409, 그 외(parent 없음 등) → 404
        if str(e).startswith("duplicate categories:"):
            raise HTTPException(status_code=409, detail=str(e))
        raise HTTPException(status_code=404, detail=str(e))
    tree = service.list_tree(db, root_id=data.parent_id, include_counts=True)
    return {
        "created": created,
        "skipped": skipped,
        "overwritten": overwritten,
        "tree": tree,
    }


@router.post("/categories", response_model=CategoryOut, status_code=201)
def create_category(data: CategoryCreate, db: Session = Depends(get_db)):
    try:
        cat = service.create_category(
            db, name=data.name, parent_id=data.parent_id, sort_order=data.sort_order
        )
        if data.slug is not None:
            from api.programming.scheduling.models import ProgrammingNode
            node = db.query(ProgrammingNode).filter(ProgrammingNode.id == cat.id).first()
            if node:
                node.slug = data.slug
                db.flush()
                cat.slug = data.slug
        db.commit()
        return cat
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/categories/{category_id}", response_model=CategoryOut)
def update_category(category_id: int, data: CategoryUpdate, db: Session = Depends(get_db)):
    _get_category_or_404(db, category_id)
    try:
        from api.programming.scheduling.models import ProgrammingLink, ProgrammingNode
        node = db.query(ProgrammingNode).filter(ProgrammingNode.id == category_id).first()
        if data.name is not None:
            node.name = data.name
        if data.is_active is not None:
            node.is_active = data.is_active
        if data.slug is not None:
            node.slug = data.slug
        if data.sort_order is not None:
            lnk = db.query(ProgrammingLink).filter(
                ProgrammingLink.child_node_id == category_id,
                ProgrammingLink.child_type == "node",
            ).first()
            if lnk:
                lnk.sort_order = data.sort_order
        db.flush()
        db.commit()
        lnk = service._incoming_link(db, category_id)
        return service._cat_view(
            node,
            depth=service._get_node_depth(db, category_id),
            sort_order=lnk.sort_order if lnk else 0,
            parent_id=lnk.parent_node_id if lnk else None,
        )
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
    links = service.map_content(
        db, content_id, data.category_ids, primary_id=data.primary_id
    )
    db.flush()
    result = [
        {
            "id": lnk.id,
            "content_id": lnk.child_content_id,
            "category_id": lnk.parent_node_id,
            "sort_order": lnk.sort_order,
            "is_primary": (lnk.child_content_id == data.primary_id),
            "created_at": lnk.created_at,
        }
        for lnk in links
    ]
    db.commit()
    return result


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
    from api.programming.scheduling.models import ChildType, ProgrammingLink
    links = (
        db.query(ProgrammingLink)
        .filter(
            ProgrammingLink.parent_node_id == category_id,
            ProgrammingLink.child_type == ChildType.content,
        )
        .all()
    )
    return [
        {
            "id": lnk.id,
            "content_id": lnk.child_content_id,
            "category_id": lnk.parent_node_id,
            "sort_order": lnk.sort_order,
            "is_primary": False,
            "created_at": lnk.created_at,
        }
        for lnk in links
    ]


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


# ── 카테고리 세트 ──────────────────────────────────────────────────────────────

@router.get("/sets", response_model=list[CategorySetOut])
def list_sets(db: Session = Depends(get_db)):
    return set_service.list_sets(db)


@router.post("/sets", response_model=CategorySetOut, status_code=201)
def commit_set(data: CategorySetCommit, db: Session = Depends(get_db)):
    result = set_service.commit_draft(db, name=data.name, description=data.description)
    db.commit()
    return result


@router.patch("/sets/{set_id}", response_model=CategorySetOut)
def update_set(set_id: int, data: CategorySetUpdate, db: Session = Depends(get_db)):
    try:
        result = set_service.update_set(db, set_id, name=data.name, description=data.description)
        db.commit()
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/sets/{set_id}", status_code=204)
def delete_set(set_id: int, db: Session = Depends(get_db)):
    try:
        set_service.delete_set(db, set_id)
        db.commit()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/sets/{set_id}/tree", response_model=list[CategoryTreeNode])
def get_set_tree(set_id: int, db: Session = Depends(get_db)):
    from api.programming.scheduling.models import ProgrammingNodeSet

    s = db.query(ProgrammingNodeSet).filter(ProgrammingNodeSet.id == set_id).first()
    if s is None:
        raise HTTPException(status_code=404, detail=f"set_id={set_id} not found")
    nodes = service.list_tree_by_set(db, set_id=set_id)
    return nodes


@router.get("/sets/{set_id}/load-preview")
def preview_load_set(set_id: int, db: Session = Depends(get_db)):
    try:
        return set_service.preview_load_set(db, set_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/sets/{set_id}/load")
def load_set(
    set_id: int,
    data: LoadSetRequest = LoadSetRequest(),
    db: Session = Depends(get_db),
):
    try:
        cleared, loaded = set_service.load_set(
            db, set_id, mode=data.mode, dup_policy=data.dup_policy
        )
        db.commit()
        return {"cleared": cleared, "loaded": loaded}
    except ValueError as e:
        if str(e).startswith("duplicate categories:"):
            raise HTTPException(status_code=409, detail=str(e))
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/sets/clear-draft")
def clear_draft(db: Session = Depends(get_db)):
    cleared = set_service.clear_draft(db)
    db.commit()
    return {"cleared": cleared}
