"""
Gap Analyzer 단위 테스트

시나리오:
  1. 빈 콘텐츠 → 6개 갭 모두 보고
  2. 부분 데이터 (synopsis 충분) → synopsis 갭 제외
  3. 모든 필드 완비 → is_clean == True
"""

import pytest
from api.meta_core.gap import analyze_gap, analyze_gap_batch
from api.programming.metadata.models.content import Content, ContentMetadata, ContentType, ContentStatus
from api.programming.metadata.models.external import ExternalMetaSource, ExternalSourceType
from api.programming.metadata.models.image import ContentImage, ImageType
from api.programming.metadata.models.person import ContentCredit, CreditRole, PersonMaster
from api.programming.metadata.models.taxonomy import ContentGenre


def _make_person(db, name="홍길동") -> PersonMaster:
    p = PersonMaster(name_ko=name)
    db.add(p)
    db.flush()
    return p


def _make_content(db, title="테스트 영화") -> Content:
    c = Content(
        title=title,
        content_type=ContentType.movie,
        status=ContentStatus.staging,
    )
    db.add(c)
    db.flush()
    return c


# ─── 1. 빈 콘텐츠 — 모든 갭 ────────────────────────────────────────────────

def test_all_gaps_for_empty_content(db):
    c = _make_content(db)
    report = analyze_gap(c.id, db)

    assert not report.is_clean
    field_names = {g.field_name for g in report.missing_fields}
    assert field_names == {"external_id", "poster", "synopsis", "cast", "director", "primary_genre"}
    assert report.min_priority == 1  # external_id, poster 가 p1


def test_gap_reasons_for_empty_content(db):
    c = _make_content(db)
    report = analyze_gap(c.id, db)

    by_field = {g.field_name: g for g in report.missing_fields}
    assert by_field["external_id"].reason == "no_match"
    assert by_field["poster"].reason == "no_primary"
    assert by_field["synopsis"].reason == "empty"
    assert by_field["cast"].reason == "empty"
    assert by_field["director"].reason == "empty"
    assert by_field["primary_genre"].reason == "no_primary"


# ─── 2. 부분 데이터 ─────────────────────────────────────────────────────────

def test_synopsis_gap_cleared_when_long_enough(db):
    c = _make_content(db)
    meta = ContentMetadata(
        content_id=c.id,
        cp_synopsis="A" * 60,  # SYNOPSIS_MIN_LEN=50 초과
    )
    db.add(meta)
    db.flush()

    report = analyze_gap(c.id, db)
    field_names = {g.field_name for g in report.missing_fields}
    assert "synopsis" not in field_names


def test_synopsis_gap_reason_too_short(db):
    c = _make_content(db)
    meta = ContentMetadata(content_id=c.id, cp_synopsis="짧음")
    db.add(meta)
    db.flush()

    report = analyze_gap(c.id, db)
    by_field = {g.field_name: g for g in report.missing_fields}
    assert by_field["synopsis"].reason == "too_short"


def test_cast_gap_cleared_by_cp_cast(db):
    c = _make_content(db)
    meta = ContentMetadata(content_id=c.id, cp_cast=[{"name": "김철수", "role": "주연"}])
    db.add(meta)
    db.flush()

    report = analyze_gap(c.id, db)
    field_names = {g.field_name for g in report.missing_fields}
    assert "cast" not in field_names


def test_cast_gap_cleared_by_credit_record(db):
    c = _make_content(db)
    person = _make_person(db)
    credit = ContentCredit(content_id=c.id, person_id=person.id, role=CreditRole.actor)
    db.add(credit)
    db.flush()

    report = analyze_gap(c.id, db)
    field_names = {g.field_name for g in report.missing_fields}
    assert "cast" not in field_names


# ─── 3. 전체 필드 완비 — is_clean ───────────────────────────────────────────

def _populate_all_fields(db, c: Content):
    db.add(ExternalMetaSource(
        content_id=c.id,
        source_type=ExternalSourceType.tmdb,
        external_id="12345",
    ))
    db.add(ContentImage(
        content_id=c.id,
        image_type=ImageType.poster,
        url="http://example.com/poster.jpg",
        is_primary=True,
    ))
    db.add(ContentMetadata(
        content_id=c.id,
        cp_synopsis="A" * 60,
    ))
    actor = _make_person(db, "배우1")
    director = _make_person(db, "감독1")
    db.add(ContentCredit(content_id=c.id, person_id=actor.id, role=CreditRole.actor))
    db.add(ContentCredit(content_id=c.id, person_id=director.id, role=CreditRole.director))
    db.add(ContentGenre(content_id=c.id, genre_id=1, is_primary=True))
    db.flush()


def test_is_clean_when_all_fields_present(db):
    c = _make_content(db)
    _populate_all_fields(db, c)

    report = analyze_gap(c.id, db)
    assert report.is_clean
    assert report.missing_fields == []
    assert report.min_priority == 99


# ─── 4. analyze_gap_batch ────────────────────────────────────────────────────

def test_batch_returns_all_contents(db):
    for i in range(3):
        _make_content(db, title=f"영화{i}")
    db.commit()

    reports = analyze_gap_batch(db, limit=10)
    assert len(reports) == 3


def test_batch_filter_by_content_type(db):
    _make_content(db, title="영화A")
    series = Content(title="시리즈A", content_type=ContentType.series, status=ContentStatus.staging)
    db.add(series)
    db.commit()

    reports = analyze_gap_batch(db, content_type="movie", limit=10)
    assert all(r.content_type == "movie" for r in reports)


def test_content_not_found_raises(db):
    with pytest.raises(ValueError, match="not found"):
        analyze_gap(99999, db)


# ─── 5. 상속-aware (season/episode) ──────────────────────────────────────────

def _make_series_with_meta(db, synopsis="A" * 60, genre="드라마", poster_url="http://img/p.jpg"):
    from api.programming.metadata.models.image import ContentImage, ImageType
    series = Content(title="시리즈X", content_type=ContentType.series,
                     production_year=2023, country="KR", status=ContentStatus.staging)
    db.add(series); db.flush()
    meta = ContentMetadata(content_id=series.id, cp_synopsis=synopsis,
                           ai_genre_primary=genre, quality_score=0.0)
    db.add(meta)
    img = ContentImage(content_id=series.id, image_type=ImageType.poster,
                       url=poster_url, is_primary=True)
    db.add(img); db.flush()
    return series


def test_episode_gap_excludes_inheritable_fields(db):
    """에피소드가 시리즈 메타(시놉시스/장르/포스터)를 상속받을 수 있으면 해당 갭 미보고."""
    series = _make_series_with_meta(db)
    episode = Content(title="시리즈X E01", content_type=ContentType.episode,
                      parent_id=series.id, status=ContentStatus.staging)
    db.add(episode); db.flush()

    report = analyze_gap(episode.id, db)
    gap_names = {g.field_name for g in report.missing_fields}

    # 시리즈에서 상속 가능한 poster/synopsis/primary_genre 는 갭 아님
    assert "poster" not in gap_names
    assert "synopsis" not in gap_names
    assert "primary_genre" not in gap_names

    # external_id/cast/director 는 여전히 갭 (에피소드 고유 조회 필요)
    assert "external_id" in gap_names


def test_season_gap_excludes_inheritable_fields(db):
    """시즌도 동일하게 상속 가능 필드 갭 제외."""
    series = _make_series_with_meta(db)
    season = Content(title="시리즈X 시즌1", content_type=ContentType.season,
                     parent_id=series.id, status=ContentStatus.staging)
    db.add(season); db.flush()

    report = analyze_gap(season.id, db)
    gap_names = {g.field_name for g in report.missing_fields}
    assert "poster" not in gap_names
    assert "synopsis" not in gap_names
    assert "primary_genre" not in gap_names


def test_movie_gap_unaffected_by_inheritance(db):
    """movie 는 상속 로직 무관 — 기존 갭 그대로 보고."""
    movie = _make_content(db, title="독립영화")
    report = analyze_gap(movie.id, db)
    gap_names = {g.field_name for g in report.missing_fields}
    # movie 는 poster/synopsis 등 모두 갭으로 보고
    assert "poster" in gap_names
    assert "synopsis" in gap_names


def test_orphan_episode_still_reports_all_gaps(db):
    """parent 없는 고아 episode 는 상속 불가 → 갭 그대로 보고."""
    episode = Content(title="고아 에피소드", content_type=ContentType.episode,
                      parent_id=None, status=ContentStatus.staging)
    db.add(episode); db.flush()

    report = analyze_gap(episode.id, db)
    gap_names = {g.field_name for g in report.missing_fields}
    assert "poster" in gap_names
    assert "synopsis" in gap_names
