from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from shared.database import get_db
from .schemas import (
    DistributionChannelOut, ServiceCategoryOut, ServiceCategoryWithItemsOut,
    ServiceCategoryCreate, ServiceCategoryUpdate,
    ServiceCategoryItemOut, ServiceCategoryItemCreate,
    ReorderRequest, DeviceVariantOut, SyncStatusOut, ServiceOut,
)
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
