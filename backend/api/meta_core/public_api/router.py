from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from shared.database import SessionLocal
from api.meta_core.public_api.schemas import ContentSummary, ContentSummaryPage, DamEventRequest

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/health")
def meta_core_health():
    return {"status": "ok", "module": "meta_core_public_api"}


@router.get("/contents/since", response_model=ContentSummaryPage)
def contents_since(
    ts: int = Query(default=0, description="Unix timestamp (milliseconds). 0 = 전체 조회"),
    limit: int = Query(default=500, le=1000),
    db: Session = Depends(get_db),
):
    from api.programming.metadata.models.content import Content

    since_dt = datetime.utcfromtimestamp(ts / 1000.0)
    effective_ts = func.coalesce(Content.updated_at, Content.created_at)

    rows = (
        db.query(Content)
        .filter(effective_ts >= since_dt)
        .order_by(effective_ts.asc())
        .limit(limit)
        .all()
    )

    items = [
        ContentSummary(
            content_id=c.id,
            title=c.title,
            original_title=c.original_title,
            content_type=c.content_type.value,
            production_year=c.production_year,
            status=c.status.value,
            updated_at=c.updated_at or c.created_at or datetime.utcnow(),
        )
        for c in rows
    ]

    if rows:
        last = rows[-1]
        last_dt = last.updated_at or last.created_at
        next_ts = int(last_dt.replace(tzinfo=timezone.utc).timestamp() * 1000) + 1 if last_dt else None
    else:
        next_ts = int(datetime.utcnow().replace(tzinfo=timezone.utc).timestamp() * 1000)

    total = db.query(func.count(Content.id)).filter(effective_ts >= since_dt).scalar() or 0

    return ContentSummaryPage(items=items, next_ts=next_ts, total=total)


@router.get("/contents/{content_id}", response_model=ContentSummary)
def get_content(content_id: int, db: Session = Depends(get_db)):
    from api.programming.metadata.models.content import Content

    content = db.get(Content, content_id)
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    return ContentSummary(
        content_id=content.id,
        title=content.title,
        original_title=content.original_title,
        content_type=content.content_type.value,
        production_year=content.production_year,
        status=content.status.value,
        updated_at=content.updated_at or content.created_at or datetime.utcnow(),
    )


@router.post("/dam-events", status_code=201)
def receive_dam_event(body: DamEventRequest, db: Session = Depends(get_db)):
    from api.meta_core.public_api.models import DamEvent
    event = DamEvent(
        event_type=body.event_type,
        content_id=body.content_id,
        asset_id=body.asset_id,
        confidence=body.confidence,
        match_method=body.match_method,
        confirmed=body.confirmed,
        payload_json=body.payload,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return {"accepted": True, "id": event.id}
