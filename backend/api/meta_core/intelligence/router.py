"""
Intelligence API 라우터 — 검수 UI 전용 (GET + POST)

prefix: /api/meta-core (main.py 에서 마운트)
GET: 읽기 전용 조회
POST: accept / pick / merge / reject / bulk-accept (step9)
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from shared.database import get_db
from api.meta_core.gap import analyze_gap
from api.meta_core.aggregator import llm_merge_synopses
from api.meta_core.models.intelligence import FieldResolution, FieldSuggestion, MatchEdge
from api.programming.metadata.models.content import Content

from .schemas import (
    GapReportOut, FieldGapOut,
    ResolutionsByStatusOut, FieldResolutionOut,
    FieldResolutionDetailOut, FieldSuggestionOut,
    MatchEdgesOut, MatchEdgeOut,
    ResolutionQueueOut, ResolutionQueueItem,
    PickRequest, MergeRequest, BulkAcceptRequest, ActionResultOut,
)

router = APIRouter(tags=["Intelligence"])

_AUTO_DECISIONS = {"auto_agreement", "auto_quality"}


# ── GET /contents/{content_id}/gap ────────────────────────────────────────────

@router.get("/contents/{content_id}/gap", response_model=GapReportOut)
def get_gap(content_id: int, db: Session = Depends(get_db)):
    try:
        report = analyze_gap(content_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return GapReportOut(
        content_id=report.content_id,
        title=report.title,
        content_type=report.content_type,
        missing_fields=[
            FieldGapOut(
                field_name=g.field_name,
                reason=g.reason,
                recommended_sources=g.recommended_sources,
                priority=g.priority,
            )
            for g in report.missing_fields
        ],
        is_clean=report.is_clean,
        min_priority=report.min_priority,
    )


# ── GET /contents/{content_id}/resolutions ───────────────────────────────────

@router.get("/contents/{content_id}/resolutions", response_model=ResolutionsByStatusOut)
def get_resolutions(content_id: int, db: Session = Depends(get_db)):
    _require_content(content_id, db)
    rows = (
        db.query(FieldResolution)
        .filter(FieldResolution.content_id == content_id)
        .order_by(FieldResolution.field_name)
        .all()
    )
    auto = [r for r in rows if r.decision in _AUTO_DECISIONS]
    pending = [r for r in rows if r.decision not in _AUTO_DECISIONS]
    return ResolutionsByStatusOut(
        auto=[FieldResolutionOut.model_validate(r) for r in auto],
        pending=[FieldResolutionOut.model_validate(r) for r in pending],
    )


# ── GET /contents/{content_id}/resolutions/{field} ───────────────────────────

@router.get(
    "/contents/{content_id}/resolutions/{field_name}",
    response_model=FieldResolutionDetailOut,
)
def get_resolution_field(content_id: int, field_name: str, db: Session = Depends(get_db)):
    _require_content(content_id, db)
    resolution = (
        db.query(FieldResolution)
        .filter(
            FieldResolution.content_id == content_id,
            FieldResolution.field_name == field_name,
        )
        .first()
    )
    suggestions = (
        db.query(FieldSuggestion)
        .filter(
            FieldSuggestion.content_id == content_id,
            FieldSuggestion.field_name == field_name,
        )
        .order_by(FieldSuggestion.confidence.desc())
        .all()
    )
    return FieldResolutionDetailOut(
        resolution=FieldResolutionOut.model_validate(resolution) if resolution else None,
        suggestions=[FieldSuggestionOut.model_validate(s) for s in suggestions],
    )


# ── GET /contents/{content_id}/match-edges ───────────────────────────────────

@router.get("/contents/{content_id}/match-edges", response_model=MatchEdgesOut)
def get_match_edges(content_id: int, db: Session = Depends(get_db)):
    _require_content(content_id, db)
    rows = (
        db.query(MatchEdge)
        .filter(MatchEdge.content_id == content_id)
        .order_by(MatchEdge.score.desc())
        .all()
    )
    decided = [MatchEdgeOut.model_validate(r) for r in rows if r.decided]
    undecided = [MatchEdgeOut.model_validate(r) for r in rows if not r.decided]
    return MatchEdgesOut(decided=decided, undecided=undecided)


# ── GET /queue/resolutions ────────────────────────────────────────────────────

@router.get("/queue/resolutions", response_model=ResolutionQueueOut)
def get_resolution_queue(
    decision: str = Query("pending", description="pending | auto_agreement | auto_quality"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    offset = (page - 1) * page_size
    q = db.query(FieldResolution).filter(FieldResolution.decision == decision)
    total = q.count()
    rows = q.order_by(FieldResolution.created_at.desc()).offset(offset).limit(page_size).all()

    items: list[ResolutionQueueItem] = []
    for r in rows:
        content = db.query(Content).filter(Content.id == r.content_id).first()
        items.append(ResolutionQueueItem(
            content_id=r.content_id,
            content_title=content.title if content else "(삭제됨)",
            field_name=r.field_name,
            resolution=FieldResolutionOut.model_validate(r),
        ))
    return ResolutionQueueOut(items=items, total=total, page=page, page_size=page_size)


# ── POST /contents/{id}/resolutions/{field}/accept ───────────────────────────

@router.post("/contents/{content_id}/resolutions/{field_name}/accept",
             response_model=ActionResultOut)
def accept_resolution(content_id: int, field_name: str, db: Session = Depends(get_db)):
    """auto 결정 그대로 확정. 이미 applied면 no-op."""
    _require_content(content_id, db)
    res = _require_resolution(content_id, field_name, db)

    if res.applied_to_content:
        return ActionResultOut(field_name=field_name, decision=res.decision,
                               applied=True, message="already applied")

    decision = res.decision
    res.applied_to_content = True
    res.decided_at = datetime.now(timezone.utc)
    db.commit()
    return ActionResultOut(field_name=field_name, decision=decision, applied=True)


# ── POST /contents/{id}/resolutions/{field}/pick ─────────────────────────────

@router.post("/contents/{content_id}/resolutions/{field_name}/pick",
             response_model=ActionResultOut)
def pick_resolution(
    content_id: int, field_name: str,
    body: PickRequest,
    db: Session = Depends(get_db),
):
    """suggestion 1개 수동 선택 → manual_pick."""
    _require_content(content_id, db)
    sug = db.query(FieldSuggestion).filter(
        FieldSuggestion.id == body.suggestion_id,
        FieldSuggestion.content_id == content_id,
        FieldSuggestion.field_name == field_name,
    ).first()
    if not sug:
        raise HTTPException(status_code=404, detail="suggestion not found")

    now = datetime.now(timezone.utc)
    res = db.query(FieldResolution).filter(
        FieldResolution.content_id == content_id,
        FieldResolution.field_name == field_name,
    ).first()

    if res:
        res.decision = "manual_pick"
        res.chosen_value_json = sug.value_json
        res.chosen_suggestion_ids = [sug.id]
        res.applied_to_content = True
        res.decided_by = "system"
        res.decided_at = now
    else:
        res = FieldResolution(
            content_id=content_id, field_name=field_name,
            decision="manual_pick",
            chosen_value_json=sug.value_json,
            chosen_suggestion_ids=[sug.id],
            agreement_count=1,
            agreeing_sources_json=[sug.source_type],
            applied_to_content=True,
            decided_by="system",
            decided_at=now,
        )
        db.add(res)

    sug.status = "applied"
    db.commit()
    return ActionResultOut(field_name=field_name, decision="manual_pick", applied=True)


# ── POST /contents/{id}/resolutions/{field}/merge ────────────────────────────

@router.post("/contents/{content_id}/resolutions/{field_name}/merge",
             response_model=ActionResultOut)
def merge_resolution(
    content_id: int, field_name: str,
    body: MergeRequest,
    db: Session = Depends(get_db),
):
    """C형(synopsis 등) 전용 — union 또는 llm_merge."""
    _require_content(content_id, db)

    sugs = (
        db.query(FieldSuggestion)
        .filter(
            FieldSuggestion.id.in_(body.suggestion_ids),
            FieldSuggestion.content_id == content_id,
            FieldSuggestion.field_name == field_name,
        )
        .all()
    )
    if not sugs:
        raise HTTPException(status_code=404, detail="suggestions not found")

    if body.method == "llm_merge":
        values = [str(s.value_json) for s in sugs]
        merged_value = llm_merge_synopses(values, db)
    else:
        # union — 텍스트의 경우 첫 번째 값 선택 (UI가 순서 결정)
        merged_value = sugs[0].value_json

    now = datetime.now(timezone.utc)
    res = db.query(FieldResolution).filter(
        FieldResolution.content_id == content_id,
        FieldResolution.field_name == field_name,
    ).first()

    if res:
        res.decision = "manual_merge"
        res.chosen_value_json = merged_value
        res.chosen_suggestion_ids = [s.id for s in sugs]
        res.merge_method = body.method
        res.applied_to_content = True
        res.decided_by = "system"
        res.decided_at = now
    else:
        res = FieldResolution(
            content_id=content_id, field_name=field_name,
            decision="manual_merge",
            chosen_value_json=merged_value,
            chosen_suggestion_ids=[s.id for s in sugs],
            agreement_count=len(sugs),
            agreeing_sources_json=[s.source_type for s in sugs],
            merge_method=body.method,
            applied_to_content=True,
            decided_by="system",
            decided_at=now,
        )
        db.add(res)

    for s in sugs:
        s.status = "applied"
    db.commit()
    return ActionResultOut(field_name=field_name, decision="manual_merge", applied=True)


# ── POST /contents/{id}/resolutions/{field}/reject ───────────────────────────

@router.post("/contents/{content_id}/resolutions/{field_name}/reject",
             response_model=ActionResultOut)
def reject_resolution(content_id: int, field_name: str, db: Session = Depends(get_db)):
    """rejected, applied=false."""
    _require_content(content_id, db)
    now = datetime.now(timezone.utc)
    res = db.query(FieldResolution).filter(
        FieldResolution.content_id == content_id,
        FieldResolution.field_name == field_name,
    ).first()

    if res:
        res.decision = "rejected"
        res.applied_to_content = False
        res.decided_by = "system"
        res.decided_at = now
    else:
        res = FieldResolution(
            content_id=content_id, field_name=field_name,
            decision="rejected",
            chosen_suggestion_ids=[],
            agreement_count=0,
            agreeing_sources_json=[],
            applied_to_content=False,
            decided_by="system",
            decided_at=now,
        )
        db.add(res)

    db.commit()
    return ActionResultOut(field_name=field_name, decision="rejected", applied=False)


# ── POST /contents/{id}/resolutions/bulk-accept ───────────────────────────────

@router.post("/contents/{content_id}/resolutions/bulk-accept",
             response_model=list[ActionResultOut])
def bulk_accept(
    content_id: int,
    body: BulkAcceptRequest,
    db: Session = Depends(get_db),
):
    """여러 필드 일괄 accept (reject 포함 불가)."""
    _require_content(content_id, db)
    results = []
    now = datetime.now(timezone.utc)

    for field_name in body.fields:
        res = db.query(FieldResolution).filter(
            FieldResolution.content_id == content_id,
            FieldResolution.field_name == field_name,
        ).first()
        if not res:
            results.append(ActionResultOut(field_name=field_name, decision="not_found",
                                           applied=False, message="resolution not found"))
            continue
        if res.applied_to_content:
            results.append(ActionResultOut(field_name=field_name, decision=res.decision,
                                           applied=True, message="already applied"))
            continue
        res.applied_to_content = True
        res.decided_at = now
        results.append(ActionResultOut(field_name=field_name, decision=res.decision, applied=True))

    db.commit()
    return results


# ── 내부 헬퍼 ─────────────────────────────────────────────────────────────────

def _require_content(content_id: int, db: Session):
    if not db.query(Content).filter(Content.id == content_id).first():
        raise HTTPException(status_code=404, detail=f"Content {content_id} not found")


def _require_resolution(content_id: int, field_name: str, db: Session) -> FieldResolution:
    res = db.query(FieldResolution).filter(
        FieldResolution.content_id == content_id,
        FieldResolution.field_name == field_name,
    ).first()
    if not res:
        raise HTTPException(status_code=404, detail=f"Resolution for {field_name} not found")
    return res
