"""
mh-dedup-delete 단위 테스트

Step 6 검증:
  - process_batch_rows: content_type 포함 dedup 키
  - bulk_delete: 자손 season/episode cascade soft-delete
  - dedup_contents.py: content_type별 그룹 분리 + Content.parent_id 재지정
"""
import pytest
from unittest.mock import patch

from api.programming.metadata.models.content import (
    Content, ContentBatchJob, ContentType, ContentStatus,
)
from api.programming.metadata.service import process_batch_rows, bulk_delete
from scripts.dedup_contents import find_duplicate_groups, dedup_group

_CELERY_PATCH = "workers.tasks.metadata.process_content_metadata"


# ─── helpers ──────────────────────────────────────────────────────────────────

def _job(db, cp="CP") -> ContentBatchJob:
    job = ContentBatchJob(job_name="test-job", cp_name=cp, status="pending")
    db.add(job)
    db.flush()
    return job


def _content(db, title, ctype=ContentType.movie, cp="CP", year=2023, parent_id=None) -> Content:
    c = Content(title=title, content_type=ctype, cp_name=cp,
                production_year=year, status=ContentStatus.raw,
                parent_id=parent_id)
    db.add(c)
    db.flush()
    return c


# ─── process_batch_rows: content_type-aware dedup ────────────────────────────

def test_dedup_same_type_skips_duplicate(db):
    """동일 (title, year, cp, type) → 2번째 row는 skip, Content 1건만 생성."""
    job = _job(db)
    rows = [
        {"title": "무빙", "production_year": 2023, "content_type": "series"},
        {"title": "무빙", "production_year": 2023, "content_type": "series"},
    ]
    with patch(_CELERY_PATCH) as mock_task:
        mock_task.delay.return_value = None
        result = process_batch_rows(db, job, rows)
    count = db.query(Content).filter(Content.title == "무빙", Content.content_type == ContentType.series).count()
    assert count == 1
    assert result["skipped_duplicates"] == 1


def test_dedup_different_type_creates_both(db):
    """동명이지만 content_type 상이(movie vs series) → 각각 독립 Content 생성."""
    job = _job(db)
    rows = [
        {"title": "무빙", "production_year": 2023, "content_type": "movie"},
        {"title": "무빙", "production_year": 2023, "content_type": "series"},
    ]
    with patch(_CELERY_PATCH) as mock_task:
        mock_task.delay.return_value = None
        result = process_batch_rows(db, job, rows)
    movie_count  = db.query(Content).filter(Content.title == "무빙", Content.content_type == ContentType.movie).count()
    series_count = db.query(Content).filter(Content.title == "무빙", Content.content_type == ContentType.series).count()
    assert movie_count == 1
    assert series_count == 1
    assert result["skipped_duplicates"] == 0


def test_dedup_movie_default_type(db):
    """content_type 미지정 → 기본 movie. movie 중복은 skip."""
    job = _job(db)
    rows = [
        {"title": "무빙2"},
        {"title": "무빙2"},
    ]
    with patch(_CELERY_PATCH) as mock_task:
        mock_task.delay.return_value = None
        process_batch_rows(db, job, rows)
    count = db.query(Content).filter(Content.title == "무빙2").count()
    assert count == 1


# ─── bulk_delete: 자손 cascade ───────────────────────────────────────────────

@pytest.mark.anyio
async def test_bulk_delete_cascades_to_children(db):
    """series bulk_delete → 하위 season/episode is_deleted=True."""
    series  = _content(db, "시리즈A", ContentType.series)
    season  = _content(db, "시즌1",   ContentType.season,  parent_id=series.id)
    episode = _content(db, "에피1",   ContentType.episode, parent_id=season.id)

    await bulk_delete(db, [series.id])

    db.expire_all()
    assert db.query(Content).get(series.id).is_deleted is True
    assert db.query(Content).get(season.id).is_deleted is True
    assert db.query(Content).get(episode.id).is_deleted is True


@pytest.mark.anyio
async def test_bulk_delete_movie_no_cascade(db):
    """movie bulk_delete → 관련 없는 다른 Content 미영향."""
    movie   = _content(db, "영화A", ContentType.movie)
    movie2  = _content(db, "영화B", ContentType.movie)

    await bulk_delete(db, [movie.id])

    db.expire_all()
    assert db.query(Content).get(movie.id).is_deleted is True
    assert db.query(Content).get(movie2.id).is_deleted is False


@pytest.mark.anyio
async def test_bulk_delete_multiple_series(db):
    """복수 series 동시 삭제 → 각 계층 모두 cascade."""
    s1 = _content(db, "S1", ContentType.series)
    c1 = _content(db, "E1", ContentType.episode, parent_id=s1.id)
    s2 = _content(db, "S2", ContentType.series)
    c2 = _content(db, "E2", ContentType.episode, parent_id=s2.id)

    await bulk_delete(db, [s1.id, s2.id])

    db.expire_all()
    for cid in [s1.id, c1.id, s2.id, c2.id]:
        assert db.query(Content).get(cid).is_deleted is True


# ─── dedup_contents.py ────────────────────────────────────────────────────────

def test_find_duplicate_groups_separates_by_type(db):
    """동명 movie/series 는 별도 그룹. movie 그룹만 중복."""
    _content(db, "공통", ContentType.movie,  year=2020)
    _content(db, "공통", ContentType.movie,  year=2020)
    _content(db, "공통", ContentType.series, year=2020)

    groups = find_duplicate_groups(db)
    # movie 중복 그룹 1개, series는 단독이므로 그룹 없음
    assert len(groups) == 1
    assert groups[0]["content_type"] == ContentType.movie
    assert groups[0]["count"] == 2


def test_dedup_group_reassigns_parent_id(db):
    """중복 시리즈 제거 시 고아 자식 parent_id → canonical."""
    s1 = _content(db, "시리즈X", ContentType.series, year=2021)
    s2 = _content(db, "시리즈X", ContentType.series, year=2021)
    ep = _content(db, "에피", ContentType.episode, parent_id=s2.id)

    group = {
        "title": "시리즈X", "year": 2021, "cp": "CP",
        "content_type": ContentType.series,
        "count": 2,
        "contents": [s1, s2],
    }
    stats = dedup_group(db, group, dry_run=False)
    db.flush()

    db.expire_all()
    assert ep.parent_id == s1.id  # canonical(s1)로 재지정
    assert stats["children_reassigned"] == 1


def test_dedup_group_dry_run_no_change(db):
    """dry_run=True → DB 변경 없이 stats만 반환, 원본 2건 유지."""
    s1 = _content(db, "영화Y", ContentType.movie, year=2022)
    s2 = _content(db, "영화Y", ContentType.movie, year=2022)

    group = {
        "title": "영화Y", "year": 2022, "cp": "CP",
        "content_type": ContentType.movie,
        "count": 2,
        "contents": [s1, s2],
    }
    stats = dedup_group(db, group, dry_run=True)

    count = db.query(Content).filter(Content.title == "영화Y").count()
    assert count == 2
    assert stats["canonical_id"] == s1.id
