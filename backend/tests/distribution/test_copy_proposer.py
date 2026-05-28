"""
tests/distribution/test_copy_proposer.py — Step 4: copy-proposer-llm 유닛 테스트

LLM 호출은 AsyncMock으로 패치 (외부 의존성 없음).
비동기 함수는 asyncio.run()으로 동기 래퍼 사용 (pytest-asyncio 미설치 환경).
"""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.distribution.copy_proposer import (
    _build_prompt,
    _extract_json_array,
    _section_names_as_fallback,
    propose_copy,
)


def _run(coro):
    return asyncio.run(coro)


# ── _extract_json_array ────────────────────────────────────────────────────────

class TestExtractJsonArray:
    def test_fenced_json_block(self):
        text = '```json\n[{"headline_copy": "테스트", "sub_copy": "설명"}]\n```'
        result = _extract_json_array(text)
        assert len(result) == 1
        assert result[0]["headline_copy"] == "테스트"

    def test_bare_array(self):
        text = '[{"headline_copy": "A"}, {"headline_copy": "B"}]'
        result = _extract_json_array(text)
        assert len(result) == 2

    def test_text_with_no_array_returns_empty(self):
        result = _extract_json_array("LLM이 잘못된 응답을 보낸 경우")
        assert result == []

    def test_wrapped_in_prose(self):
        text = '여기 결과입니다:\n[{"headline_copy": "핵심"}]\n끝.'
        result = _extract_json_array(text)
        assert result[0]["headline_copy"] == "핵심"


# ── _section_names_as_fallback ─────────────────────────────────────────────────

class TestSectionNamesFallback:
    def test_basic(self):
        names = ["이번 주 TOP10", "신작 공개"]
        result = _section_names_as_fallback(names, limit=3)
        assert len(result) == 2
        assert result[0]["headline_copy"] == "이번 주 TOP10"
        assert result[0]["source"] == "external_imported"
        assert result[0]["rank"] == 1

    def test_limit_applied(self):
        names = ["A", "B", "C", "D"]
        result = _section_names_as_fallback(names, limit=2)
        assert len(result) == 2

    def test_empty_names(self):
        result = _section_names_as_fallback([], limit=3)
        assert result == []


# ── _build_prompt ──────────────────────────────────────────────────────────────

class TestBuildPrompt:
    def test_includes_genres(self):
        tf = {"genres": ["드라마", "로맨스"]}
        prompt = _build_prompt(tf, [], 3)
        assert "드라마" in prompt
        assert "로맨스" in prompt

    def test_includes_section_names(self):
        tf = {}
        names = ["이번 주 TOP10"]
        prompt = _build_prompt(tf, names, 3)
        assert "이번 주 TOP10" in prompt

    def test_era_runtime_included(self):
        tf = {"era_from": 1990, "era_to": 2000, "runtime_min": 90, "runtime_max": 120}
        prompt = _build_prompt(tf, [], 3)
        assert "1990" in prompt
        assert "90" in prompt

    def test_limit_in_prompt(self):
        prompt = _build_prompt({}, [], 5)
        assert "5" in prompt


# ── propose_copy (LLM 모킹) ───────────────────────────────────────────────────

MOCK_LLM_RESPONSE = json.dumps([
    {"headline_copy": "감동의 순간", "sub_copy": "올 겨울 최고의 선택", "reasoning": "감성적"},
    {"headline_copy": "당신의 밤을 채울 이야기", "sub_copy": None, "reasoning": "무드"},
    {"headline_copy": "지금 당장 시작하세요", "sub_copy": "놓치면 후회", "reasoning": "CTA"},
])

def _make_mock_provider(response_text: str):
    provider = MagicMock()
    provider.engine_name = "mock-gemini"
    provider.generate = AsyncMock(return_value=response_text)
    return provider


class TestProposeCopy:
    def test_normal_llm_response_returns_ai_proposed(self):
        mock_provider = _make_mock_provider(f"```json\n{MOCK_LLM_RESPONSE}\n```")
        with patch(
            "api.distribution.copy_proposer.get_provider_chain",
            return_value=[lambda: mock_provider],
        ):
            candidates, engine = _run(propose_copy(
                theme_features={"genres": ["드라마"]},
                selected_section_names=["이번 주 TOP10"],
                limit=3,
            ))

        assert len(candidates) == 3
        assert all(c["source"] == "ai_proposed" for c in candidates)
        assert candidates[0]["headline_copy"] == "감동의 순간"
        assert engine == "mock-gemini"

    def test_limit_respected(self):
        mock_provider = _make_mock_provider(f"```json\n{MOCK_LLM_RESPONSE}\n```")
        with patch(
            "api.distribution.copy_proposer.get_provider_chain",
            return_value=[lambda: mock_provider],
        ):
            candidates, _ = _run(propose_copy(
                theme_features={"genres": ["액션"]},
                selected_section_names=[],
                limit=1,
            ))
        assert len(candidates) == 1

    def test_llm_failure_falls_back_to_section_names(self):
        failing_provider = MagicMock()
        failing_provider.generate = AsyncMock(side_effect=Exception("API 오류"))

        with patch(
            "api.distribution.copy_proposer.get_provider_chain",
            return_value=[lambda: failing_provider],
        ):
            candidates, engine = _run(propose_copy(
                theme_features={"genres": ["코미디"]},
                selected_section_names=["신작 코미디", "장르-코미디"],
                limit=3,
            ))

        assert len(candidates) == 2
        assert all(c["source"] == "external_imported" for c in candidates)
        assert engine == "external_fallback"

    def test_empty_theme_and_no_sections_returns_empty(self):
        candidates, engine = _run(propose_copy(
            theme_features={},
            selected_section_names=[],
            limit=3,
        ))
        assert candidates == []
        assert engine == "none"

    def test_section_names_only_no_theme_features(self):
        """섹션명만 있어도 LLM 호출은 시도한다."""
        mock_provider = _make_mock_provider(f"```json\n{MOCK_LLM_RESPONSE}\n```")
        with patch(
            "api.distribution.copy_proposer.get_provider_chain",
            return_value=[lambda: mock_provider],
        ):
            candidates, engine = _run(propose_copy(
                theme_features={},
                selected_section_names=["주목할 만한 시리즈"],
                limit=3,
            ))
        assert len(candidates) > 0

    def test_llm_bad_json_skips_to_next_provider(self):
        bad_provider = MagicMock()
        bad_provider.generate = AsyncMock(return_value="JSON 아님 응답")
        bad_provider.engine_name = "bad-engine"

        good_provider = _make_mock_provider(f"```json\n{MOCK_LLM_RESPONSE}\n```")

        with patch(
            "api.distribution.copy_proposer.get_provider_chain",
            return_value=[lambda: bad_provider, lambda: good_provider],
        ):
            candidates, engine = _run(propose_copy(
                theme_features={"genres": ["SF"]},
                selected_section_names=[],
                limit=2,
            ))

        assert len(candidates) == 2
        assert engine == "mock-gemini"
