"""
inheritance.py read-time 상속 resolver 단위 테스트
"""
import pytest

from api.programming.metadata.inheritance import resolve_inherited_metadata
from api.programming.metadata.models.content import Content, ContentType, ContentMetadata
from api.programming.metadata.models.image import ContentImage, ImageType
from api.programming.metadata.models.taxonomy import ContentGenre
from api.programming.metadata.schemas import ContentCreate
from api.programming.metadata.service import create_content, get_content_hierarchy


# ── fixtures ──────────────────────────────────────────────────────────────────

def _make_series(db, title="무빙", year=2023, country="KR") -> Content:
    s = Content(title=title, content_type=ContentType.series,
                production_year=year, country=country)
    db.add(s); db.flush()
    return s


def _make_season(db, series_id, num=1) -> Content:
    s = Content(title="무빙 시즌1", content_type=ContentType.season,
                parent_id=series_id, season_number=num)
    db.add(s); db.flush()
    return s


def _make_episode(db, season_id, num=1) -> Content:
    e = Content(title="무빙 E01", content_type=ContentType.episode,
                parent_id=season_id, episode_number=num)
    db.add(e); db.flush()
    return e


def _add_meta(db, content_id, synopsis="", genre=None):
    m = ContentMetadata(content_id=content_id, quality_score=0.0,
                        cp_synopsis=synopsis, ai_genre_primary=genre)
    db.add(m); db.flush()
    return m


def _add_poster(db, content_id, url="http://img/p.jpg"):
    img = ContentImage(content_id=content_id, image_type=ImageType.poster,
                       url=url, is_primary=True)
    db.add(img); db.flush()


# ── movie/series → None ───────────────────────────────────────────────────────

def test_movie_returns_none(db):
    movie = create_content(db, ContentCreate(title="M", content_type=ContentType.movie))
    assert resolve_inherited_metadata(movie, db) is None


def test_series_returns_none(db):
    series = _make_series(db)
    assert resolve_inherited_metadata(series, db) is None


# ── season inherits from series ───────────────────────────────────────────────

def test_season_inherits_production_year(db):
    series = _make_series(db, year=2023)
    season = _make_season(db, series.id)  # season has no year

    result = resolve_inherited_metadata(season, db)
    assert result is not None
    assert result.get("production_year") == 2023
    assert result.get("_source_id") == series.id


def test_season_inherits_country(db):
    series = _make_series(db, country="KR")
    season = _make_season(db, series.id)

    result = resolve_inherited_metadata(season, db)
    assert result is not None
    assert result.get("country") == "KR"


def test_season_inherits_synopsis_from_series_meta(db):
    series = _make_series(db)
    _add_meta(db, series.id, synopsis="A" * 60)
    season = _make_season(db, series.id)
    _add_meta(db, season.id, synopsis="")  # empty

    result = resolve_inherited_metadata(season, db)
    assert result is not None
    assert "synopsis" in result
    assert len(result["synopsis"]) >= 50


def test_season_inherits_poster_url(db):
    series = _make_series(db)
    _add_poster(db, series.id, url="http://img/series_poster.jpg")
    season = _make_season(db, series.id)  # no poster

    result = resolve_inherited_metadata(season, db)
    assert result is not None
    assert result.get("poster_url") == "http://img/series_poster.jpg"


def test_season_inherits_genre(db):
    series = _make_series(db)
    _add_meta(db, series.id, genre="액션")
    season = _make_season(db, series.id)
    _add_meta(db, season.id)  # no genre

    result = resolve_inherited_metadata(season, db)
    assert result is not None
    assert result.get("primary_genre") == "액션"


# ── episode inherits through season → series ─────────────────────────────────

def test_episode_inherits_via_chain(db):
    series = _make_series(db, year=2023, country="KR")
    _add_poster(db, series.id)
    season = _make_season(db, series.id)
    episode = _make_episode(db, season.id)

    result = resolve_inherited_metadata(episode, db)
    assert result is not None
    assert result.get("production_year") == 2023
    assert result.get("country") == "KR"
    assert result.get("poster_url") is not None


# ── season already populated → None or no re-inherit ─────────────────────────

def test_no_inherit_if_season_is_complete(db):
    series = _make_series(db, year=2023, country="KR")
    _add_meta(db, series.id, synopsis="A" * 60, genre="드라마")
    _add_poster(db, series.id)

    season = _make_season(db, series.id)
    season.production_year = 2023
    season.country = "KR"
    db.flush()
    _add_meta(db, season.id, synopsis="B" * 60, genre="액션")
    _add_poster(db, season.id)

    # season 이 모두 채워져 있으면 inherit 불필요
    result = resolve_inherited_metadata(season, db)
    assert result is None


# ── hierarchy endpoint includes inherited_meta ────────────────────────────────

def test_get_content_hierarchy_includes_inherited_meta(db):
    series = _make_series(db, year=2023, country="KR")
    _add_meta(db, series.id, synopsis="A" * 60)
    _add_poster(db, series.id)
    season = _make_season(db, series.id)

    staging = get_content_hierarchy(db, series.id)
    assert staging is not None
    assert len(staging.children) == 1

    season_item = staging.children[0]
    assert season_item.inherited_meta is not None
    assert season_item.inherited_meta.get("production_year") == 2023
