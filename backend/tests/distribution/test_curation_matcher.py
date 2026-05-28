"""
dev-curation-workbench Step 3 — curation_matcher 유닛 테스트
"""
from unittest.mock import MagicMock

import pytest

from api.distribution.curation_matcher import (
    _era_score,
    _external_score,
    _genre_score,
    _keyword_score,
    _mood_score,
    _runtime_score,
    match_contents,
    score_content,
)
from api.distribution.ott.base import OttItem, OttSection
from api.programming.metadata.models.content import Content, ContentType
from api.programming.metadata.models.taxonomy import ContentGenre, GenreCode


# ── 개별 스코어 함수 ──────────────────────────────────────────────────────────

class TestGenreScore:
    def test_no_target_genres_returns_max(self):
        assert _genre_score([], None, None, []) == 1.0

    def test_exact_match(self):
        score = _genre_score(["코미디"], "코미디", None, ["코미디"])
        assert score > 0.0

    def test_no_match_returns_zero(self):
        assert _genre_score([], None, None, ["코미디"]) == 0.0

    def test_multiple_match_bonus(self):
        s1 = _genre_score(["코미디"], None, None, ["코미디"])
        s2 = _genre_score(["코미디", "드라마"], None, None, ["코미디", "드라마"])
        assert s2 >= s1

    def test_case_insensitive(self):
        assert _genre_score(["Comedy"], None, None, ["comedy"]) > 0.0


class TestMoodScore:
    def test_no_target_returns_max(self):
        assert _mood_score(["가벼운"], []) == 1.0

    def test_no_content_tags_returns_zero(self):
        assert _mood_score(None, ["가벼운"]) == 0.0

    def test_match(self):
        assert _mood_score(["가벼운", "따뜻한"], ["가벼운"]) == 1.0

    def test_partial_match(self):
        s = _mood_score(["가벼운"], ["가벼운", "따뜻한"])
        assert 0.0 < s < 1.0


class TestRuntimeScore:
    def test_no_constraints_returns_max(self):
        assert _runtime_score(90, None, None) == 1.0

    def test_no_runtime_returns_neutral(self):
        assert _runtime_score(None, 80, 120) == 0.5

    def test_in_range(self):
        assert _runtime_score(90, 80, 120) == 1.0

    def test_out_of_range_penalized(self):
        s = _runtime_score(60, 80, 120)
        assert 0.0 <= s < 1.0


class TestEraScore:
    def test_no_constraints_returns_max(self):
        assert _era_score(2005, None, None) == 1.0

    def test_no_year_returns_neutral(self):
        assert _era_score(None, 2000, 2020) == 0.5

    def test_in_range(self):
        assert _era_score(2010, 2000, 2020) == 1.0

    def test_out_of_range(self):
        assert _era_score(1990, 2000, 2020) == 0.0


class TestExternalScore:
    def test_no_external_titles_returns_zero(self):
        assert _external_score("기생충", set()) == 0.0

    def test_title_in_set(self):
        assert _external_score("기생충", {"기생충"}) == 1.0

    def test_case_insensitive(self):
        assert _external_score("기생충", {"기생충"}) == 1.0

    def test_not_in_set(self):
        assert _external_score("버닝", {"기생충"}) == 0.0


class TestKeywordScore:
    def test_no_keywords_returns_max(self):
        assert _keyword_score("기생충", "가족 이야기", []) == 1.0

    def test_keyword_in_title(self):
        assert _keyword_score("퇴근 후 이야기", None, ["퇴근"]) == 1.0

    def test_keyword_in_synopsis(self):
        assert _keyword_score("제목", "위로가 되는 이야기", ["위로"]) == 1.0

    def test_no_match(self):
        assert _keyword_score("제목", None, ["존재하지않는단어xyz"]) == 0.0


# ── score_content 통합 ────────────────────────────────────────────────────────

@pytest.fixture
def simple_content():
    c = Content(
        id=1,
        title="기생충",
        content_type=ContentType.movie,
        production_year=2019,
        runtime_minutes=132,
        is_deleted=False,
    )
    return c


@pytest.fixture
def simple_metadata():
    m = MagicMock()
    m.ai_genre_primary = "드라마"
    m.ai_genre_secondary = "스릴러"
    m.ai_mood_tags = ["긴장감", "어두운"]
    m.ai_synopsis = "계층 사회를 파헤치는 가족 이야기"
    return m


def test_score_content_returns_normalized(simple_content, simple_metadata):
    total, breakdown = score_content(
        content=simple_content,
        metadata=simple_metadata,
        genre_names=["드라마"],
        theme_features={"genres": ["드라마"], "moods": ["긴장감"]},
        external_titles=set(),
    )
    assert 0.0 <= total <= 1.0
    assert "genre" in breakdown
    assert "mood" in breakdown
    assert "runtime" in breakdown
    assert "era" in breakdown
    assert "external" in breakdown
    assert "keywords" in breakdown


def test_score_content_external_bonus(simple_content, simple_metadata):
    score_without, _ = score_content(
        content=simple_content,
        metadata=simple_metadata,
        genre_names=[],
        theme_features={},
        external_titles=set(),
    )
    score_with, _ = score_content(
        content=simple_content,
        metadata=simple_metadata,
        genre_names=[],
        theme_features={},
        external_titles={"기생충"},
    )
    assert score_with > score_without


def test_score_content_no_metadata(simple_content):
    total, breakdown = score_content(
        content=simple_content,
        metadata=None,
        genre_names=[],
        theme_features={"genres": ["드라마"]},
        external_titles=set(),
    )
    assert 0.0 <= total <= 1.0


# ── match_contents DB 통합 ────────────────────────────────────────────────────

def test_match_contents_empty_db(db):
    results = match_contents(db, {})
    assert results == []


def test_match_contents_returns_sorted(db):
    # 두 콘텐츠 삽입 — 장르 일치 콘텐츠가 더 높은 점수
    c1 = Content(
        title="기생충",
        content_type=ContentType.movie,
        production_year=2019,
        runtime_minutes=132,
        is_deleted=False,
    )
    c2 = Content(
        title="버닝",
        content_type=ContentType.movie,
        production_year=2018,
        runtime_minutes=148,
        is_deleted=False,
    )
    db.add_all([c1, c2])
    db.commit()

    results = match_contents(db, {}, limit=10)
    assert len(results) == 2
    # 점수 내림차순 정렬
    assert results[0].score >= results[1].score


def test_match_contents_limit(db):
    for i in range(5):
        db.add(Content(
            title=f"영화{i}",
            content_type=ContentType.movie,
            is_deleted=False,
        ))
    db.commit()

    results = match_contents(db, {}, limit=3)
    assert len(results) == 3


def test_match_contents_skips_deleted(db):
    db.add(Content(
        title="삭제된영화",
        content_type=ContentType.movie,
        is_deleted=True,
    ))
    db.add(Content(
        title="활성영화",
        content_type=ContentType.movie,
        is_deleted=False,
    ))
    db.commit()

    results = match_contents(db, {})
    assert len(results) == 1
    assert results[0].title == "활성영화"


def test_match_contents_era_filter(db):
    db.add(Content(title="구작", content_type=ContentType.movie, production_year=1990, is_deleted=False))
    db.add(Content(title="신작", content_type=ContentType.movie, production_year=2020, is_deleted=False))
    db.commit()

    results = match_contents(db, {"era_from": 2000, "era_to": 2026}, limit=10)
    assert len(results) == 2
    # 신작이 더 높은 era_score → 더 앞에 위치
    titles = [r.title for r in results]
    assert titles[0] == "신작"


def test_match_contents_external_titles_bonus(db):
    db.add(Content(title="기생충", content_type=ContentType.movie, is_deleted=False))
    db.add(Content(title="버닝",   content_type=ContentType.movie, is_deleted=False))
    db.commit()

    results = match_contents(db, {}, external_titles={"기생충"}, limit=10)
    titles = [r.title for r in results]
    assert titles[0] == "기생충"
