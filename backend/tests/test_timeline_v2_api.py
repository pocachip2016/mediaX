"""ADR-006 timeline v2 API 테스트 — 9-stage pipeline response."""

import pytest
from fastapi.testclient import TestClient

from main import app
from shared.database import get_db
from api.programming.metadata.models.content import (
    Content, ContentType, ContentStatus, IntakeChannel,
    PipelineStage, StageEventType,
)
from api.programming.metadata.models.stage_event import StageEvent


@pytest.fixture
def test_db(db):
    """HTTP TestClient 용 db override."""
    app.dependency_overrides[get_db] = lambda: db
    yield db
    app.dependency_overrides.clear()


@pytest.fixture
def client(test_db):
    """TestClient."""
    return TestClient(app)


def test_timeline_v2_empty_content(test_db, client):
    """stage_event 없음 → pipeline_stages 9개 전부 pending."""
    content = Content(
        title="빈 콘텐츠",
        content_type=ContentType.movie,
        status=ContentStatus.waiting,
    )
    test_db.add(content)
    test_db.commit()

    resp = client.get(f"/api/programming/metadata/contents/{content.id}/timeline")
    assert resp.status_code == 200
    data = resp.json()

    assert "pipeline_stages" in data
    assert len(data["pipeline_stages"]) == 9
    for stage in data["pipeline_stages"]:
        assert stage["status"] == "pending"
        assert stage["sources"] == []


def test_timeline_v2_s1_to_s7_flow(test_db, client):
    """S1 COMPLETED, S3 COMPLETED, S4 COMPLETED → 해당 stage done, 이후 pending."""
    content = Content(
        title="흐름 테스트",
        content_type=ContentType.movie,
        status=ContentStatus.processing,
    )
    test_db.add(content)
    test_db.flush()

    # S1 완료
    ev_s1_entered = StageEvent(
        content_id=content.id,
        stage=PipelineStage.S1_INTAKE,
        event_type=StageEventType.ENTERED,
        source="email_poll",
        actor="system",
    )
    ev_s1_completed = StageEvent(
        content_id=content.id,
        stage=PipelineStage.S1_INTAKE,
        event_type=StageEventType.COMPLETED,
        source="email_poll",
        actor="system",
    )
    test_db.add_all([ev_s1_entered, ev_s1_completed])

    # S3 완료
    ev_s3_entered = StageEvent(
        content_id=content.id,
        stage=PipelineStage.S3_LLM_EXTRACT,
        event_type=StageEventType.ENTERED,
        source="ollama",
        actor="system",
    )
    ev_s3_completed = StageEvent(
        content_id=content.id,
        stage=PipelineStage.S3_LLM_EXTRACT,
        event_type=StageEventType.COMPLETED,
        source="ollama",
        actor="system",
    )
    test_db.add_all([ev_s3_entered, ev_s3_completed])

    # S4 완료
    ev_s4_entered = StageEvent(
        content_id=content.id,
        stage=PipelineStage.S4_SOURCE_MATCH,
        event_type=StageEventType.ENTERED,
        source="tmdb",
        actor="system",
    )
    ev_s4_completed = StageEvent(
        content_id=content.id,
        stage=PipelineStage.S4_SOURCE_MATCH,
        event_type=StageEventType.COMPLETED,
        source="tmdb",
        actor="system",
    )
    test_db.add_all([ev_s4_entered, ev_s4_completed])
    test_db.commit()

    resp = client.get(f"/api/programming/metadata/contents/{content.id}/timeline")
    assert resp.status_code == 200
    data = resp.json()

    # S1, S3, S4는 done
    assert data["pipeline_stages"][0]["status"] == "done"  # S1
    assert data["pipeline_stages"][2]["status"] == "done"  # S3
    assert data["pipeline_stages"][3]["status"] == "done"  # S4

    # S2, S5+ pending
    assert data["pipeline_stages"][1]["status"] == "pending"  # S2
    assert data["pipeline_stages"][4]["status"] == "pending"  # S5


def test_timeline_v2_s4_sources(test_db, client):
    """S4에 tmdb+kobis 2개 source → sources 배열에 2건."""
    content = Content(
        title="S4 소스 테스트",
        content_type=ContentType.movie,
        status=ContentStatus.processing,
    )
    test_db.add(content)
    test_db.flush()

    # S4 tmdb
    ev_s4_tmdb = StageEvent(
        content_id=content.id,
        stage=PipelineStage.S4_SOURCE_MATCH,
        event_type=StageEventType.COMPLETED,
        source="tmdb",
        latency_ms=412,
        payload_json={"tmdb_id": 1185528},
        actor="system",
    )
    # S4 kobis
    ev_s4_kobis = StageEvent(
        content_id=content.id,
        stage=PipelineStage.S4_SOURCE_MATCH,
        event_type=StageEventType.SKIPPED,
        source="kobis",
        latency_ms=201,
        actor="system",
    )
    test_db.add_all([ev_s4_tmdb, ev_s4_kobis])
    test_db.commit()

    resp = client.get(f"/api/programming/metadata/contents/{content.id}/timeline")
    assert resp.status_code == 200
    data = resp.json()

    s4 = data["pipeline_stages"][3]  # S4 = index 3
    assert s4["status"] == "done"
    assert len(s4["sources"]) == 2
    assert s4["sources"][0]["source"] == "kobis"
    assert s4["sources"][0]["result"] == "miss"
    assert s4["sources"][1]["source"] == "tmdb"
    assert s4["sources"][1]["result"] == "hit"
    assert s4["sources"][1]["latency_ms"] == 412


def test_timeline_v2_failed_stage(test_db, client):
    """S3 FAILED → S3 status=active, sources에 result=error."""
    content = Content(
        title="FAILED 테스트",
        content_type=ContentType.movie,
        status=ContentStatus.processing,
    )
    test_db.add(content)
    test_db.flush()

    ev_s3_entered = StageEvent(
        content_id=content.id,
        stage=PipelineStage.S3_LLM_EXTRACT,
        event_type=StageEventType.ENTERED,
        source="ollama",
        actor="system",
    )
    ev_s3_failed = StageEvent(
        content_id=content.id,
        stage=PipelineStage.S3_LLM_EXTRACT,
        event_type=StageEventType.FAILED,
        source="ollama",
        error_text="model timeout",
        actor="system",
    )
    test_db.add_all([ev_s3_entered, ev_s3_failed])
    test_db.commit()

    resp = client.get(f"/api/programming/metadata/contents/{content.id}/timeline")
    assert resp.status_code == 200
    data = resp.json()

    s3 = data["pipeline_stages"][2]
    assert s3["status"] == "active"
    assert len(s3["sources"]) == 1
    assert s3["sources"][0]["result"] == "error"


def test_timeline_v2_v1_compat(test_db, client):
    """응답에 기존 v1 `stages` 배열(6건) 보존."""
    content = Content(
        title="v1 호환 테스트",
        content_type=ContentType.movie,
        status=ContentStatus.approved,
    )
    test_db.add(content)
    test_db.commit()

    resp = client.get(f"/api/programming/metadata/contents/{content.id}/timeline")
    assert resp.status_code == 200
    data = resp.json()

    # v1 필드 보존
    assert "content_id" in data
    assert "title" in data
    assert "content_type" in data
    assert "current_status" in data
    assert "stages" in data
    assert len(data["stages"]) == 6  # 기존 6-stage
    assert all("stage" in s for s in data["stages"])
    assert all("name" in s for s in data["stages"])


def test_timeline_v2_intake_channel(test_db, client):
    """intake_channel=email_poll → 응답에 intake_channel 필드 포함."""
    content = Content(
        title="intake_channel 테스트",
        content_type=ContentType.movie,
        status=ContentStatus.waiting,
        intake_channel=IntakeChannel.EMAIL_POLL,
    )
    test_db.add(content)
    test_db.commit()

    resp = client.get(f"/api/programming/metadata/contents/{content.id}/timeline")
    assert resp.status_code == 200
    data = resp.json()

    assert "intake_channel" in data
    assert data["intake_channel"] == "email_poll"
    assert "current_stage" in data
    assert "pipeline_stages" in data
