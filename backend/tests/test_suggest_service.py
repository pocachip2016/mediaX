"""suggest_service 단위 테스트 — SQLite in-memory. Ollama 비종속(벡터 직접 주입)."""
import pytest

from api.programming.metadata.models.content import Content, ContentStatus, ContentType
from api.programming.scheduling.models import (
    ChildType,
    LinkSource,
    LinkStatus,
    ProgrammingLink,
    ProgrammingNode,
    ProgrammingNodeSet,
)
from api.programming.scheduling.profile_models import ContentSemanticProfile
from api.programming.scheduling.suggest_service import confirm_link, reject_link, suggest_links


# ── helpers ───────────────────────────────────────────────────────────────────

def _node(db, *, embed_theme=None, theme_features=None, rule_query=None):
    ns = ProgrammingNodeSet(name="s", status="draft")
    db.add(ns)
    db.flush()
    n = ProgrammingNode(
        set_id=ns.id,
        kind="manual",
        name="테스트 노드",
        embed_theme=embed_theme,
        theme_features=theme_features,
        rule_query=rule_query,
    )
    db.add(n)
    db.flush()
    return n


def _content(db, title="콘텐츠"):
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
    return c


def _profile(db, content_id, embed_synopsis=None, facets=None):
    p = ContentSemanticProfile(
        content_id=content_id,
        embed_synopsis=embed_synopsis or [],
        facets=facets or {},
        model_version="test:1.0",
    )
    db.add(p)
    db.flush()
    return p


def _suggested_link(db, node_id, content_id, confidence=0.5):
    lnk = ProgrammingLink(
        parent_node_id=node_id,
        child_type=ChildType.content,
        child_content_id=content_id,
        source=LinkSource.ai,
        confidence=confidence,
        status=LinkStatus.suggested,
        sort_order=0,
    )
    db.add(lnk)
    db.flush()
    return lnk


# ── suggest_links ─────────────────────────────────────────────────────────────

def test_suggest_saves_source_ai_suggested(db):
    """추천 저장 시 source=ai, status=suggested 로 저장돼야 한다."""
    node = _node(db, embed_theme=[1.0, 0.0])
    c = _content(db)
    _profile(db, c.id, embed_synopsis=[1.0, 0.0])

    result = suggest_links(db, node, threshold=0.0)

    assert len(result.saved) == 1
    lnk = result.saved[0]
    assert lnk.source == LinkSource.ai
    assert lnk.status == LinkStatus.suggested
    assert lnk.child_content_id == c.id


def test_suggest_threshold_excludes_low_confidence(db):
    """threshold 미만 후보는 저장되지 않고 skipped_count 에 반영된다."""
    node = _node(db, embed_theme=[1.0, 0.0])
    c_high = _content(db, "high")
    c_low  = _content(db, "low")
    _profile(db, c_high.id, embed_synopsis=[1.0, 0.0])   # cosine≈1 → high
    _profile(db, c_low.id,  embed_synopsis=[0.0, 1.0])   # cosine=0 → low

    result = suggest_links(db, node, threshold=0.5)

    saved_ids = {lnk.child_content_id for lnk in result.saved}
    assert c_high.id in saved_ids
    assert c_low.id not in saved_ids
    assert result.skipped_count >= 1


def test_suggest_idempotent_updates_existing(db):
    """이미 suggested 링크가 있으면 중복 생성 없이 confidence/reason 갱신."""
    node = _node(db, embed_theme=[1.0, 0.0])
    c = _content(db)
    _profile(db, c.id, embed_synopsis=[1.0, 0.0])

    suggest_links(db, node, threshold=0.0)
    suggest_links(db, node, threshold=0.0)  # 재실행

    count = (
        db.query(ProgrammingLink)
        .filter(
            ProgrammingLink.parent_node_id == node.id,
            ProgrammingLink.child_content_id == c.id,
        )
        .count()
    )
    assert count == 1


def test_suggest_reason_stored_in_copy_override(db):
    """reason은 copy_override['_ai_reason'] 에 저장돼야 한다."""
    node = _node(db, embed_theme=[1.0, 0.0])
    c = _content(db)
    _profile(db, c.id, embed_synopsis=[1.0, 0.0])

    result = suggest_links(db, node, threshold=0.0)

    lnk = result.saved[0]
    assert lnk.copy_override is not None
    assert "_ai_reason" in lnk.copy_override
    assert "tier2" in lnk.copy_override["_ai_reason"]


def test_suggest_skips_active_link(db):
    """이미 active 링크가 있으면 갱신하지 않고 그대로 둔다."""
    node = _node(db, embed_theme=[1.0, 0.0])
    c = _content(db)
    _profile(db, c.id, embed_synopsis=[1.0, 0.0])

    # 먼저 active 링크 수동 생성
    existing = ProgrammingLink(
        parent_node_id=node.id,
        child_type=ChildType.content,
        child_content_id=c.id,
        source=LinkSource.manual,
        status=LinkStatus.active,
        sort_order=0,
    )
    db.add(existing)
    db.flush()

    result = suggest_links(db, node, threshold=0.0)

    # active 링크가 있으면 saved에 포함 안 됨
    assert not any(lnk.child_content_id == c.id for lnk in result.saved)
    # active 상태 변경 없음
    db.refresh(existing)
    assert existing.status == LinkStatus.active


def test_suggest_empty_candidates(db):
    """매칭 후보 없으면 빈 결과."""
    node = _node(db, embed_theme=[1.0, 0.0])
    # 콘텐츠/프로파일 없음

    result = suggest_links(db, node, threshold=0.0)

    assert result.saved == []
    assert result.skipped_count == 0


def test_suggest_threshold_zero_includes_all(db):
    """threshold=0 이면 confidence 0인 후보도 포함된다."""
    node = _node(db, embed_theme=[1.0, 0.0])
    c = _content(db)
    _profile(db, c.id, embed_synopsis=[0.0, 1.0])  # cosine=0, facet=0 → confidence=0

    result = suggest_links(db, node, threshold=0.0)

    assert any(lnk.child_content_id == c.id for lnk in result.saved)


# ── confirm_link ──────────────────────────────────────────────────────────────

def test_confirm_suggested_to_active(db):
    """confirm_link: suggested → active."""
    node = _node(db)
    c = _content(db)
    lnk = _suggested_link(db, node.id, c.id)

    confirmed = confirm_link(db, lnk.id)

    assert confirmed.status == LinkStatus.active


def test_confirm_non_suggested_raises(db):
    """active 링크를 confirm 하면 ValueError."""
    node = _node(db)
    c = _content(db)
    lnk = ProgrammingLink(
        parent_node_id=node.id,
        child_type=ChildType.content,
        child_content_id=c.id,
        source=LinkSource.manual,
        status=LinkStatus.active,
        sort_order=0,
    )
    db.add(lnk)
    db.flush()

    with pytest.raises(ValueError, match="suggested"):
        confirm_link(db, lnk.id)


# ── reject_link ───────────────────────────────────────────────────────────────

def test_reject_suggested_to_rejected(db):
    """reject_link: suggested → rejected."""
    node = _node(db)
    c = _content(db)
    lnk = _suggested_link(db, node.id, c.id)

    rejected = reject_link(db, lnk.id)

    assert rejected.status == LinkStatus.rejected


def test_reject_non_suggested_raises(db):
    """active 링크를 reject 하면 ValueError."""
    node = _node(db)
    c = _content(db)
    lnk = ProgrammingLink(
        parent_node_id=node.id,
        child_type=ChildType.content,
        child_content_id=c.id,
        source=LinkSource.manual,
        status=LinkStatus.active,
        sort_order=0,
    )
    db.add(lnk)
    db.flush()

    with pytest.raises(ValueError, match="suggested"):
        reject_link(db, lnk.id)
