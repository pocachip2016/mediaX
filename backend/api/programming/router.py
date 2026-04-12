from fastapi import APIRouter
from api.programming.metadata.router import router as metadata_router

router = APIRouter()

router.include_router(metadata_router, prefix="/metadata", tags=["1.1 메타데이터 AI"])

# TODO: 추후 추가
# from api.programming.catalog.router import router as catalog_router
# from api.programming.curation.router import router as curation_router
# router.include_router(catalog_router, prefix="/catalog", tags=["1.2 카탈로그"])
# router.include_router(curation_router, prefix="/curation", tags=["1.3 큐레이션"])
