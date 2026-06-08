"""match_service 단위 테스트 — SQLite in-memory. Ollama 비종속(벡터 직접 주입)."""
import pytest

from api.programming.metadata.models.content import Content, ContentStatus, ContentType
from api.programming.metadata.models.taxonomy import ContentGenre, GenreCode
from api.programming.scheduling.match_service import (
    MatchResult,
    cosine_similarity,
    match_node_to_contents,
)
from api.programming.scheduling.models import NodeKind, ProgrammingNode, ProgrammingNodeSet
from api.programming.scheduling.profile_models import ContentSemanticProfile


# ── helpers ───────────────────────────────────────────────────────────────────

def _node(db, *, rule_query=None, embed_theme=None, theme_features=None):
    ns = ProgrammingNodeSet(name="s", status="draft")
    db.add(ns)
    db.flush()
    n = ProgrammingNode(
        set_id=ns.id,
        kind=NodeKind.manual,
        name="테스트 노드",
        rule_query=rule_query,
        embed_theme=embed_theme,
        theme_features=theme_features,
    )
    db.add(n)
    db.flush()
    return n


def _content(db, title="콘텐츠", genre_code=None):
    c = Content(
        title=title,
        content_type=ContentType.movie,
        production_year=2024,
        country="한국",
        status=ContentStatus.approved,
        cp_name="TEST",
    )
    db.add(c)
    db.flush()
    if genre_code:
        gc = GenreCode(code=genre_code, name_ko=genre_code)
        db.add(gc)
        db.flush()
        cg = ContentGenre(content_id=c.id, genre_id=gc.id)
        db.add(cg)
        db.flush()
    return c


def _profile(db, content_id, embed_synopsis=None, facets=None):
    p = ContentSemanticProfile(
        content_id=content_id,
        embed_synopsis=embed_synopsis,
        facets=facets,
        model_version="test:1.0",
    )
    db.add(p)
    db.flush()
    return p


# ── cosine_similarity ─────────────────────────────────────────────────────────

def test_cosine_identical():
    v = [1.0, 0.0, 0.0]
    assert abs(cosine_similarity(v, v) - 1.0) < 1e-9


def test_cosine_orthogonal():
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    assert abs(cosine_similarity(a, b)) < 1e-9


def test_cosine_zero_norm():
    assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0


def test_cosine_length_mismatch():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0, 0.0]) == 0.0


def test_cosine_empty():
    assert cosine_similarity([], []) == 0.0


# ── cosine 랭킹 ───────────────────────────────────────────────────────────────

def test_cosine_ranking(db):
    """node embed에 가까운 콘텐츠가 상위여야 한다."""
    node_vec = [1.0, 0.0]
    node = _node(db, embed_theme=node_vec)

    c_near = _content(db, "near")
    c_far  = _content(db, "far")
    _profile(db, c_near.id, embed_synopsis=[1.0, 0.0])   # cosine=1.0
    _profile(db, c_far.id,  embed_synopsis=[0.0, 1.0])   # cosine=0.0

    results = match_node_to_contents(db, node)
    assert results[0].content_id == c_near.id
    assert results[0].cosine > results[1].cosine


# ── facet overlap 기여 ────────────────────────────────────────────────────────

def test_facet_overlap_contribution(db):
    """같은 cosine이어도 facet 겹침이 큰 콘텐츠가 confidence↑."""
    node = _node(
        db,
        embed_theme=[1.0, 0.0],
        theme_features={"facets": {"mood": ["경쾌", "감성"]}},
    )

    c_high = _content(db, "high-facet")
    c_low  = _content(db, "low-facet")
    # 둘 다 동일한 cosine
    _profile(db, c_high.id, embed_synopsis=[1.0, 0.0], facets={"mood": ["경쾌", "감성"]})
    _profile(db, c_low.id,  embed_synopsis=[1.0, 0.0], facets={"mood": ["어두움"]})

    results = match_node_to_contents(db, node)
    high = next(r for r in results if r.content_id == c_high.id)
    low  = next(r for r in results if r.content_id == c_low.id)
    assert high.confidence > low.confidence


# ── 가중합 ────────────────────────────────────────────────────────────────────

def test_weighted_sum(db):
    """confidence = cosine_weight * cosine + facet_weight * facet_overlap."""
    node = _node(
        db,
        embed_theme=[1.0, 0.0],
        theme_features={"facets": {"mood": ["경쾌"]}},
    )
    c = _content(db)
    _profile(db, c.id, embed_synopsis=[1.0, 0.0], facets={"mood": ["경쾌"]})

    results = match_node_to_contents(db, node, cosine_weight=0.6, facet_weight=0.4)
    r = results[0]
    expected = 0.6 * r.cosine + 0.4 * r.facet_overlap
    assert abs(r.confidence - expected) < 1e-9


# ── Tier0 후보축소 ────────────────────────────────────────────────────────────

def test_tier0_candidate_exclusion(db):
    """rule_query에 걸리지 않는 콘텐츠는 임베딩이 가까워도 제외."""
    node = _node(db, embed_theme=[1.0, 0.0], rule_query={"genre": "ACT"})

    # ACT 장르 있는 콘텐츠 — 포함돼야 함
    c_in  = _content(db, "in",  genre_code="ACT")
    # 장르 없는 콘텐츠 — Tier0에서 제외
    c_out = _content(db, "out")

    _profile(db, c_in.id,  embed_synopsis=[1.0, 0.0])
    _profile(db, c_out.id, embed_synopsis=[1.0, 0.0])

    results = match_node_to_contents(db, node)
    ids = [r.content_id for r in results]
    assert c_in.id in ids
    assert c_out.id not in ids


# ── min_confidence 필터 ───────────────────────────────────────────────────────

def test_min_confidence_filter(db):
    node = _node(db, embed_theme=[1.0, 0.0])
    c = _content(db)
    _profile(db, c.id, embed_synopsis=[0.0, 1.0])  # cosine=0, facet=0 → confidence=0

    results = match_node_to_contents(db, node, min_confidence=0.1)
    assert all(r.confidence >= 0.1 for r in results)


# ── 프로파일 없는 후보 제외 ───────────────────────────────────────────────────

def test_no_profile_excluded(db):
    node = _node(db, embed_theme=[1.0, 0.0])
    c = _content(db)  # 프로파일 없음

    results = match_node_to_contents(db, node)
    assert not any(r.content_id == c.id for r in results)


# ── embed_theme 없음 → cosine=0, facet-only ───────────────────────────────────

def test_no_node_embed_facet_only(db):
    node = _node(
        db,
        embed_theme=None,  # 벡터 없음
        theme_features={"facets": {"mood": ["경쾌"]}},
    )
    c = _content(db)
    _profile(db, c.id, embed_synopsis=[1.0, 0.0], facets={"mood": ["경쾌"]})

    results = match_node_to_contents(db, node)
    assert len(results) == 1
    r = results[0]
    assert r.cosine == 0.0
    assert r.facet_overlap > 0.0
    assert r.confidence > 0.0  # facet-only confidence


# ── limit 상한 + 정렬 결정성 ─────────────────────────────────────────────────

def test_limit_and_deterministic_sort(db):
    node = _node(db, embed_theme=[1.0, 0.0])
    # 동일한 벡터를 가진 콘텐츠 3개 → 동률 시 content_id 오름차순
    cs = [_content(db, f"c{i}") for i in range(3)]
    for c in cs:
        _profile(db, c.id, embed_synopsis=[1.0, 0.0])

    results = match_node_to_contents(db, node, limit=2)
    assert len(results) == 2
    # 동률 → content_id 오름차순이어야 함
    assert results[0].content_id < results[1].content_id
