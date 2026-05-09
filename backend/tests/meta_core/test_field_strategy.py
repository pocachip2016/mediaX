"""
Field Strategy Catalog 단위 테스트

분류별 1 케이스씩 + env override + 정규화 함수 검증
DB 의존 없음.
"""

import os
import pytest

from api.meta_core.field_strategy import (
    FIELD_STRATEGIES, FieldType, FieldStrategy, get_strategy,
    _genre_norm, _country_norm, _person_norm, _runtime_norm, _content_type_norm,
)


# ── A. 단일값·이산 ────────────────────────────────────────────────────────────

def test_a_director_type():
    s = FIELD_STRATEGIES["director"]
    assert s.type == FieldType.A_SINGLE


def test_a_director_defaults():
    s = FIELD_STRATEGIES["director"]
    assert s.agree_threshold == 2
    assert s.weight_threshold == 1.5
    assert s.normalizer is not None


def test_a_primary_genre_type():
    assert FIELD_STRATEGIES["primary_genre"].type == FieldType.A_SINGLE


def test_a_runtime_has_tolerance():
    s = FIELD_STRATEGIES["runtime"]
    assert s.tolerance == 5


def test_a_runtime_normalizer():
    s = FIELD_STRATEGIES["runtime"]
    assert s.normalizer("120분") == "120"
    assert s.normalizer("90") == "90"


def test_a_country_normalizer():
    assert _country_norm("korea") == "KR"
    assert _country_norm("South Korea") == "KR"
    assert _country_norm("JP") == "JP"


def test_a_content_type_normalizer():
    assert _content_type_norm("Movie") == "movie"
    assert _content_type_norm("TV Series") == "tv_series"


# ── B. 다중값·이산 ────────────────────────────────────────────────────────────

def test_b_cast_type():
    assert FIELD_STRATEGIES["cast"].type == FieldType.B_MULTI


def test_b_cast_max_auto():
    assert FIELD_STRATEGIES["cast"].max_auto == 20


def test_b_secondary_genres_cap():
    assert FIELD_STRATEGIES["secondary_genres"].max_auto == 3


def test_b_mood_tags_cap():
    assert FIELD_STRATEGIES["mood_tags"].max_auto == 10


# ── C. 자유 텍스트 ────────────────────────────────────────────────────────────

def test_c_synopsis_type():
    assert FIELD_STRATEGIES["synopsis"].type == FieldType.C_TEXT


def test_c_synopsis_allows_llm_merge():
    assert FIELD_STRATEGIES["synopsis"].allow_llm_merge is True


def test_c_description_type():
    assert FIELD_STRATEGIES["description"].type == FieldType.C_TEXT


# ── D. 자산 URL ───────────────────────────────────────────────────────────────

def test_d_poster_type():
    assert FIELD_STRATEGIES["poster"].type == FieldType.D_ASSET


def test_d_poster_source_priority():
    s = FIELD_STRATEGIES["poster"]
    assert s.source_priority[0] == "tmdb"


def test_d_logo_cp_first():
    s = FIELD_STRATEGIES["logo"]
    assert s.source_priority[0] == "cp"


# ── E. 외부 ID ────────────────────────────────────────────────────────────────

def test_e_tmdb_id_type():
    assert FIELD_STRATEGIES["tmdb_id"].type == FieldType.E_EXTERNAL_ID


def test_e_kobis_id_type():
    assert FIELD_STRATEGIES["kobis_id"].type == FieldType.E_EXTERNAL_ID


def test_e_kmdb_id_type():
    assert FIELD_STRATEGIES["kmdb_id"].type == FieldType.E_EXTERNAL_ID


# ── env override ──────────────────────────────────────────────────────────────

def test_agree_threshold_env_override(monkeypatch):
    monkeypatch.setenv("META_FIELD_THRESHOLD__DIRECTOR", "3")
    # 모듈을 재임포트해야 env 반영됨 — _agree() 직접 테스트
    from api.meta_core.field_strategy import _agree
    assert _agree("director", 2) == 3


def test_weight_threshold_env_override(monkeypatch):
    monkeypatch.setenv("META_WEIGHT_THRESHOLD__SYNOPSIS", "2.0")
    from api.meta_core.field_strategy import _weight
    assert _weight("synopsis", 1.5) == 2.0


# ── get_strategy ──────────────────────────────────────────────────────────────

def test_get_strategy_known():
    s = get_strategy("director")
    assert s is not None
    assert s.type == FieldType.A_SINGLE


def test_get_strategy_unknown():
    assert get_strategy("nonexistent_field") is None


# ── 정규화 함수 ───────────────────────────────────────────────────────────────

def test_genre_norm():
    assert _genre_norm("드라마") == "드라마"
    assert _genre_norm(" Sci-Fi ") == "scifi"


def test_person_norm():
    assert _person_norm("봉 준 호") == "봉준호"
    assert _person_norm("Bong Joon-ho") == "bongjoon-ho"
