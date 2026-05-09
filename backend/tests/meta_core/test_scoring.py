"""
meta_core.scoring 단위 테스트
DB 접근 없음 — 순수 함수 검증
"""
import pytest
from api.meta_core.scoring import (
    classify_match,
    cast_overlap_score,
    compute_match_score,
    external_id_score,
    normalize_title,
    MatchScoreResult,
    title_score,
    year_score,
)


# ── normalize_title ─────────────────────────────────────────────

def test_normalize_title_removes_year():
    assert "(2024)" not in normalize_title("눈물의 여왕 (2024)")

def test_normalize_title_removes_season():
    result = normalize_title("My Drama Season 2")
    assert "season" not in result
    assert "2" not in result

def test_normalize_title_empty():
    assert normalize_title("") == ""
    assert normalize_title(None) == ""


# ── title_score ─────────────────────────────────────────────────

def test_title_score_exact():
    assert title_score("눈물의 여왕", "눈물의 여왕") == 1.0

def test_title_score_different():
    assert title_score("눈물의 여왕", "이상한 변호사 우영우") < 0.3

def test_title_score_similar():
    # 공백 차이만 있는 경우
    score = title_score("눈물의여왕", "눈물의 여왕")
    assert score >= 0.7

def test_title_score_empty():
    assert title_score("", "눈물의 여왕") == 0.0


# ── year_score ──────────────────────────────────────────────────

def test_year_score_exact():
    assert year_score(2024, 2024) == 1.0

def test_year_score_close():
    assert year_score(2024, 2023) == 0.7
    assert year_score(2024, 2025) == 0.7

def test_year_score_far():
    assert year_score(2024, 2020) == 0.0

def test_year_score_none_one_side():
    assert year_score(None, 2024) == 0.5
    assert year_score(2024, None) == 0.5

def test_year_score_none_both():
    assert year_score(None, None) == 0.5


# ── cast_overlap_score ──────────────────────────────────────────

def test_cast_overlap_exact():
    names = ["김수현", "김지원"]
    assert cast_overlap_score(names, names) == 1.0

def test_cast_overlap_partial():
    a = ["김수현", "김지원"]
    b = ["김수현", "이민호"]
    score = cast_overlap_score(a, b)
    # intersection=1, union=3 → Jaccard ≈ 0.333
    assert 0.2 < score < 0.5

def test_cast_overlap_no_match():
    a = ["김수현", "김지원"]
    b = ["이민호", "박서준"]
    assert cast_overlap_score(a, b) == 0.0

def test_cast_overlap_empty():
    assert cast_overlap_score([], []) == 0.0
    assert cast_overlap_score(["김수현"], []) == 0.0
    assert cast_overlap_score([], ["김수현"]) == 0.0


# ── external_id_score ───────────────────────────────────────────

def test_external_id_match():
    assert external_id_score({"tmdb": "1234"}, {"tmdb": "1234"}) == 1.0

def test_external_id_conflict():
    assert external_id_score({"tmdb": "1234"}, {"tmdb": "9999"}) == 0.0

def test_external_id_no_overlap():
    assert external_id_score({"tmdb": "1234"}, {"kobis": "20231234"}) == 0.0

def test_external_id_empty():
    assert external_id_score({}, {"tmdb": "1234"}) == 0.0
    assert external_id_score({"tmdb": "1234"}, {}) == 0.0


# ── compute_match_score ─────────────────────────────────────────

_CAND_HIGH = {
    "title_norm": "눈물의 여왕",
    "year": 2024,
    "cast_json": ["김수현", "김지원"],
    "source_type": "tmdb",
    "external_ids_json": {"tmdb": "1234"},
    "poster_url": "https://example.com/poster.jpg",
}

_CONT_HIGH = {
    "title": "눈물의 여왕",
    "production_year": 2024,
    "cast": ["김수현", "김지원"],
    "external_ids": {"tmdb": "1234"},
    "poster_url": "https://example.com/poster.jpg",
}

def test_compute_match_score_high():
    r = compute_match_score(_CAND_HIGH, _CONT_HIGH)
    assert isinstance(r, MatchScoreResult)
    assert r.score >= 0.85
    assert "title_exact" in r.reasons or "title_similar" in r.reasons
    assert "year_match" in r.reasons
    assert "external_id_match" in r.reasons

def test_compute_match_score_low():
    cand = {"title_norm": "전혀다른작품", "year": 2010, "source_type": "tmdb"}
    cont = {"title": "눈물의 여왕", "production_year": 2024}
    r = compute_match_score(cand, cont)
    assert r.score < 0.5

def test_compute_match_score_multi_source_bonus():
    other = [{"source_type": "kobis"}, {"source_type": "kmdb"}]
    r_with = compute_match_score(_CAND_HIGH, _CONT_HIGH, other_candidates=other)
    r_without = compute_match_score(_CAND_HIGH, _CONT_HIGH)
    assert r_with.score > r_without.score
    assert "multi_source" in r_with.reasons


# ── classify_match ──────────────────────────────────────────────

def test_classify_match_auto():
    assert classify_match(0.90) == "auto"
    assert classify_match(1.00) == "auto"

def test_classify_match_review():
    assert classify_match(0.89) == "review"
    assert classify_match(0.70) == "review"

def test_classify_match_hold():
    assert classify_match(0.69) == "hold"
    assert classify_match(0.50) == "hold"

def test_classify_match_drop():
    assert classify_match(0.49) == "drop"
    assert classify_match(0.0) == "drop"
