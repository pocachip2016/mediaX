from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from shared.database import get_db
from .schemas import DistributionChannelOut, ServiceCategoryOut, DeviceVariantOut, SyncStatusOut, ServiceOut
from . import service

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


@router.get("/contents/{content_id}/devices", response_model=list[DeviceVariantOut])
def get_content_devices(content_id: int, db: Session = Depends(get_db)):
    return service.get_devices_for_content(db, content_id)


@router.get("/sync/status", response_model=list[SyncStatusOut])
def get_sync_status(db: Session = Depends(get_db)):
    return service.get_sync_status(db)
