"""
mh-bulk-e2e 통합 테스트

Step 10 검증:
  - 혼합 movie+series 배치 dispatch (process_batch_rows 진입점)
  - HTTP 라우터 POST /upload/batch E2E (CSV → DB state)
  - episode→series synopsis 상속 통합 (resolve_inherited_metadata)
  - ContentBatchJob 상태 전이 (pending→processing→done)
  - 빈 배치 / 부분 실패 / 재업로드 idempotency
  - dispatch 격리 (movie series_title 누수, series runtime 미매핑)
"""
import pytest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.programming.metadata.models.content import (
    Content, ContentBatchJob, ContentType, ContentStatus,
)
from api.programming.metadata.service import process_batch_rows
from api.programming.metadata.inheritance import resolve_inherited_metadata
from api.programming.metadata.router import router as metadata_router
from shared.database import Base, get_db

import api.programming.metadata.models  # noqa: F401
import api.meta_core.models  # noqa: F401
import api.meta_core.public_api.models  # noqa: F401
import api.distribution.models  # noqa: F401

_CELERY_PATCH = "workers.tasks.metadata.process_content_metadata"


def _job(db, cp="CP") -> ContentBatchJob:
    job = ContentBatchJob(job_name="test-job", cp_name=cp, status="pending")
    db.add(job)
    db.flush()
    return job


def _count(db, ctype: ContentType) -> int:
    return db.query(Content).filter(Content.content_type == ctype).count()


@pytest.fixture
def api_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    app = FastAPI()
    app.include_router(metadata_router)

    def override_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    session = Session()
    yield TestClient(app), session
    session.close()
    Base.metadata.drop_all(engine)


# ─── 혼합 배치 dispatch ────────────────────────────────────────────────────────

@patch(_CELERY_PATCH)
def test_mixed_movie_series_single_batch(mock_task, db):
    """단일 process_batch_rows 호출에서 movie+series 경로 독립 처리."""
    job = _job(db)
    rows = [
        {"title": "영화1", "content_type": "movie"},
        {"title": "영화2", "content_type": "movie", "runtime": 120},
        {"content_type": "episode", "series_title": "드라마A", "season_number": 1, "episode_number": 1, "title": "1화"},
        {"content_type": "episode", "series_title": "드라마A", "season_number": 1, "episode_number": 2, "title": "2화"},
    ]
    result = process_batch_rows(db, job, rows)
    # movie 2 + series 1 + season 1 + episode 2 = 6
    assert result["success"] == 6
    assert _count(db, ContentType.movie) == 2
    assert _count(db, ContentType.series) == 1
    assert _count(db, ContentType.season) == 1
    assert _count(db, ContentType.episode) == 2


# ─── HTTP 라우터 E2E ───────────────────────────────────────────────────────────

@patch(_CELERY_PATCH)
def test_router_upload_batch_e2e(mock_task, api_client):
    """POST /upload/batch: CSV → 파싱 → process_batch_rows → DB state 통합 확인."""
    client, db = api_client
    csv_content = (
        "title,content_type,series_title,season_number,episode_number\n"
        "영화1,movie,,,\n"
        "영화2,movie,,,\n"
        "드라마A,series,,,\n"
        "1화,episode,드라마A,1,1\n"
        "2화,episode,드라마A,1,2\n"
    )
    resp = client.post(
        "/upload/batch",
        files={"file": ("test.csv", csv_content.encode("utf-8"), "text/csv")},
        data={"cp_name": "테스트CP"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["success_count"] == 6  # movie 2 + series 1 + season 1 + episode 2
    assert data["failed_count"] == 0
    assert data["status"] == "done"
    db.expire_all()
    assert _count(db, ContentType.movie) == 2
    assert _count(db, ContentType.series) == 1
    assert _count(db, ContentType.episode) == 2


# ─── 상속 통합 ────────────────────────────────────────────────────────────────

@patch(_CELERY_PATCH)
def test_episode_inherits_series_synopsis(mock_task, db):
    """series synopsis(50자+) 있을 때 episode가 resolve_inherited_metadata로 상속."""
    # _SYNOPSIS_MIN = 50 — inheritance.py 가 50자 미만 시놉시스는 상속 대상 제외
    long_synopsis = "상속드라마의 상세한 시놉시스 텍스트입니다. 이 내용은 에피소드에 read-time 상속되어야 합니다."
    assert len(long_synopsis) >= 50  # 사전 검증
    job = _job(db)
    rows = [
        {"content_type": "series", "series_title": "상속드라마", "synopsis": long_synopsis},
        {"content_type": "episode", "series_title": "상속드라마", "season_number": 1, "episode_number": 1, "title": "1화"},
    ]
    process_batch_rows(db, job, rows)

    episode = db.query(Content).filter(Content.content_type == ContentType.episode).first()
    assert episode is not None
    inherited = resolve_inherited_metadata(episode, db)
    assert inherited is not None
    assert inherited.get("synopsis") == long_synopsis


# ─── job 상태 전이 ─────────────────────────────────────────────────────────────

@patch(_CELERY_PATCH)
def test_batch_job_status_transitions(mock_task, db):
    """process_batch_rows 완료 후 job.status=done, 카운트 정확성."""
    job = _job(db)
    rows = [
        {"title": "영화A", "content_type": "movie"},
        {"content_type": "episode", "series_title": "드라마B", "season_number": 1, "episode_number": 1, "title": "E1"},
    ]
    process_batch_rows(db, job, rows)
    db.refresh(job)
    assert job.status == "done"
    assert job.success_count == 4  # movie 1 + series 1 + season 1 + episode 1
    assert job.failed_count == 0
    assert job.parsed_count == 2
    assert job.finished_at is not None


# ─── 빈 배치 ──────────────────────────────────────────────────────────────────

@patch(_CELERY_PATCH)
def test_empty_batch_completes(mock_task, db):
    """rows=[] → success=0, job.status=done, 예외 없음."""
    job = _job(db)
    result = process_batch_rows(db, job, [])
    db.refresh(job)
    assert result["success"] == 0
    assert result["failed"] == 0
    assert job.status == "done"
    assert job.parsed_count == 0


# ─── 부분 실패 ────────────────────────────────────────────────────────────────

@patch(_CELERY_PATCH)
def test_partial_failure_counts(mock_task, db):
    """title 없는 movie 행 → failed=1, 정상 행 → success=1, error_log 기록."""
    job = _job(db)
    rows = [
        {"title": "정상영화", "content_type": "movie"},
        {"title": "", "content_type": "movie"},
    ]
    result = process_batch_rows(db, job, rows)
    db.refresh(job)
    assert result["success"] == 1
    assert result["failed"] == 1
    assert len(job.error_log) == 1


# ─── 재업로드 idempotency ─────────────────────────────────────────────────────

@patch(_CELERY_PATCH)
def test_reupload_idempotent_mixed(mock_task, db):
    """동일 혼합 배치 2회 업로드 → Content 수 불변, skipped_duplicates >= 2."""
    rows = [
        {"title": "영화X", "content_type": "movie"},
        {"content_type": "series", "series_title": "드라마X"},
    ]
    job1 = _job(db)
    process_batch_rows(db, job1, rows)
    count_first = db.query(Content).count()

    job2 = _job(db)
    result2 = process_batch_rows(db, job2, rows)
    count_second = db.query(Content).count()

    assert count_second == count_first
    assert result2["skipped_duplicates"] >= 2  # movie 1 + series 1 dedup


# ─── dispatch 격리 ────────────────────────────────────────────────────────────

@patch(_CELERY_PATCH)
def test_dispatch_isolation(mock_task, db):
    """movie 행의 series_title 누수 없음 + series 행의 runtime 미매핑."""
    job = _job(db)
    rows = [
        {"title": "영화Z", "content_type": "movie", "series_title": "누수테스트", "runtime": 90},
        {"title": "드라마Z", "content_type": "series", "runtime": 120},
    ]
    process_batch_rows(db, job, rows)

    movie = db.query(Content).filter(Content.title == "영화Z").first()
    assert movie.runtime_minutes == 90
    assert movie.content_type == ContentType.movie

    series = db.query(Content).filter(Content.title == "드라마Z").first()
    assert series.runtime_minutes is None  # series는 runtime_minutes 미매핑

    assert db.query(Content).filter(Content.title == "누수테스트").first() is None
