"""
dev-stage-manual-steps — 내부처리/다음단계 분리 회귀 테스트 (ADR-009)

핵심 가드:
  - /advance: work 없이 status 1칸 진행, StageEvent(ADVANCED) 기록
  - /enrich-source: 단일 소스 회수, status 불변
  - run_single_ai_task: 단일 AiTask 실행, status 불변
  - enrich_content(only_sources): 지정 소스만 강제 실행
  - advance terminal: approved → terminal 반환, status 미변경

pytest tests/test_stage_manual_steps.py -q
"""
import asyncio
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import api.programming.metadata.models          # noqa: F401
import api.meta_core.models                     # noqa: F401
import api.meta_core.public_api.models          # noqa: F401
import api.distribution.models                  # noqa: F401
from shared.database import Base, get_db
from main import app

from api.programming.metadata.models import (
    Content, ContentMetadata, ContentStatus, ContentType,
)
from api.programming.metadata.models.stage_event import StageEvent
from api.programming.metadata.models.content import StageEventType, PipelineStage
from api.programming.metadata.schemas import AIGenerateResponse


# ── fixtures ────────────────────────────────────────────────────────────────
# client와 db는 동일한 module-scoped 엔진을 공유 — 테스트 간 데이터 일관성 보장.

_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
_Session = sessionmaker(bind=_engine)


@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(_engine)
    def override():
        d = _Session()
        try: yield d
        finally: d.close()
    app.dependency_overrides[get_db] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    Base.metadata.drop_all(_engine)


@pytest.fixture
def db(client):  # client 의존 → 같은 엔진 사용 보장
    session = _Session()
    yield session
    session.rollback()
    session.close()


def _make(db, status=ContentStatus.raw, title="테스트"):
    c = Content(title=title, content_type=ContentType.movie, cp_name="TEST_MSS", status=status)
    db.add(c); db.flush()
    db.add(ContentMetadata(content_id=c.id, quality_score=0.0)); db.flush()
    return c


def _mock_gen(score: float):
    async def _inner(req, db_):
        return AIGenerateResponse(
            synopsis="mock", genre_primary="드라마", genre_secondary=None,
            mood_tags=["테스트"], rating_suggestion="전체관람가", quality_score=score,
        ), "mock_engine"
    return _inner


# ── advance (status bump, no work) ──────────────────────────────────────────

def test_advance_raw_to_enriched(client, db):
    """advance: raw → enriched, work 없음."""
    c = _make(db, ContentStatus.raw)
    db.commit()
    res = client.post("/api/test/pipeline/advance", json={"ids": [c.id]})
    assert res.status_code == 200
    data = res.json()
    assert data["advanced"] == 1
    assert data["results"][str(c.id)] == "enriched"
    db.refresh(c)
    assert c.status == ContentStatus.enriched


def test_advance_records_stage_event(client, db):
    """advance는 StageEvent(ADVANCED) 를 기록한다."""
    c = _make(db, ContentStatus.raw)
    db.commit()
    before = db.query(StageEvent).filter(StageEvent.content_id == c.id,
                                         StageEvent.event_type == StageEventType.ADVANCED).count()
    client.post("/api/test/pipeline/advance", json={"ids": [c.id]})
    after = db.query(StageEvent).filter(StageEvent.content_id == c.id,
                                        StageEvent.event_type == StageEventType.ADVANCED).count()
    assert after == before + 1


def test_advance_full_chain(client, db):
    """raw → enriched → ai → review → approved (각 advance 1칸)."""
    c = _make(db, ContentStatus.raw)
    db.commit()
    for expected in ("enriched", "ai", "review", "approved"):
        r = client.post("/api/test/pipeline/advance", json={"ids": [c.id]})
        assert r.json()["results"][str(c.id)] == expected


def test_advance_terminal_approved(client, db):
    """approved 는 terminal — status 미변경."""
    c = _make(db, ContentStatus.approved)
    db.commit()
    r = client.post("/api/test/pipeline/advance", json={"ids": [c.id]})
    assert r.json()["results"][str(c.id)] == "terminal"
    db.refresh(c)
    assert c.status == ContentStatus.approved


# ── enrich-source (status unchanged) ────────────────────────────────────────

def test_enrich_source_status_unchanged(client, db):
    """enrich-source 실행 후 status 불변."""
    c = _make(db, ContentStatus.raw)
    db.commit()
    r = client.post("/api/test/pipeline/enrich-source",
                    json={"content_id": c.id, "source": "tmdb"})
    assert r.status_code == 200
    assert r.json()["status_unchanged"] == "raw"
    db.refresh(c)
    assert c.status == ContentStatus.raw


def test_enrich_source_invalid_source(client, db):
    """invalid source 는 422."""
    c = _make(db)
    db.commit()
    r = client.post("/api/test/pipeline/enrich-source",
                    json={"content_id": c.id, "source": "websearch"})
    assert r.status_code == 422


# ── AI task sub-step (status unchanged) ─────────────────────────────────────

def test_run_ai_task_list(client):
    """ai-tasks GET 는 5개 태스크 반환."""
    r = client.get("/api/test/pipeline/ai-tasks")
    assert r.status_code == 200
    tasks = r.json()["tasks"]
    assert set(tasks) == {"translate_synopsis", "short_synopsis", "genre_normalized", "mood_tags", "keywords"}


def test_run_ai_task_unknown(client, db):
    """unknown task_name 은 422."""
    c = _make(db); db.commit()
    r = client.post("/api/test/pipeline/run-ai-task",
                    json={"content_id": c.id, "task_name": "nonexistent_task"})
    assert r.status_code == 422


def test_run_single_ai_task_status_unchanged(db, monkeypatch):
    """run_single_ai_task: 태스크 실행 후 status 불변."""
    import api.programming.metadata.ai_engine as eng
    monkeypatch.setattr(eng, "_generate_metadata_with_engine", _mock_gen(80.0))

    from api.programming.metadata.ai_tasks.runner import run_single_ai_task
    c = _make(db, ContentStatus.enriched)
    db.commit()

    result = asyncio.run(run_single_ai_task(c.id, "genre_normalized", db))
    assert result["status"] in ("ok", "skip", "cached")
    db.refresh(c)
    assert c.status == ContentStatus.enriched  # status 불변


# ── enrich_content(only_sources) ────────────────────────────────────────────

def test_enrich_only_sources_skips_others(db):
    """only_sources={tmdb} 지정 시 kmdb 는 실행 안 됨."""
    from api.meta_core.enrich import enrich_content
    c = _make(db); db.commit()
    result = enrich_content(c.id, db, only_sources={"tmdb"})
    # tmdb 는 시도(API 키 없으면 no_key skip), kmdb 는 아예 미시도
    assert "kmdb" not in result.sources_hit
    assert "kmdb:no_key" not in result.sources_skipped  # kmdb 자체를 호출 안 함
