from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.meta_core.router import router as meta_core_router
from api.programming.router import router as programming_router
from api.design.router import router as design_router
from api.ingest.router import router as ingest_router
from api.analytics.router import router as analytics_router
from api.marketing.router import router as marketing_router
from api.monitoring.router import router as monitoring_router
from api.common.router import router as common_router
from api.distribution.router import router as distribution_router

@asynccontextmanager
async def lifespan(app):
    from api.meta_core.public_api.changefeed import setup_changefeed_events
    setup_changefeed_events()
    yield


app = FastAPI(
    title="미디어AX API",
    description="VOD AI Transformation Platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
        "http://localhost:4000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_POSTERS_DIR = Path(__file__).parent / "data" / "watcha_real" / "posters"
_POSTERS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static/posters", StaticFiles(directory=str(_POSTERS_DIR)), name="posters")

app.include_router(meta_core_router,   prefix="/api/meta-core",   tags=["Meta-Core (canonical)"])
app.include_router(programming_router, prefix="/api/programming", tags=["편성 기획 AX"])
app.include_router(design_router,      prefix="/api/design",      tags=["디자인 AX"])
app.include_router(ingest_router,      prefix="/api/ingest",      tags=["인제스트 AX"])
app.include_router(analytics_router,   prefix="/api/analytics",   tags=["통계 AX"])
app.include_router(marketing_router,   prefix="/api/marketing",   tags=["마케팅 AX"])
app.include_router(monitoring_router,  prefix="/api/monitoring",  tags=["모니터링 AX"])
app.include_router(common_router,      prefix="/api/common",      tags=["공통 인프라"])
app.include_router(distribution_router,prefix="/api/distribution",tags=["배포 AX"])


@app.get("/health")
def health():
    return {"status": "ok"}
