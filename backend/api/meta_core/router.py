from fastapi import APIRouter

from api.meta_core.public_api.router import router as public_api_router
from api.meta_core.intelligence.router import router as intelligence_router

router = APIRouter()
router.include_router(public_api_router)
router.include_router(intelligence_router)

