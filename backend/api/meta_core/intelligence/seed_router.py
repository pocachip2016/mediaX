"""
SEED 검수 라우터 — GET /seeds* + POST /seeds/{id}/lock|unlock|accept|reject|edit|bulk-promote

prefix: /api/meta-core (main → meta_core_router → intelligence_router → seed_router)
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from shared.database import get_db
from api.meta_core.models.seed import ContentSeed, SeedDiscoveryLog
from api.meta_core.discovery.promote import (
    promote_seed,
    SeedNotFound, SeedAlreadyProcessed, SeedLockedByOther, PossibleDuplicate,
)
from .seed_schemas import (
    SeedListItem, SeedListResponse, SeedDetail,
    SeedAcceptRequest, SeedRejectRequest, SeedEditRequest,
    SeedBulkPromoteRequest, SeedBulkPromoteResult,
    SeedStatsOut, SeedActionOut,
)

router = APIRouter(tags=["Seeds"])


# ── GET /seeds ────────────────────────────────────────────────────────────────

@router.get("/seeds", response_model=SeedListResponse)
def list_seeds(
    status: str | None = Query(None),
    source_type: str | None = Query(None),
    content_type: str | None = Query(None),
    year_from: int | None = Query(None),
    year_to: int | None = Query(None),
    locked: bool | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    order_by: str = Query("discovered_at"),
    db: Session = Depends(get_db),
):
    q = db.query(ContentSeed)
    if status:
        q = q.filter(ContentSeed.status == status)
    if source_type:
        q = q.filter(ContentSeed.source_type == source_type)
    if content_type:
        q = q.filter(ContentSeed.content_type == content_type)
    if year_from:
        q = q.filter(ContentSeed.production_year >= year_from)
    if year_to:
        q = q.filter(ContentSeed.production_year <= year_to)
    if locked is True:
        q = q.filter(ContentSeed.locked_by.isnot(None))
    elif locked is False:
        q = q.filter(ContentSeed.locked_by.is_(None))

    total = q.count()

    sort_col = ContentSeed.updated_at if order_by == "updated_at" else ContentSeed.id
    q = q.order_by(sort_col.desc())
    items = q.offset((page - 1) * page_size).limit(page_size).all()

    return SeedListResponse(
        items=[SeedListItem.model_validate(s) for s in items],
        total=total,
        page=page,
        page_size=page_size,
    )


# ── GET /seeds/stats ──────────────────────────────────────────────────────────

@router.get("/seeds/stats", response_model=SeedStatsOut)
def seed_stats(db: Session = Depends(get_db)):
    by_status = {
        row[0]: row[1]
        for row in db.query(ContentSeed.status, func.count()).group_by(ContentSeed.status).all()
    }
    by_source = {
        row[0]: row[1]
        for row in db.query(ContentSeed.source_type, func.count()).group_by(ContentSeed.source_type).all()
    }
    return SeedStatsOut(by_status=by_status, by_source=by_source, recent_7days=[])


# ── GET /seeds/discovery-log ──────────────────────────────────────────────────
# NOTE: 고정 경로는 반드시 GET /seeds/{seed_id} 보다 먼저 등록

@router.get("/seeds/discovery-log")
def discovery_log(
    source: str | None = Query(None),
    mode: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    q = db.query(SeedDiscoveryLog)
    if source:
        q = q.filter(SeedDiscoveryLog.source_type == source)
    if mode:
        q = q.filter(SeedDiscoveryLog.discovery_mode == mode)
    rows = q.order_by(SeedDiscoveryLog.id.desc()).limit(limit).all()
    return [
        {
            "id": r.id,
            "source_type": r.source_type,
            "discovery_mode": r.discovery_mode,
            "total_fetched": r.total_fetched,
            "new_seeds": r.new_seeds,
            "matched_existing": r.matched_existing,
            "duplicates": r.duplicates,
            "errors": r.errors,
            "duration_ms": r.duration_ms,
            "fetched_at": r.fetched_at.isoformat() if r.fetched_at else None,
        }
        for r in rows
    ]


# ── GET /seeds/discovery-stats ────────────────────────────────────────────────

@router.get("/seeds/discovery-stats")
def discovery_stats(
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
):
    from datetime import timedelta
    since = datetime.now(tz=timezone.utc) - timedelta(days=days)

    rows = db.query(SeedDiscoveryLog).filter(SeedDiscoveryLog.fetched_at >= since).all()

    total_fetched = sum(r.total_fetched or 0 for r in rows)
    total_new = sum(r.new_seeds or 0 for r in rows)
    total_matched = sum(r.matched_existing or 0 for r in rows)
    total_dup = sum(r.duplicates or 0 for r in rows)
    total_err = sum(r.errors or 0 for r in rows)

    by_source: dict[str, dict] = {}
    for r in rows:
        s = r.source_type
        if s not in by_source:
            by_source[s] = {"fetched": 0, "new_seeds": 0, "errors": 0}
        by_source[s]["fetched"] += r.total_fetched or 0
        by_source[s]["new_seeds"] += r.new_seeds or 0
        by_source[s]["errors"] += r.errors or 0

    return {
        "period_days": days,
        "total_fetched": total_fetched,
        "total_new_seeds": total_new,
        "total_matched_existing": total_matched,
        "total_duplicates": total_dup,
        "total_errors": total_err,
        "by_source": by_source,
    }


# ── GET /seeds/funnel ─────────────────────────────────────────────────────────

@router.get("/seeds/funnel")
def seed_funnel(db: Session = Depends(get_db)):
    statuses = ["discovered", "candidate", "under_review", "accepted", "rejected"]
    counts = {
        row[0]: row[1]
        for row in db.query(ContentSeed.status, func.count()).group_by(ContentSeed.status).all()
    }
    total = sum(counts.values()) or 1

    return {
        "total": total,
        "funnel": [
            {
                "status": s,
                "count": counts.get(s, 0),
                "pct": round(counts.get(s, 0) / total * 100, 1),
            }
            for s in statuses
        ],
        "acceptance_rate": round(counts.get("accepted", 0) / total * 100, 1),
    }


# ── GET /seeds/{id} ───────────────────────────────────────────────────────────

@router.get("/seeds/{seed_id}", response_model=SeedDetail)
def get_seed(seed_id: int, db: Session = Depends(get_db)):
    seed = _require_seed(seed_id, db)
    return SeedDetail.model_validate(seed)


# ── POST /seeds/{id}/lock ─────────────────────────────────────────────────────

@router.post("/seeds/{seed_id}/lock", response_model=SeedActionOut)
def lock_seed(seed_id: int, actor: str = Query(...), db: Session = Depends(get_db)):
    seed = _require_seed(seed_id, db)
    now = datetime.now(tz=timezone.utc)

    if seed.is_locked and seed.locked_by != actor:
        raise HTTPException(status_code=423,
                            detail={"error": "locked_by_other", "locked_by": seed.locked_by})

    seed.status = "under_review"
    seed.locked_by = actor
    seed.locked_at = now
    db.commit()
    return SeedActionOut(seed_id=seed_id, action="lock", success=True)


# ── POST /seeds/{id}/unlock ───────────────────────────────────────────────────

@router.post("/seeds/{seed_id}/unlock", response_model=SeedActionOut)
def unlock_seed(seed_id: int, actor: str = Query(...), db: Session = Depends(get_db)):
    seed = _require_seed(seed_id, db)

    if seed.locked_by and seed.locked_by != actor:
        raise HTTPException(status_code=403, detail="본인 lock 만 해제 가능")

    seed.locked_by = None
    seed.locked_at = None
    if seed.status == "under_review":
        seed.status = "candidate"
    db.commit()
    return SeedActionOut(seed_id=seed_id, action="unlock", success=True)


# ── POST /seeds/{id}/accept ───────────────────────────────────────────────────

@router.post("/seeds/{seed_id}/accept", response_model=SeedActionOut)
def accept_seed(seed_id: int, body: SeedAcceptRequest, db: Session = Depends(get_db)):
    try:
        content = promote_seed(db, seed_id, actor=body.actor, override_dup=body.override_dup)
        db.commit()
        return SeedActionOut(seed_id=seed_id, action="accept", success=True,
                             message=f"content_id={content.id}")
    except SeedNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except SeedAlreadyProcessed as e:
        raise HTTPException(status_code=400, detail=str(e))
    except SeedLockedByOther as e:
        raise HTTPException(status_code=423,
                            detail={"error": "locked_by_other", "locked_by": e.locked_by})
    except PossibleDuplicate as e:
        raise HTTPException(status_code=409,
                            detail={"error": "possible_duplicate",
                                    "content_id": e.content_id, "score": e.score})


# ── POST /seeds/{id}/reject ───────────────────────────────────────────────────

@router.post("/seeds/{seed_id}/reject", response_model=SeedActionOut)
def reject_seed(seed_id: int, body: SeedRejectRequest, db: Session = Depends(get_db)):
    seed = _require_seed(seed_id, db)
    if seed.status in {"accepted", "rejected"}:
        raise HTTPException(status_code=400, detail=f"SEED status={seed.status!r} — 변경 불가")

    seed.status = "rejected"
    payload = seed.raw_payload or {}
    payload["_reject_reason"] = body.reason
    payload["_rejected_by"] = body.actor
    seed.raw_payload = payload
    seed.locked_by = None
    seed.locked_at = None
    db.commit()
    return SeedActionOut(seed_id=seed_id, action="reject", success=True)


# ── POST /seeds/{id}/edit ─────────────────────────────────────────────────────

@router.post("/seeds/{seed_id}/edit", response_model=SeedActionOut)
def edit_seed(seed_id: int, body: SeedEditRequest, db: Session = Depends(get_db)):
    seed = _require_seed(seed_id, db)
    if seed.status in {"accepted", "rejected"}:
        raise HTTPException(status_code=400, detail=f"SEED status={seed.status!r} — 편집 불가")

    if body.title is not None:
        seed.title = body.title
    if body.production_year is not None:
        seed.production_year = body.production_year
    if body.synopsis is not None:
        seed.synopsis = body.synopsis
    if body.poster_url is not None:
        seed.poster_url = body.poster_url

    db.commit()
    return SeedActionOut(seed_id=seed_id, action="edit", success=True)


# ── POST /seeds/bulk-promote ──────────────────────────────────────────────────

@router.post("/seeds/bulk-promote", response_model=list[SeedBulkPromoteResult])
def bulk_promote(body: SeedBulkPromoteRequest, db: Session = Depends(get_db)):
    if len(body.seed_ids) > 50:
        raise HTTPException(status_code=400, detail="bulk-promote 최대 50건")

    results = []
    for seed_id in body.seed_ids:
        try:
            content = promote_seed(db, seed_id, actor=body.actor, override_dup=body.override_dup)
            db.commit()
            results.append(SeedBulkPromoteResult(seed_id=seed_id, success=True,
                                                  content_id=content.id))
        except Exception as exc:
            db.rollback()
            results.append(SeedBulkPromoteResult(seed_id=seed_id, success=False,
                                                  error=str(exc)))
    return results


# ── 내부 헬퍼 ─────────────────────────────────────────────────────────────────

def _require_seed(seed_id: int, db: Session) -> ContentSeed:
    seed = db.query(ContentSeed).filter_by(id=seed_id).first()
    if not seed:
        raise HTTPException(status_code=404, detail=f"ContentSeed id={seed_id} 없음")
    return seed
