"""
mh-bulk-series 단위 테스트

Step 9 검증:
  - _process_series_rows: series→season→episode upsert + parent_id 자동 링크
  - series_title 기준 그룹핑
  - 재업로드 idempotency (중복 생성 X)
  - season_number 없는 series 단독 행
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


def _count(db, ctype: ContentType) -> int:
    return db.query(Content).filter(Content.content_type == ctype).count()


# ─── 기본 계층 구성 ────────────────────────────────────────────────────────────

@patch(_CELERY_PATCH)
def test_series_rows_create_hierarchy(mock_task, db):
    """series + season 2 + episode 4 → 계층 자동 구성."""
    job = _job(db)
    rows = [
        {"content_type": "series", "series_title": "드라마A", "synopsis": "드라마A 시놉시스"},
        {"content_type": "episode", "series_title": "드라마A", "season_number": 1, "episode_number": 1, "title": "1화"},
        {"content_type": "episode", "series_title": "드라마A", "season_number": 1, "episode_number": 2, "title": "2화"},
        {"content_type": "episode", "series_title": "드라마A", "season_number": 2, "episode_number": 1, "title": "S2E1"},
        {"content_type": "episode", "series_title": "드라마A", "season_number": 2, "episode_number": 2, "title": "S2E2"},
    ]
    result = process_batch_rows(db, job, rows)
    assert result["success"] == 7  # series1 + season2 + episode4

    series = db.query(Content).filter(
        Content.title == "드라마A", Content.content_type == ContentType.series
    ).first()
    assert series is not None
    assert series.parent_id is None

    seasons = db.query(Content).filter(
        Content.parent_id == series.id, Content.content_type == ContentType.season
    ).all()
    assert len(seasons) == 2

    for season in seasons:
        episodes = db.query(Content).filter(
            Content.parent_id == season.id, Content.content_type == ContentType.episode
        ).all()
        assert len(episodes) == 2


@patch(_CELERY_PATCH)
def test_parent_id_chain_correct(mock_task, db):
    """episode.parent_id → season, season.parent_id → series."""
    job = _job(db)
    rows = [
        {"content_type": "episode", "series_title": "체인테스트", "season_number": 1, "episode_number": 1},
    ]
    process_batch_rows(db, job, rows)

    series = db.query(Content).filter(Content.title == "체인테스트").first()
    season = db.query(Content).filter(
        Content.parent_id == series.id, Content.content_type == ContentType.season
    ).first()
    episode = db.query(Content).filter(
        Content.parent_id == season.id, Content.content_type == ContentType.episode
    ).first()

    assert season.parent_id == series.id
    assert episode.parent_id == season.id
    assert season.season_number == 1
    assert episode.episode_number == 1


@patch(_CELERY_PATCH)
def test_series_only_row(mock_task, db):
    """season/episode 없는 series 단독 행 → series만 생성."""
    job = _job(db)
    rows = [{"content_type": "series", "series_title": "시리즈만", "synopsis": "단독 시리즈"}]
    result = process_batch_rows(db, job, rows)
    assert result["success"] == 1
    assert _count(db, ContentType.series) == 1
    assert _count(db, ContentType.season) == 0
    assert _count(db, ContentType.episode) == 0


# ─── episode runtime 매핑 ─────────────────────────────────────────────────────

@patch(_CELERY_PATCH)
def test_episode_runtime_mapped(mock_task, db):
    """episode 행의 runtime=45 → Content.runtime_minutes=45."""
    job = _job(db)
    rows = [
        {"content_type": "episode", "series_title": "런타임드라마", "season_number": 1,
         "episode_number": 1, "runtime": 45},
    ]
    process_batch_rows(db, job, rows)
    episode = db.query(Content).filter(Content.content_type == ContentType.episode).first()
    assert episode.runtime_minutes == 45


# ─── 재업로드 idempotency ─────────────────────────────────────────────────────

@patch(_CELERY_PATCH)
def test_series_reupload_idempotent(mock_task, db):
    """동일 CSV 2회 업로드 → 중복 Content 미생성, skipped_duplicates 증가."""
    rows = [
        {"content_type": "episode", "series_title": "반복드라마", "season_number": 1, "episode_number": 1},
        {"content_type": "episode", "series_title": "반복드라마", "season_number": 1, "episode_number": 2},
    ]
    job1 = _job(db)
    process_batch_rows(db, job1, rows)
    count_after_first = db.query(Content).count()

    job2 = _job(db)
    result2 = process_batch_rows(db, job2, rows)
    count_after_second = db.query(Content).count()

    assert count_after_second == count_after_first
    assert result2["skipped_duplicates"] >= 1  # series 중복


@patch(_CELERY_PATCH)
def test_series_title_fallback_to_title(mock_task, db):
    """series_title 없으면 title 컬럼을 series_title 대체로 사용."""
    job = _job(db)
    rows = [
        {"content_type": "series", "title": "타이틀대체시리즈"},
    ]
    result = process_batch_rows(db, job, rows)
    assert result["success"] == 1
    series = db.query(Content).filter(Content.content_type == ContentType.series).first()
    assert series.title == "타이틀대체시리즈"


# ─── 다중 시리즈 독립 처리 ────────────────────────────────────────────────────

@patch(_CELERY_PATCH)
def test_multiple_series_independent(mock_task, db):
    """서로 다른 series_title → 각각 독립 계층."""
    job = _job(db)
    rows = [
        {"content_type": "episode", "series_title": "드라마X", "season_number": 1, "episode_number": 1},
        {"content_type": "episode", "series_title": "드라마Y", "season_number": 1, "episode_number": 1},
    ]
    process_batch_rows(db, job, rows)
    assert _count(db, ContentType.series) == 2
    assert _count(db, ContentType.season) == 2
    assert _count(db, ContentType.episode) == 2

    x = db.query(Content).filter(Content.title == "드라마X").first()
    y = db.query(Content).filter(Content.title == "드라마Y").first()
    assert x.id != y.id

    x_ep = db.query(Content).filter(Content.content_type == ContentType.episode,
                                     Content.cp_name == x.cp_name).first()
    # episode의 season이 올바른 series에 연결됐는지 확인
    x_season = db.query(Content).filter(Content.id == x_ep.parent_id).first()
    assert x_season.parent_id == x.id
