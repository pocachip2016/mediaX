"""ADR-006 pipeline board API 테스트 — board / gate advance / events / mode."""

import pytest
from fastapi.testclient import TestClient

from main import app
from shared.database import get_db
from api.programming.metadata.models.content import (
    Content, ContentType, ContentStatus, IntakeChannel,
    PipelineStage, StageEventType, FailureCode,
)
from api.programming.metadata.models.stage_event import StageEvent
import api.programming.metadata.router_pipeline as rp_module


@pytest.fixture(autouse=True)
def reset_gate_modes():
    """각 테스트 전후로 _GATE_MODES 를 기본값으로 초기화."""
    original = {k: v for k, v in rp_module._GATE_MODES.items()}
    yield
    rp_module._GATE_MODES.clear()
    rp_module._GATE_MODES.update(original)


@pytest.fixture
def test_db(db):
    app.dependency_overrides[get_db] = lambda: db
    yield db
    app.dependency_overrides.clear()


@pytest.fixture
def client(test_db):
    return TestClient(app)


def test_board_response_structure(test_db, client):
    """board 응답에 channels_24h / stages(9개) / gates(6개) / alerts 확인."""
    resp = client.get("/api/pipeline/board")
    assert resp.status_code == 200
    data = resp.json()

    assert "channels_24h" in data
    assert "stages" in data
    assert "gates" in data
    assert "alerts" in data

    # 4채널 모두 포함
    for ch in ("email_poll", "manual", "bulk_csv", "dam_webhook"):
        assert ch in data["channels_24h"]
        assert "count" in data["channels_24h"][ch]

    # 9 stage 모두 포함
    assert len(data["stages"]) == 9
    for s in ("s1_intake", "s2_normalize", "s6_llm_extract", "s3_source_match",
              "s4_gap_detect", "s5_websearch_fill", "s7_staging", "s8_review", "s9_publish"):
        assert s in data["stages"]

    # 6 gate 포함
    assert len(data["gates"]) == 6
    for gate in ("GATE_1", "GATE_2", "GATE_3", "GATE_4", "GATE_5", "GATE_6"):
        assert gate in data["gates"]
        assert "mode" in data["gates"][gate]
        assert "pending" in data["gates"][gate]

    # alerts 3개 키
    assert "failed_queue" in data["alerts"]
    assert "rejected_archive" in data["alerts"]
    assert "enrichment_blocked" in data["alerts"]


def test_gate_advance_normal(test_db, client):
    """GATE_2 advance → 2 contents S4 이동 + advanced=2."""
    c1 = Content(title="영화A", content_type=ContentType.movie, status=ContentStatus.enriched,
                 current_stage=PipelineStage.S6_LLM_EXTRACT)
    c2 = Content(title="영화B", content_type=ContentType.movie, status=ContentStatus.enriched,
                 current_stage=PipelineStage.S6_LLM_EXTRACT)
    test_db.add_all([c1, c2])
    test_db.commit()

    resp = client.post("/api/pipeline/gate/GATE_2/advance", json={"content_ids": [c1.id, c2.id]})
    assert resp.status_code == 200
    data = resp.json()
    assert data["advanced"] == 2
    assert data["next_stage"] == "s3_source_match"

    # DB 반영 확인
    test_db.refresh(c1)
    assert c1.current_stage == PipelineStage.S3_SOURCE_MATCH


def test_gate_advance_if_match_conflict(test_db, client):
    """if_match 제공 시 최신 이벤트보다 오래되면 409."""
    content = Content(title="충돌 테스트", content_type=ContentType.movie, status=ContentStatus.enriched,
                      current_stage=PipelineStage.S6_LLM_EXTRACT)
    test_db.add(content)
    test_db.flush()

    # 이벤트 추가 (id > 0 이면 항상 최신)
    ev = StageEvent(
        content_id=content.id,
        stage=PipelineStage.S6_LLM_EXTRACT,
        event_type=StageEventType.ENTERED,
        actor="system",
    )
    test_db.add(ev)
    test_db.commit()

    # if_match=0 → 이벤트 id > 0 이므로 충돌 → 409
    resp = client.post(
        "/api/pipeline/gate/GATE_2/advance",
        json={"content_ids": [content.id], "if_match": 0},
    )
    assert resp.status_code == 409


def test_gate_mode_toggle(test_db, client):
    """GATE_1 mode=auto 토글 → board 응답에 auto 반환."""
    # toggle to auto
    resp = client.post("/api/pipeline/gate/GATE_1/mode", json={"mode": "auto"})
    assert resp.status_code == 200
    assert resp.json()["mode"] == "auto"

    # board에서 확인
    board = client.get("/api/pipeline/board").json()
    assert board["gates"]["GATE_1"]["mode"] == "auto"

    # 다시 manual로
    resp2 = client.post("/api/pipeline/gate/GATE_1/mode", json={"mode": "manual"})
    assert resp2.json()["mode"] == "manual"


def test_board_stage_top_contents(test_db, client):
    """S4 stage에 콘텐츠 2건 + tmdb/kobis 이벤트 → top_contents에 sources tree 포함."""
    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc)
    c1 = Content(title="외계+인 2부", content_type=ContentType.movie, status=ContentStatus.enriched,
                 current_stage=PipelineStage.S3_SOURCE_MATCH)
    c2 = Content(title="파묘", content_type=ContentType.movie, status=ContentStatus.enriched,
                 current_stage=PipelineStage.S3_SOURCE_MATCH)
    test_db.add_all([c1, c2])
    test_db.flush()

    # c1: tmdb hit + kobis miss + dam hit
    test_db.add_all([
        StageEvent(content_id=c1.id, stage=PipelineStage.S3_SOURCE_MATCH,
                   event_type=StageEventType.ENTERED, source=None,
                   started_at=now - timedelta(minutes=5), actor="system"),
        StageEvent(content_id=c1.id, stage=PipelineStage.S3_SOURCE_MATCH,
                   event_type=StageEventType.COMPLETED, source="tmdb",
                   latency_ms=412, actor="system"),
        StageEvent(content_id=c1.id, stage=PipelineStage.S3_SOURCE_MATCH,
                   event_type=StageEventType.SKIPPED, source="kobis",
                   latency_ms=201, actor="system"),
    ])
    # c2: tmdb only
    test_db.add(StageEvent(
        content_id=c2.id, stage=PipelineStage.S3_SOURCE_MATCH,
        event_type=StageEventType.ENTERED, source=None,
        started_at=now - timedelta(minutes=2), actor="system",
    ))
    test_db.commit()

    resp = client.get("/api/pipeline/board")
    assert resp.status_code == 200
    s4 = resp.json()["stages"]["s3_source_match"]
    assert s4["count"] == 2
    assert len(s4["top_contents"]) == 2

    # 가장 오래 머문 c1이 먼저
    top0 = s4["top_contents"][0]
    assert top0["id"] == c1.id
    assert top0["title"] == "외계+인 2부"
    sources = top0["sources"]
    assert len(sources) == 2  # tmdb + kobis
    src_map = {s["source"]: s for s in sources}
    assert src_map["tmdb"]["result"] == "hit"
    assert src_map["tmdb"]["latency_ms"] == 412
    assert src_map["kobis"]["result"] == "miss"


def test_board_stage_stats(test_db, client):
    """avg_seconds 평균 체류시간 + error_count 최근 FAILED 카운트 확인."""
    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc)
    c = Content(title="에러 테스트", content_type=ContentType.movie, status=ContentStatus.enriched,
                current_stage=PipelineStage.S6_LLM_EXTRACT)
    test_db.add(c)
    test_db.flush()

    # ENTERED 10분 전 → 약 600s
    test_db.add(StageEvent(
        content_id=c.id, stage=PipelineStage.S6_LLM_EXTRACT,
        event_type=StageEventType.ENTERED, source=None,
        started_at=now - timedelta(minutes=10), actor="system",
    ))
    # FAILED 최근 1h 이내
    test_db.add(StageEvent(
        content_id=c.id, stage=PipelineStage.S6_LLM_EXTRACT,
        event_type=StageEventType.FAILED, source="ollama",
        started_at=now - timedelta(minutes=3), error_text="timeout", actor="system",
    ))
    test_db.commit()

    resp = client.get("/api/pipeline/board")
    s3 = resp.json()["stages"]["s6_llm_extract"]
    # avg_seconds: 약 600 (±20s 허용)
    assert s3["avg_seconds"] is not None
    assert 580 <= s3["avg_seconds"] <= 620
    # error_count: 1
    assert s3["error_count"] == 1


def test_events_paging(test_db, client):
    """이벤트 10개 삽입 후 since/limit 페이징 검증."""
    content = Content(title="페이징 테스트", content_type=ContentType.movie, status=ContentStatus.enriched)
    test_db.add(content)
    test_db.flush()

    for i in range(10):
        ev = StageEvent(
            content_id=content.id,
            stage=PipelineStage.S1_INTAKE,
            event_type=StageEventType.ENTERED,
            source="manual",
            actor="system",
        )
        test_db.add(ev)
    test_db.commit()

    # 전체 조회
    resp = client.get("/api/pipeline/events?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 10

    # limit=5 페이징
    resp2 = client.get("/api/pipeline/events?limit=5")
    data2 = resp2.json()
    assert len(data2["items"]) == 5
    assert data2["next_cursor"] is not None

    # since= 로 다음 페이지
    cursor = data2["next_cursor"]
    resp3 = client.get(f"/api/pipeline/events?since={cursor}&limit=5")
    data3 = resp3.json()
    assert len(data3["items"]) >= 1
    # 모든 id는 cursor 보다 커야 함
    for item in data3["items"]:
        assert item["id"] > cursor
