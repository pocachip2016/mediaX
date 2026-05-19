"""
content_kind 헬퍼 단위 테스트 — TV_TYPES, is_tv_type, tmdb_search_kind, external_lookup_target
"""
import pytest

from api.programming.metadata.content_kind import (
    TV_TYPES,
    is_tv_type,
    tmdb_search_kind,
    external_lookup_target,
)
from api.programming.metadata.models.content import Content, ContentType
from api.programming.metadata.schemas import ContentCreate
from api.programming.metadata.service import create_content


# ── TV_TYPES 집합 ─────────────────────────────────────────────────────────────

def test_tv_types_members():
    assert ContentType.series in TV_TYPES
    assert ContentType.season in TV_TYPES
    assert ContentType.episode in TV_TYPES
    assert ContentType.movie not in TV_TYPES


# ── is_tv_type ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("ct, expected", [
    (ContentType.movie,   False),
    (ContentType.series,  True),
    (ContentType.season,  True),
    (ContentType.episode, True),
    ("movie",             False),
    ("series",            True),
    ("season",            True),
    ("episode",           True),
    ("unknown",           False),
])
def test_is_tv_type_enum_and_str(ct, expected):
    assert is_tv_type(ct) == expected


def test_is_tv_type_content_object(db):
    series = create_content(db, ContentCreate(title="S", content_type=ContentType.series))
    movie  = create_content(db, ContentCreate(title="M", content_type=ContentType.movie))
    assert is_tv_type(series) is True
    assert is_tv_type(movie) is False


# ── tmdb_search_kind ──────────────────────────────────────────────────────────

def test_tmdb_search_kind(db):
    movie   = create_content(db, ContentCreate(title="M", content_type=ContentType.movie))
    series  = create_content(db, ContentCreate(title="S", content_type=ContentType.series))
    season  = create_content(db, ContentCreate(title="Sn", content_type=ContentType.season))
    episode = create_content(db, ContentCreate(title="E",  content_type=ContentType.episode))

    assert tmdb_search_kind(movie)   == "movie"
    assert tmdb_search_kind(series)  == "tv"
    assert tmdb_search_kind(season)  == "tv"
    assert tmdb_search_kind(episode) == "tv"


# ── external_lookup_target ────────────────────────────────────────────────────

def test_lookup_target_movie_returns_self(db):
    movie = create_content(db, ContentCreate(title="M", content_type=ContentType.movie))
    assert external_lookup_target(movie, db).id == movie.id


def test_lookup_target_series_returns_self(db):
    series = create_content(db, ContentCreate(title="S", content_type=ContentType.series))
    assert external_lookup_target(series, db).id == series.id


def test_lookup_target_season_returns_series(db):
    series = create_content(db, ContentCreate(title="S", content_type=ContentType.series))
    season = Content(title="Sn", content_type=ContentType.season, parent_id=series.id)
    db.add(season)
    db.commit()
    db.refresh(season)

    result = external_lookup_target(season, db)
    assert result.id == series.id
    assert result.content_type == ContentType.series


def test_lookup_target_episode_returns_series(db):
    series = create_content(db, ContentCreate(title="S", content_type=ContentType.series))
    season = Content(title="Sn", content_type=ContentType.season, parent_id=series.id)
    db.add(season)
    db.commit()
    db.refresh(season)

    episode = Content(title="E", content_type=ContentType.episode, parent_id=season.id)
    db.add(episode)
    db.commit()
    db.refresh(episode)

    result = external_lookup_target(episode, db)
    assert result.id == series.id


def test_lookup_target_orphan_episode_returns_self(db):
    episode = Content(title="E", content_type=ContentType.episode, parent_id=None)
    db.add(episode)
    db.commit()
    db.refresh(episode)

    result = external_lookup_target(episode, db)
    assert result.id == episode.id


def test_lookup_target_season_without_series_parent_returns_self(db):
    """season 의 parent 가 없는(고아) 경우 season 자신을 반환."""
    season = Content(title="Sn", content_type=ContentType.season, parent_id=None)
    db.add(season)
    db.commit()
    db.refresh(season)

    result = external_lookup_target(season, db)
    assert result.id == season.id
