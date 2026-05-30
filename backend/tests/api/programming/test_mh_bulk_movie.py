"""
mh-bulk-movie 단위 테스트

Step 8 검증:
  - process_batch_rows: movie/tv-type 디스패치 분리
  - _process_movie_row: runtime → runtime_minutes 매핑 (양수만, 0/음수 무시)
  - movie dedup 회귀 (Phase B content_type 포함 키)
"""
import pytest
from unittest.mock import patch

from api.programming.metadata.models.content import (
    Content, ContentBatchJob, ContentType, ContentStatus,
)
from api.programming.metadata.service import process_batch_rows

_CELERY_PATCH = "workers.tasks.metadata.process_content_metadata"


def _job(db, cp="CP") -> ContentBatchJob:
    job = ContentBatchJob(job_name="test-job", cp_name=cp, status="pending")
    db.add(job)
    db.flush()
    return job


# ─── runtime_minutes 매핑 ─────────────────────────────────────────────────────

@patch(_CELERY_PATCH)
def test_runtime_mapped_to_runtime_minutes(mock_task, db):
    job = _job(db)
    process_batch_rows(db, job, [{"title": "영화A", "content_type": "movie", "runtime": 90}])
    content = db.query(Content).filter(Content.title == "영화A").first()
    assert content is not None
    assert content.runtime_minutes == 90


@patch(_CELERY_PATCH)
def test_runtime_zero_not_mapped(mock_task, db):
    job = _job(db)
    process_batch_rows(db, job, [{"title": "영화B", "content_type": "movie", "runtime": 0}])
    content = db.query(Content).filter(Content.title == "영화B").first()
    assert content.runtime_minutes is None


@patch(_CELERY_PATCH)
def test_runtime_negative_not_mapped(mock_task, db):
    job = _job(db)
    process_batch_rows(db, job, [{"title": "영화C", "content_type": "movie", "runtime": -5}])
    content = db.query(Content).filter(Content.title == "영화C").first()
    assert content.runtime_minutes is None


@patch(_CELERY_PATCH)
def test_runtime_none_not_mapped(mock_task, db):
    job = _job(db)
    process_batch_rows(db, job, [{"title": "영화D", "content_type": "movie"}])
    content = db.query(Content).filter(Content.title == "영화D").first()
    assert content.runtime_minutes is None


# ─── 디스패치 분기 ────────────────────────────────────────────────────────────

@patch(_CELERY_PATCH)
def test_tv_rows_not_created_as_movie(mock_task, db):
    """series/episode 행은 movie Content 미생성 — TV-type은 series 계층으로 처리됨."""
    job = _job(db)
    result = process_batch_rows(db, job, [
        {"title": "드라마A", "content_type": "series"},
        {"title": "에피소드1", "content_type": "episode"},
    ])
    assert db.query(Content).filter(Content.content_type == ContentType.movie).count() == 0
    assert result["success"] >= 1  # TV-type 행은 series 계층으로 생성됨


@patch(_CELERY_PATCH)
def test_mixed_rows_movie_only_dispatched(mock_task, db):
    """movie 2 + series 1 혼재 → movie 2건은 평면, series 1건은 독립 계층으로 처리."""
    job = _job(db)
    rows = [
        {"title": "영화1", "content_type": "movie", "runtime": 100},
        {"title": "영화2", "content_type": "movie"},
        {"title": "시리즈A", "content_type": "series"},
    ]
    result = process_batch_rows(db, job, rows)
    assert result["success"] == 3  # movie 2 + series 1
    assert db.query(Content).filter(Content.content_type == ContentType.movie).count() == 2
    assert db.query(Content).filter(Content.content_type == ContentType.series).count() == 1


# ─── movie dedup 회귀 ─────────────────────────────────────────────────────────

@patch(_CELERY_PATCH)
def test_movie_dedup_skips_duplicate(mock_task, db):
    job = _job(db)
    row = {"title": "중복영화", "content_type": "movie", "production_year": 2024}
    process_batch_rows(db, job, [row])
    job2 = _job(db)
    result2 = process_batch_rows(db, job2, [row])
    assert result2["skipped_duplicates"] == 1
    assert db.query(Content).filter(Content.title == "중복영화").count() == 1


@patch(_CELERY_PATCH)
def test_movie_content_type_and_status(mock_task, db):
    """생성된 Content는 content_type=movie, status=waiting."""
    job = _job(db)
    process_batch_rows(db, job, [{"title": "테스트영화", "content_type": "movie"}])
    content = db.query(Content).first()
    assert content.content_type == ContentType.movie
    assert content.status == ContentStatus.raw
