"""
GET /api/programming/metadata/contents/{id}/timeline 테스트

확인:
  - 404: 존재하지 않는 content_id
  - waiting 상태: stage 1 done, 2~6 pending
  - staging 상태: stage 1~3 done or active
  - approved 상태: stage 1~5 done
  - 6개 stage 항목 반환
  - stage 1 detail에 cp_name 포함
  - stage 3 detail에 sources 목록 포함
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import datetime, timezone

import api.programming.metadata.models  # noqa
import api.meta_core.models             # noqa
import api.meta_core.public_api.models  # noqa
import api.distribution.models          # noqa
from shared.database import Base, get_db
from main import app

from api.programming.metadata.models import (
    Content, ContentMetadata, ContentType, ContentStatus, MetaSource,
    ContentAIResult, AITaskType, ExternalMetaSource, ExternalSourceType,
)


@pytest.fixture
def test_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    app.dependency_overrides[get_db] = lambda: session
    yield session
    session.close()
    Base.metadata.drop_all(engine)
    app.dependency_overrides.clear()


@pytest.fixture
def client(test_db):
    return TestClient(app)


def _make_content(db, status: ContentStatus, cp_name="TEST") -> Content:
    c = Content(
        title=f"테스트콘텐츠-{status.value}", content_type=ContentType.movie,
        status=status, cp_name=cp_name, production_year=2024, country="KR",
    )
    db.add(c)
    db.flush()
    db.add(ContentMetadata(
        content_id=c.id, quality_score=85.0,
        ai_synopsis="테스트 시놉시스", ai_genre_primary="DRM",
        ai_mood_tags=["따뜻한"], final_source=MetaSource.ai,
    ))
    db.flush()
    return c


def test_timeline_404(client):
    res = client.get("/api/programming/metadata/contents/99999/timeline")
    assert res.status_code == 404


def test_timeline_returns_6_stages(client, test_db):
    c = _make_content(test_db, ContentStatus.raw)
    test_db.commit()
    res = client.get(f"/api/programming/metadata/contents/{c.id}/timeline")
    assert res.status_code == 200
    data = res.json()
    assert len(data["stages"]) == 6
    assert data["content_id"] == c.id
    assert data["current_status"] == "raw"


def test_timeline_waiting_stage1_done(client, test_db):
    c = _make_content(test_db, ContentStatus.raw)
    test_db.commit()
    res = client.get(f"/api/programming/metadata/contents/{c.id}/timeline")
    stages = res.json()["stages"]
    assert stages[0]["stage"] == 1
    assert stages[0]["status"] == "done"   # 생성 = 항상 done
    assert stages[0]["at"] is not None
    assert stages[0]["detail"]["cp_name"] == "TEST"
    # 나머지는 pending/active
    for s in stages[1:]:
        assert s["status"] in ("pending", "active")


def test_timeline_with_ai_result(client, test_db):
    c = _make_content(test_db, ContentStatus.ai)
    test_db.add(ContentAIResult(
        content_id=c.id, engine="llama3.2:3b",
        task_type=AITaskType.synopsis,
        result_json={"synopsis": "test"}, quality_score=85.0,
        is_final=True, processed_at=datetime.now(timezone.utc),
    ))
    test_db.add(ExternalMetaSource(
        content_id=c.id, source_type=ExternalSourceType.tmdb,
        external_id="496243", title_on_source="Parasite",
        raw_json={}, match_confidence=0.95,
        matched_at=datetime.now(timezone.utc),
    ))
    test_db.commit()

    res = client.get(f"/api/programming/metadata/contents/{c.id}/timeline")
    assert res.status_code == 200
    stages = res.json()["stages"]

    stage2 = stages[1]
    assert stage2["at"] is not None
    assert stage2["detail"]["engine"] == "llama3.2:3b"
    assert stage2["detail"]["quality_score"] == 85.0

    stage3 = stages[2]
    assert stage3["at"] is not None
    assert "tmdb" in stage3["detail"]["sources"]


def test_timeline_approved_stages_done(client, test_db):
    c = _make_content(test_db, ContentStatus.approved)
    test_db.commit()
    res = client.get(f"/api/programming/metadata/contents/{c.id}/timeline")
    stages = res.json()["stages"]
    # stage 1~5는 done (stage 6은 미구현 → pending)
    for s in stages[:5]:
        assert s["status"] == "done", f"Stage {s['stage']} should be done for approved content"
    assert stages[5]["status"] == "pending"


def test_timeline_stage6_always_pending(client, test_db):
    c = _make_content(test_db, ContentStatus.approved)
    test_db.commit()
    res = client.get(f"/api/programming/metadata/contents/{c.id}/timeline")
    stage6 = res.json()["stages"][5]
    assert stage6["stage"] == 6
    assert stage6["name"] == "게시"
    assert stage6["status"] == "pending"
    assert stage6["at"] is None
