import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from shared.database import get_db
from .schemas import (
    DistributionChannelOut, ServiceCategoryOut, ServiceCategoryWithItemsOut,
    ServiceCategoryCreate, ServiceCategoryUpdate,
    ServiceCategoryItemOut, ServiceCategoryItemCreate,
    ReorderRequest, DeviceVariantOut, SyncStatusOut, ServiceOut,
    MatchContentsRequest, MatchContentsResponse, ContentMatchCandidateOut,
    ExternalReferencesResponse, OttSectionCardOut, OttItemOut,
    ProposeCopyRequest, ProposeCopyResponse, CopyCandidateOut,
)
from . import service
from .curation_matcher import match_contents

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/services", response_model=list[ServiceOut])
def get_services(
    kind: str | None = Query(None, description="ott | iptv"),
    db: Session = Depends(get_db),
):
    return service.get_services(db, kind=kind)


@router.get("/contents/{content_id}/channels", response_model=list[DistributionChannelOut])
def get_content_channels(content_id: int, db: Session = Depends(get_db)):
    return service.get_channels_for_content(db, content_id)


@router.get("/categories", response_model=list[ServiceCategoryOut])
def get_categories(
    platform: str | None = Query(None),
    is_active: bool | None = Query(None),
    db: Session = Depends(get_db),
):
    return service.get_categories(db, platform=platform, is_active=is_active)


@router.post("/categories", response_model=ServiceCategoryOut, status_code=201)
def create_category(data: ServiceCategoryCreate, db: Session = Depends(get_db)):
    return service.create_category(db, data)


@router.get("/categories/{category_id}", response_model=ServiceCategoryWithItemsOut)
def get_category(category_id: int, db: Session = Depends(get_db)):
    return service.get_category_with_items(db, category_id)


@router.put("/categories/{category_id}", response_model=ServiceCategoryOut)
def update_category(category_id: int, data: ServiceCategoryUpdate, db: Session = Depends(get_db)):
    return service.update_category(db, category_id, data)


@router.delete("/categories/{category_id}")
def delete_category(category_id: int, db: Session = Depends(get_db)):
    return service.delete_category(db, category_id)


@router.post("/categories/{category_id}/items", response_model=ServiceCategoryItemOut, status_code=201)
def add_item(category_id: int, data: ServiceCategoryItemCreate, db: Session = Depends(get_db)):
    return service.add_item(db, category_id, data)


@router.delete("/categories/{category_id}/items/{item_id}")
def remove_item(category_id: int, item_id: int, db: Session = Depends(get_db)):
    return service.remove_item(db, category_id, item_id)


@router.post("/categories/{category_id}/items/reorder")
def reorder_items(category_id: int, data: ReorderRequest, db: Session = Depends(get_db)):
    return service.reorder_items(db, category_id, data)


@router.get("/contents/{content_id}/devices", response_model=list[DeviceVariantOut])
def get_content_devices(content_id: int, db: Session = Depends(get_db)):
    return service.get_devices_for_content(db, content_id)


@router.get("/sync/status", response_model=list[SyncStatusOut])
def get_sync_status(db: Session = Depends(get_db)):
    return service.get_sync_status(db)


# ── 큐레이션 워크벤치 Step 3 ──────────────────────────────────────────────────

@router.post("/curations/match-contents", response_model=MatchContentsResponse)
def match_curation_contents(body: MatchContentsRequest, db: Session = Depends(get_db)):
    """theme_features → 보유 콘텐츠 매칭 후보 (결정적 알고리즘, LLM 미사용)."""
    external_titles = {t.strip().lower() for t in body.external_titles if t.strip()}
    external_content_ids = set(body.external_content_ids) if body.external_content_ids else None
    results = match_contents(
        db, body.theme_features, external_titles,
        external_content_ids=external_content_ids,
        limit=body.limit,
    )
    items = [
        ContentMatchCandidateOut(
            content_id=r.content_id,
            title=r.title,
            content_type=r.content_type,
            production_year=r.production_year,
            runtime_minutes=r.runtime_minutes,
            score=r.score,
            score_breakdown=r.score_breakdown,
        )
        for r in results
    ]
    return MatchContentsResponse(
        items=items,
        total=len(items),
        theme_features=body.theme_features,
    )


@router.get("/curations/external-references", response_model=ExternalReferencesResponse)
def get_external_references(
    channel: str | None = Query(None, description="특정 채널 필터 (e.g., ott_watcha)"),
    db: Session = Depends(get_db),
):
    """외부 큐레이션 섹션 카드 목록 — 영속 테이블 읽기 우선, 비었으면 live 크롤 폴백.
    영속 데이터는 content_id(resolve) 포함."""
    from .models import ExternalCuration, ExternalCurationItem

    q = db.query(ExternalCuration)
    if channel:
        q = q.filter(ExternalCuration.channel == channel)
    rows = q.order_by(ExternalCuration.channel, ExternalCuration.id).all()

    if rows:
        cards: list[OttSectionCardOut] = []
        for row in rows:
            item_rows = (
                db.query(ExternalCurationItem)
                .filter(ExternalCurationItem.external_curation_id == row.id)
                .order_by(ExternalCurationItem.external_rank)
                .all()
            )
            cards.append(OttSectionCardOut(
                section_id=row.section_id,
                name=row.section_name,
                category_type=row.category_type,
                channel=row.channel,
                item_count=row.total_count,
                items=[
                    OttItemOut(
                        title=it.external_title,
                        rank=it.external_rank,
                        production_year=it.production_year,
                        external_id=None,
                        content_id=it.content_id,
                    )
                    for it in item_rows
                ],
            ))
        return ExternalReferencesResponse(sections=cards, total_sections=len(cards))

    # 영속 데이터 없을 때 live 크롤 폴백 (초기 세팅 전 또는 Beat 미실행 시)
    logger.info("external-references: 영속 데이터 없음 → live 크롤 폴백")
    from .ott.watcha import WatchaTopSource
    from .ott.netflix import NetflixTudumSource
    from .ott.wave import WaveTopSource
    from .ott.tving import TvingTopSource

    sources = [WatchaTopSource(), NetflixTudumSource(), WaveTopSource(), TvingTopSource()]
    if channel:
        sources = [s for s in sources if s.channel == channel]

    live_cards: list[OttSectionCardOut] = []
    for src in sources:
        try:
            sections = src.fetch_sections()
        except Exception:
            logger.exception("external-references live폴백: 소스 실패 channel=%s", src.channel)
            sections = []
        for sec in sections:
            live_cards.append(OttSectionCardOut(
                section_id=sec.section_id,
                name=sec.name,
                category_type=sec.category_type,
                channel=src.channel,
                item_count=len(sec.items),
                items=[
                    OttItemOut(
                        title=item.title,
                        rank=item.rank,
                        production_year=item.production_year,
                        external_id=item.external_id,
                        content_id=None,
                    )
                    for item in sec.items
                ],
            ))

    return ExternalReferencesResponse(sections=live_cards, total_sections=len(live_cards))


# ── 큐레이션 워크벤치 Step 4 ──────────────────────────────────────────────────

@router.post("/curations/propose-copy", response_model=ProposeCopyResponse)
async def propose_curation_copy(body: ProposeCopyRequest):
    """theme_features + 외부 섹션명 → LLM 카피 후보 (Gemini→Groq→Ollama 폴백).
    LLM 전체 실패 시 섹션명을 external_imported 후보로 반환."""
    from .copy_proposer import propose_copy

    candidates_raw, engine_used = await propose_copy(
        theme_features=body.theme_features,
        selected_section_names=body.selected_section_names,
        limit=body.limit,
    )
    candidates = [CopyCandidateOut(**c) for c in candidates_raw]
    return ProposeCopyResponse(candidates=candidates, engine_used=engine_used)
