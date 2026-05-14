"""
poster_url 컬럼 포함 CSV 업로드 → ContentImage 생성 테스트
"""
from unittest.mock import patch

import pytest

from api.programming.metadata.models import ContentBatchJob
from api.programming.metadata.schemas import BatchUploadRow
from api.programming.metadata.service import process_batch_rows


def _make_job(db) -> ContentBatchJob:
    job = ContentBatchJob(
        job_name="test-job",
        file_name="test.csv",
        status="pending",
        total_count=0,
        success_count=0,
        failed_count=0,
        parsed_count=0,
    )
    db.add(job)
    db.flush()
    return job


@patch("workers.tasks.metadata.process_content_metadata.delay")
def test_poster_url_creates_content_image(mock_delay, db):
    """poster_url 포함 행 업로드 시 ContentImage 1건 생성, source='cp', is_primary=True"""
    from api.programming.metadata.models import ContentImage

    job = _make_job(db)
    rows = [{
        "title": "테스트 영화",
        "production_year": 2024,
        "content_type": "movie",
        "cp_name": "Watcha",
        "cp_synopsis": "테스트 시놉시스",
        "poster_url": "https://example.com/poster.jpg",
    }]

    result = process_batch_rows(db, job, rows)

    assert result["success"] == 1
    assert result["failed"] == 0

    images = db.query(ContentImage).filter(ContentImage.image_type == "poster").all()
    assert len(images) == 1
    assert images[0].url == "https://example.com/poster.jpg"
    assert images[0].source == "cp"
    assert images[0].is_primary is True


@patch("workers.tasks.metadata.process_content_metadata.delay")
def test_no_poster_url_skips_image(mock_delay, db):
    """poster_url 없는 행은 ContentImage 생성 안 함"""
    from api.programming.metadata.models import ContentImage

    job = _make_job(db)
    rows = [{
        "title": "포스터 없는 영화",
        "production_year": 2023,
        "content_type": "movie",
        "cp_name": "Test CP",
        "cp_synopsis": "",
        "poster_url": None,
    }]

    process_batch_rows(db, job, rows)

    count = db.query(ContentImage).count()
    assert count == 0


@patch("workers.tasks.metadata.process_content_metadata.delay")
def test_duplicate_poster_url_idempotent(mock_delay, db):
    """동일 poster_url 로 두 번 업로드해도 ContentImage 는 1건만 존재"""
    from api.programming.metadata.models import ContentImage

    job1 = _make_job(db)
    job2 = _make_job(db)
    row = [{
        "title": "중복 테스트",
        "production_year": 2024,
        "content_type": "movie",
        "cp_name": "Watcha",
        "cp_synopsis": "",
        "poster_url": "/static/posters/test.jpg",
    }]

    process_batch_rows(db, job1, row)
    process_batch_rows(db, job2, row)

    # 같은 제목/CP 로 두 번 업로드되면 Content 는 2건이지만
    # 각 Content 의 ContentImage 는 1건씩이어야 함
    images = db.query(ContentImage).filter(ContentImage.image_type == "poster").all()
    assert len(images) == 2
    assert all(img.is_primary is True for img in images)


@patch("workers.tasks.metadata.process_content_metadata.delay")
def test_batch_upload_row_schema_has_poster_url(_mock, db):
    """BatchUploadRow 스키마에 poster_url 필드 존재"""
    row = BatchUploadRow(title="test")
    assert hasattr(row, "poster_url")
    assert row.poster_url is None

    row_with_poster = BatchUploadRow(title="test", poster_url="https://x.com/p.jpg")
    assert row_with_poster.poster_url == "https://x.com/p.jpg"
