"""
mh-write-guards 단위 테스트

Step 7 검증:
  - create_content: season/episode는 parent_id 필수
  - update_content: children 존재 시 content_type 변경 금지 가드
"""
import pytest
from types import SimpleNamespace

from api.programming.metadata.models.content import (
    Content, ContentType, ContentStatus,
)
from api.programming.metadata.schemas import ContentCreate, ContentUpdate
from api.programming.metadata.service import create_content, update_content


def _content(db, title, ctype=ContentType.movie, year=2023, parent_id=None) -> Content:
    c = Content(title=title, content_type=ctype, production_year=year,
                status=ContentStatus.raw, parent_id=parent_id)
    db.add(c)
    db.flush()
    return c


# ─── create_content: parent_id 필수 검증 ──────────────────────────────────────

def test_create_season_without_parent_id_raises(db):
    """season 생성 시 parent_id 없으면 ValueError."""
    data = ContentCreate(title="시즌1", content_type="season")
    with pytest.raises(ValueError, match="parent_id required"):
        create_content(db, data)


def test_create_episode_without_parent_id_raises(db):
    """episode 생성 시 parent_id 없으면 ValueError."""
    data = ContentCreate(title="에피1", content_type="episode")
    with pytest.raises(ValueError, match="parent_id required"):
        create_content(db, data)


def test_create_movie_without_parent_id_succeeds(db):
    """movie는 parent_id 없어도 OK."""
    data = ContentCreate(title="영화A", content_type="movie")
    content = create_content(db, data)
    assert content.content_type == ContentType.movie
    assert content.parent_id is None


def test_create_series_without_parent_id_succeeds(db):
    """series는 parent_id 없어도 OK."""
    data = ContentCreate(title="시리즈A", content_type="series")
    content = create_content(db, data)
    assert content.content_type == ContentType.series
    assert content.parent_id is None


def test_create_season_with_parent_id_succeeds(db):
    """season + parent_id → OK."""
    series = _content(db, "시리즈", ContentType.series)
    data = ContentCreate(title="시즌1", content_type="season", parent_id=series.id)
    content = create_content(db, data)
    assert content.parent_id == series.id


# ─── update_content: content_type 변경 가드 ────────────────────────────────────

def test_update_with_children_guard_blocks_change(db):
    """가드: children 있으면 content_type 변경 불가."""
    series = _content(db, "시리즈", ContentType.series)
    season = _content(db, "시즌1", ContentType.season, parent_id=series.id)

    data = SimpleNamespace(
        title=None, synopsis=None, cast=None, directors=None, genres=None,
        country=None, runtime=None, rating_age=None, poster_url=None,
        production_year=None, content_type="movie"
    )

    with pytest.raises(ValueError, match="Cannot change content_type.*children exist"):
        update_content(db, series.id, data)


def test_update_without_children_succeeds(db):
    """자식 없으면 다른 필드 수정 OK."""
    movie = _content(db, "영화", ContentType.movie)

    data = ContentUpdate(title="영화 수정됨")
    result = update_content(db, movie.id, data)
    assert result.id == movie.id


def test_update_series_with_children_other_fields_ok(db):
    """series에 children 있어도 다른 필드 수정 OK."""
    series = _content(db, "시리즈", ContentType.series)
    season = _content(db, "시즌1", ContentType.season, parent_id=series.id)

    data = ContentUpdate(synopsis="새 시놉시스")
    result = update_content(db, series.id, data)
    assert result.id == series.id
