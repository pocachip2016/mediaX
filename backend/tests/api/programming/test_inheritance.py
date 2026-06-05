"""
inheritance.py read-time 상속 resolver 단위 테스트
"""
import pytest

from api.programming.metadata.inheritance import resolve_inherited_metadata
from api.programming.metadata.models.content import Content, ContentType, ContentMetadata
from api.programming.metadata.models.image import ContentImage, ImageType
from api.programming.metadata.models.person import PersonMaster, ContentCredit, CreditRole
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


def _add_credit(db, content_id, role, name_ko="홍길동"):
    p = PersonMaster(name_ko=name_ko)
    db.add(p); db.flush()
    db.add(ContentCredit(content_id=content_id, person_id=p.id, role=role, cast_order=1))
    db.flush()


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


# ── cast / director 상속 ─────────────────────────────────────────────────────

def test_season_inherits_cast_credits(db):
    """시즌에 actor 없고 부모 시리즈에 actor 있으면 cast_credits 상속."""
    series = _make_series(db)
    _add_credit(db, series.id, CreditRole.actor, "배우A")
    season = _make_season(db, series.id)

    result = resolve_inherited_metadata(season, db)
    assert result is not None
    assert "cast_credits" in result
    names = [c["name_ko"] for c in result["cast_credits"]]
    assert "배우A" in names


def test_season_inherits_director_credits(db):
    """시즌에 director 없고 부모 시리즈에 director 있으면 director_credits 상속."""
    series = _make_series(db)
    _add_credit(db, series.id, CreditRole.director, "감독A")
    season = _make_season(db, series.id)

    result = resolve_inherited_metadata(season, db)
    assert result is not None
    assert "director_credits" in result
    names = [c["name_ko"] for c in result["director_credits"]]
    assert "감독A" in names


def test_episode_inherits_cast_via_chain(db):
    """에피소드 → 시즌(크레딧 없음) → 시리즈(actor 있음) 체인 상속."""
    series = _make_series(db, year=2023, country="KR")
    _add_credit(db, series.id, CreditRole.actor, "배우B")
    season = _make_season(db, series.id)
    episode = _make_episode(db, season.id)

    result = resolve_inherited_metadata(episode, db)
    assert result is not None
    assert "cast_credits" in result


def test_no_cast_inherit_if_direct_credits_exist(db):
    """시즌에 직접 actor 있으면 cast_credits 상속 안 함."""
    series = _make_series(db)
    _add_credit(db, series.id, CreditRole.actor, "부모배우")
    season = _make_season(db, series.id)
    _add_credit(db, season.id, CreditRole.actor, "자식배우")  # direct credit

    result = resolve_inherited_metadata(season, db)
    # cast_credits 상속 없음 (직접 있으니까)
    assert result is None or "cast_credits" not in (result or {})


# ── apply_parent_inheritance — 스칼라 필드 DB 기록 ────────────────────────────

def test_apply_parent_inheritance_fills_scalar_fields(db):
    """시즌 빈 production_year/country가 부모값으로 DB 기록되고 title/synopsis는 불변."""
    from api.test.pipeline_auto_service import apply_parent_inheritance

    series = _make_series(db, year=2022, country="South Korea")
    _add_meta(db, series.id, synopsis="A" * 270)
    season = _make_season(db, series.id)  # year/country 비어있음
    _add_meta(db, season.id, synopsis="")  # synopsis 빈 채로

    filled = apply_parent_inheritance(db, season.id)
    db.refresh(season)

    assert set(filled) == {"production_year", "country"}
    assert season.production_year == 2022
    assert season.country == "South Korea"
    # title·synopsis 불변
    assert season.title == "무빙 시즌1"
    season_meta = db.query(ContentMetadata).filter_by(content_id=season.id).first()
    assert (season_meta.cp_synopsis or "") == ""


def test_apply_parent_inheritance_idempotent(db):
    """2회 호출 시 두 번째는 추가 변경 없음 (멱등)."""
    from api.test.pipeline_auto_service import apply_parent_inheritance

    series = _make_series(db, year=2022, country="South Korea")
    season = _make_season(db, series.id)

    first = apply_parent_inheritance(db, season.id)
    second = apply_parent_inheritance(db, season.id)
    assert set(first) == {"production_year", "country"}
    assert second == []


def test_apply_parent_inheritance_movie_noop(db):
    """movie는 무처리."""
    from api.test.pipeline_auto_service import apply_parent_inheritance
    movie = create_content(db, ContentCreate(title="M", content_type=ContentType.movie))
    assert apply_parent_inheritance(db, movie.id) == []


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
