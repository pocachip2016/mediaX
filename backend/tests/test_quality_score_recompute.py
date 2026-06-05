"""
recompute_quality_score (완성도 기반 quality_score 재계산) 회귀 가드.

대상: api.programming.metadata.ai_engine.recompute_quality_score
배점(합 100): synopsis 22(길이 tier) / genre 14 / cast 12 / director 12 /
              country 10 / production_year 10 / runtime 10 / title 10

외부 API/LLM 호출이 전혀 없는 순수 함수 → mock 불필요, in-memory SQLite(db 픽스처)만 사용.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.programming.metadata.models.content import (
    Content, ContentMetadata, ContentType, ContentStatus,
)
from api.programming.metadata.models.person import PersonMaster, ContentCredit, CreditRole
from api.programming.metadata.models.taxonomy import GenreCode, ContentGenre
from api.programming.metadata.ai_engine import recompute_quality_score


# ── helpers ───────────────────────────────────────────────────────────────────

def _content(db, *, country=None, production_year=None, runtime_minutes=None, meta=None):
    c = Content(
        title="테스트 영화",
        content_type=ContentType.movie,
        cp_name="TEST_GUARD",
        status=ContentStatus.ai,
        country=country,
        production_year=production_year,
        runtime_minutes=runtime_minutes,
    )
    db.add(c)
    db.flush()
    if meta is not None:
        db.add(ContentMetadata(content_id=c.id, **meta))
        db.flush()
    return c


def _add_credit(db, content_id, role):
    p = PersonMaster(name_ko="홍길동")
    db.add(p)
    db.flush()
    db.add(ContentCredit(content_id=content_id, person_id=p.id, role=role))
    db.flush()


def _add_genre(db, content_id):
    g = GenreCode(code="ACT", name_ko="액션")
    db.add(g)
    db.flush()
    db.add(ContentGenre(content_id=content_id, genre_id=g.id, is_primary=True))
    db.flush()


# ── tests ─────────────────────────────────────────────────────────────────────

def test_missing_content_returns_none(db):
    assert recompute_quality_score(db, 999999) is None


def test_title_only(db):
    c = _content(db)  # meta 없음 → title만
    assert recompute_quality_score(db, c.id) == 10.0


def test_meta_created_when_absent(db):
    """ContentMetadata 없던 콘텐츠도 생성 후 quality_score 기록."""
    c = _content(db)
    assert c.metadata_record is None
    score = recompute_quality_score(db, c.id)
    db.refresh(c)
    assert c.metadata_record is not None
    assert c.metadata_record.quality_score == score == 10.0


def test_title_synopsis_genre(db):
    c = _content(db, meta={"ai_synopsis": "줄" * 200, "ai_genre_primary": "드라마"})
    # title 10 + synopsis(>=200) 22 + genre 14
    assert recompute_quality_score(db, c.id) == 46.0


def test_genre_via_relationship(db):
    """meta 장르 문자열이 없어도 ContentGenre 관계가 있으면 genre 점수 반영."""
    c = _content(db, meta={"ai_synopsis": "줄" * 200})
    _add_genre(db, c.id)
    # title 10 + synopsis 22 + genre(관계) 14
    assert recompute_quality_score(db, c.id) == 46.0


def test_cast_and_director(db):
    c = _content(db, meta={"ai_synopsis": "줄" * 200, "ai_genre_primary": "드라마"})
    _add_credit(db, c.id, CreditRole.actor)
    _add_credit(db, c.id, CreditRole.director)
    # 46 + cast 12 + director 12
    assert recompute_quality_score(db, c.id) == 70.0


def test_full_metadata_is_100(db):
    c = _content(
        db, country="한국", production_year=2015, runtime_minutes=123,
        meta={"ai_synopsis": "줄" * 200, "ai_genre_primary": "드라마"},
    )
    _add_credit(db, c.id, CreditRole.actor)
    _add_credit(db, c.id, CreditRole.director)
    # 10+22+14+12+12 + country 10 + year 10 + runtime 10 = 100
    assert recompute_quality_score(db, c.id) == 100.0


def test_synopsis_length_tiers(db):
    cases = [(200, 22), (199, 16), (100, 16), (99, 8), (50, 8), (49, 4), (1, 4), (0, 0)]
    for length, syn_pts in cases:
        c = _content(db, meta={"ai_synopsis": "줄" * length})
        # title 10 + synopsis tier
        assert recompute_quality_score(db, c.id) == 10.0 + syn_pts, f"len={length}"


def test_no_external_mapping_component(db):
    """외부 매핑(TMDB/KOBIS/KMDB) 유무는 점수에 영향 없음 — 완성도 기준."""
    c = _content(db, country="한국", production_year=2015, runtime_minutes=123,
                 meta={"ai_synopsis": "줄" * 200, "ai_genre_primary": "드라마"})
    _add_credit(db, c.id, CreditRole.actor)
    _add_credit(db, c.id, CreditRole.director)
    # 외부 소스를 만들지 않아도 모든 기본 필드가 차 있으면 100 → 매핑 비의존 확인
    assert recompute_quality_score(db, c.id) == 100.0


# ── 상속 채점 (season/episode) ─────────────────────────────────────────────────

def _episode_with_parent_credits(db):
    """credits 없는 에피소드 + 시리즈에 actor/director 크레딧 — 상속 채점 테스트용."""
    from api.programming.metadata.models.content import ContentStatus
    series = Content(
        title="부모 시리즈", content_type=ContentType.series,
        cp_name="TEST_GUARD", status=ContentStatus.ai,
        country="한국", production_year=2023,
    )
    db.add(series); db.flush()
    _add_credit(db, series.id, CreditRole.actor)
    _add_credit(db, series.id, CreditRole.director)

    season = Content(
        title="시즌1", content_type=ContentType.season,
        cp_name="TEST_GUARD", status=ContentStatus.ai,
        parent_id=series.id,
    )
    db.add(season); db.flush()

    episode = Content(
        title="에피소드1", content_type=ContentType.episode,
        cp_name="TEST_GUARD", status=ContentStatus.ai,
        parent_id=season.id,
        country="한국", production_year=2023, runtime_minutes=45,
    )
    db.add(episode); db.flush()
    db.add(ContentMetadata(
        content_id=episode.id, quality_score=0.0,
        ai_synopsis="줄" * 200, ai_genre_primary="드라마",
    ))
    db.flush()
    return episode


def test_episode_inherits_cast_director_for_quality_score(db):
    """직접 크레딧 없는 에피소드가 부모 시리즈 크레딧을 상속해 임계값(90) 이상 달성."""
    ep = _episode_with_parent_credits(db)
    # title 10 + synopsis 22 + genre 14 + country 10 + year 10 + runtime 10
    # + cast(상속) 12 + director(상속) 12 = 100
    score = recompute_quality_score(db, ep.id)
    assert score is not None
    assert score >= 90.0


def test_episode_without_any_credits_below_threshold(db):
    """부모에도 크레딧 없으면 상속 없음 → 점수 < 90."""
    from api.programming.metadata.models.content import ContentStatus
    series = Content(
        title="빈 시리즈", content_type=ContentType.series,
        cp_name="TEST_GUARD", status=ContentStatus.ai,
    )
    db.add(series); db.flush()
    episode = Content(
        title="에피소드", content_type=ContentType.episode,
        cp_name="TEST_GUARD", status=ContentStatus.ai,
        parent_id=series.id,
        country="한국", production_year=2023, runtime_minutes=45,
    )
    db.add(episode); db.flush()
    db.add(ContentMetadata(
        content_id=episode.id, quality_score=0.0,
        ai_synopsis="줄" * 200, ai_genre_primary="드라마",
    ))
    db.flush()
    # 크레딧 없음 → cast 0 + director 0 → 76점
    score = recompute_quality_score(db, episode.id)
    assert score is not None
    assert score < 90.0
