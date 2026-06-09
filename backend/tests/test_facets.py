"""facets.py 단위 테스트 — VOCAB 검증·intensity 포함."""
import pytest

from api.programming.scheduling.facets import VOCAB, facet_overlap_score, validate_facets


# ── validate_facets ────────────────────────────────────────────────────────────

def test_validate_keeps_valid_values():
    raw = {"mood": ["경쾌", "감성"], "intensity": ["폭력", "공포"]}
    result = validate_facets(raw)
    assert result["mood"] == ["경쾌", "감성"]
    assert result["intensity"] == ["폭력", "공포"]


def test_validate_strips_invalid_values():
    raw = {"mood": ["경쾌", "없는값"], "intensity": ["폭력", "존재안함"]}
    result = validate_facets(raw)
    assert result["mood"] == ["경쾌"]
    assert result["intensity"] == ["폭력"]


def test_validate_drops_unknown_axis():
    raw = {"mood": ["경쾌"], "unknown_axis": ["xyz"]}
    result = validate_facets(raw)
    assert "unknown_axis" not in result
    assert "mood" in result


def test_validate_empty_list_after_strip():
    raw = {"intensity": ["없는값1", "없는값2"]}
    result = validate_facets(raw)
    # 빈 리스트 또는 키 제거 — 둘 다 허용
    assert result.get("intensity", []) == []


# ── intensity 어휘 망라 ────────────────────────────────────────────────────────

def test_intensity_vocab_complete():
    expected = {"폭력", "잔인", "선정", "공포", "복잡"}
    assert set(VOCAB["intensity"]) == expected


# ── facet_overlap_score ────────────────────────────────────────────────────────

def test_overlap_score_identical():
    a = {"mood": ["경쾌"], "intensity": ["폭력"]}
    b = {"mood": ["경쾌"], "intensity": ["폭력"]}
    assert facet_overlap_score(a, b) == pytest.approx(1.0)


def test_overlap_score_zero():
    a = {"mood": ["경쾌"], "intensity": ["폭력"]}
    b = {"mood": ["어두움"], "intensity": ["복잡"]}
    assert facet_overlap_score(a, b) == pytest.approx(0.0)


def test_overlap_score_intensity_contributes():
    # intensity만 겹치는 경우 > 0
    a = {"intensity": ["폭력", "공포"]}
    b = {"intensity": ["폭력"]}
    score = facet_overlap_score(a, b)
    assert score > 0.0


def test_overlap_score_partial():
    a = {"mood": ["경쾌", "감성"], "intensity": ["폭력"]}
    b = {"mood": ["경쾌"], "intensity": ["폭력"]}
    score = facet_overlap_score(a, b)
    assert 0.0 < score < 1.0
