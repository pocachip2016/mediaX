"""Tier 0 rule_engine 단위 테스트 — SQLite in-memory."""
import pytest

from api.programming.metadata.models.content import (
    Content, ContentStatus, ContentType,
)
from api.programming.metadata.models.taxonomy import (
    ContentGenre, ContentTag, GenreCode, TagCode, TagType,
)
from api.programming.scheduling.rule_engine import RuleResult, apply_rule_query
from api.programming.scheduling.models import NodeKind
from api.programming.scheduling.node_service import compute_members, create_node


# ── 픽스처 헬퍼 ───────────────────────────────────────────────────────────────

def _content(db, title="콘텐츠", content_type=ContentType.movie,
             production_year=2024, country="한국",
             status=ContentStatus.approved):
    c = Content(
        title=title,
        content_type=content_type,
        production_year=production_year,
        country=country,
        status=status,
        cp_name="TEST",
    )
    db.add(c)
    db.flush()
    return c


def _genre_code(db, code="ACT", name_ko="액션"):
    gc = GenreCode(code=code, name_ko=name_ko)
    db.add(gc)
    db.flush()
    return gc


def _tag_code(db, name="힐링", tag_type=TagType.mood):
    tc = TagCode(tag_type=tag_type, name=name)
    db.add(tc)
    db.flush()
    return tc


def _link_genre(db, content_id, genre_id):
    cg = ContentGenre(content_id=content_id, genre_id=genre_id)
    db.add(cg)
    db.flush()


def _link_tag(db, content_id, tag_id):
    ct = ContentTag(content_id=content_id, tag_id=tag_id)
    db.add(ct)
    db.flush()


# ── 빈 query ──────────────────────────────────────────────────────────────────

def test_empty_query_returns_all(db):
    _content(db, "A")
    _content(db, "B")
    results = apply_rule_query(db, {})
    assert len(results) == 2
    assert all(isinstance(r, RuleResult) for r in results)
    assert all(r.reason == "rule:all" for r in results)


# ── genre 필터 ────────────────────────────────────────────────────────────────

def test_genre_filter_single(db):
    act = _genre_code(db, "ACT")
    drm = _genre_code(db, "DRM")
    c1 = _content(db, "액션A")
    c2 = _content(db, "드라마B")
    _link_genre(db, c1.id, act.id)
    _link_genre(db, c2.id, drm.id)

    results = apply_rule_query(db, {"genre": "ACT"})
    ids = [r.content_id for r in results]
    assert c1.id in ids
    assert c2.id not in ids


def test_genre_filter_list(db):
    act = _genre_code(db, "ACT")
    drm = _genre_code(db, "DRM")
    rom = _genre_code(db, "ROM")
    c1 = _content(db, "액션")
    c2 = _content(db, "드라마")
    c3 = _content(db, "다큐")
    _link_genre(db, c1.id, act.id)
    _link_genre(db, c2.id, drm.id)
    # c3는 장르 없음

    results = apply_rule_query(db, {"genre": ["ACT", "DRM"]})
    ids = {r.content_id for r in results}
    assert c1.id in ids
    assert c2.id in ids
    assert c3.id not in ids


def test_genre_reason_contains_code(db):
    act = _genre_code(db, "ACT")
    c = _content(db)
    _link_genre(db, c.id, act.id)
    results = apply_rule_query(db, {"genre": "ACT"})
    assert len(results) == 1
    assert "ACT" in results[0].reason


# ── year 필터 ─────────────────────────────────────────────────────────────────

def test_year_gte_filter(db):
    c_old = _content(db, "구작", production_year=2010)
    c_new = _content(db, "신작", production_year=2023)
    results = apply_rule_query(db, {"year_gte": 2020})
    ids = {r.content_id for r in results}
    assert c_new.id in ids
    assert c_old.id not in ids


def test_year_lte_filter(db):
    c_old = _content(db, "구작", production_year=2010)
    c_new = _content(db, "신작", production_year=2023)
    results = apply_rule_query(db, {"year_lte": 2015})
    ids = {r.content_id for r in results}
    assert c_old.id in ids
    assert c_new.id not in ids


def test_year_range_filter(db):
    c1 = _content(db, "2015작", production_year=2015)
    c2 = _content(db, "2020작", production_year=2020)
    c3 = _content(db, "2023작", production_year=2023)
    results = apply_rule_query(db, {"year_gte": 2016, "year_lte": 2021})
    ids = {r.content_id for r in results}
    assert c2.id in ids
    assert c1.id not in ids
    assert c3.id not in ids


# ── country 필터 ──────────────────────────────────────────────────────────────

def test_country_filter(db):
    c_kr = _content(db, "한국영화", country="한국")
    c_us = _content(db, "미국영화", country="미국")
    results = apply_rule_query(db, {"country": "한국"})
    ids = {r.content_id for r in results}
    assert c_kr.id in ids
    assert c_us.id not in ids


def test_country_partial_match(db):
    c = _content(db, "미국영화", country="미국/캐나다")
    results = apply_rule_query(db, {"country": "미국"})
    assert any(r.content_id == c.id for r in results)


# ── content_type 필터 ─────────────────────────────────────────────────────────

def test_content_type_filter(db):
    c_movie = _content(db, "영화", content_type=ContentType.movie)
    c_series = _content(db, "시리즈", content_type=ContentType.series)
    results = apply_rule_query(db, {"content_type": "movie"})
    ids = {r.content_id for r in results}
    assert c_movie.id in ids
    assert c_series.id not in ids


def test_content_type_unknown_ignored(db):
    _content(db, "영화")
    results = apply_rule_query(db, {"content_type": "unknown_type"})
    assert len(results) >= 1  # 알 수 없는 타입은 무시 → 전체 반환


# ── tags 필터 ─────────────────────────────────────────────────────────────────

def test_tags_filter_single(db):
    tc = _tag_code(db, "힐링")
    c1 = _content(db, "힐링드라마")
    c2 = _content(db, "일반영화")
    _link_tag(db, c1.id, tc.id)
    results = apply_rule_query(db, {"tags": "힐링"})
    ids = {r.content_id for r in results}
    assert c1.id in ids
    assert c2.id not in ids


def test_tags_filter_list_or(db):
    t1 = _tag_code(db, "힐링")
    t2 = _tag_code(db, "액션적")
    c1 = _content(db, "힐링")
    c2 = _content(db, "액션적")
    c3 = _content(db, "무태그")
    _link_tag(db, c1.id, t1.id)
    _link_tag(db, c2.id, t2.id)
    results = apply_rule_query(db, {"tags": ["힐링", "액션적"]})
    ids = {r.content_id for r in results}
    assert c1.id in ids
    assert c2.id in ids
    assert c3.id not in ids


# ── approved_only 필터 ────────────────────────────────────────────────────────

def test_approved_only_filter(db):
    c_ok = _content(db, "승인됨", status=ContentStatus.approved)
    c_raw = _content(db, "미처리", status=ContentStatus.raw)
    results = apply_rule_query(db, {"approved_only": True})
    ids = {r.content_id for r in results}
    assert c_ok.id in ids
    assert c_raw.id not in ids


# ── limit ─────────────────────────────────────────────────────────────────────

def test_limit(db):
    for i in range(5):
        _content(db, f"콘텐츠{i}")
    results = apply_rule_query(db, {"limit": 3})
    assert len(results) == 3


# ── 복합 필터 ─────────────────────────────────────────────────────────────────

def test_combined_genre_year_country(db):
    act = _genre_code(db, "ACT")
    c1 = _content(db, "한국액션2022", production_year=2022, country="한국")
    c2 = _content(db, "미국액션2022", production_year=2022, country="미국")
    c3 = _content(db, "한국액션2018", production_year=2018, country="한국")
    _link_genre(db, c1.id, act.id)
    _link_genre(db, c2.id, act.id)
    _link_genre(db, c3.id, act.id)
    results = apply_rule_query(db, {"genre": "ACT", "year_gte": 2020, "country": "한국"})
    ids = {r.content_id for r in results}
    assert c1.id in ids
    assert c2.id not in ids
    assert c3.id not in ids


def test_combined_reason_contains_all_rules(db):
    act = _genre_code(db, "ACT")
    c = _content(db, "한국액션2022", production_year=2022, country="한국")
    _link_genre(db, c.id, act.id)
    results = apply_rule_query(db, {"genre": "ACT", "year_gte": 2020, "country": "한국"})
    assert len(results) == 1
    assert "ACT" in results[0].reason
    assert "2020" in results[0].reason
    assert "한국" in results[0].reason


# ── compute_members 통합: rule 노드에서 Tier 0 엔진 결합 ─────────────────────

def test_compute_members_uses_rule_engine(db):
    act = _genre_code(db, "ACT")
    c1 = _content(db, "액션A")
    c2 = _content(db, "드라마B")
    _link_genre(db, c1.id, act.id)
    # rule 노드 생성
    node = create_node(db, NodeKind.rule, "액션 자동", rule_query={"genre": "ACT"})
    members = compute_members(db, node)
    ids = [m.content_id for m in members]
    assert c1.id in ids
    assert c2.id not in ids
    assert all(m.source == "rule" for m in members)


def test_compute_members_rule_reason_populated(db):
    act = _genre_code(db, "ACT")
    c = _content(db, "액션")
    _link_genre(db, c.id, act.id)
    node = create_node(db, NodeKind.rule, "액션", rule_query={"genre": "ACT"})
    members = compute_members(db, node)
    assert len(members) == 1
    assert members[0].reason is not None
    assert "ACT" in members[0].reason
