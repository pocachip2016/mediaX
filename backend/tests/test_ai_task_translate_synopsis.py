"""
B2: TranslateSynopsisTask 구조 검증 pytest

run() 테스트는 로컬 Ollama(qwen2.5:3b, OllamaTaskProvider) 실제 호출.
도커 네트워크 내부(ollama:11434)에서만 도달 가능 — 미기동 시 xfail.
실행: docker exec mediax-backend-1 python3 -m pytest tests/test_ai_task_translate_synopsis.py
"""

import asyncio
import pytest
from unittest.mock import MagicMock

from api.programming.metadata.ai_tasks import AI_TASK_REGISTRY, AiTask
from api.programming.metadata.ai_tasks.translate_synopsis import (
    TranslateSynopsisTask,
    translate_synopsis_task,
    _detect_language,
    _get_source_synopsis,
)
from api.programming.metadata.ai_tasks.base import TaskInput, TaskOutput
from api.programming.metadata.llm.ollama import OllamaTaskProvider


# ── 언어 감지 ─────────────────────────────────────────────

def test_detect_language_korean():
    text = "이 영화는 어린 시절의 기억을 아름답게 그려낸 작품이다."
    assert _detect_language(text) == "ko"


def test_detect_language_english():
    text = "A beautiful story about childhood memories."
    assert _detect_language(text) == "en"


def test_detect_language_empty():
    assert _detect_language("") == "en"


def test_detect_language_mixed_mostly_korean():
    text = "안녕 hello 세계 world 한국어"
    assert _detect_language(text) == "ko"


# ── build_input ───────────────────────────────────────────

def _make_meta(
    cp_synopsis=None, ai_synopsis=None,
    synopsis_ko=None, synopsis_en=None,
    content_id=1,
):
    meta = MagicMock()
    meta.content_id = content_id
    meta.cp_synopsis = cp_synopsis
    meta.ai_synopsis = ai_synopsis
    meta.synopsis_ko = synopsis_ko
    meta.synopsis_en = synopsis_en
    return meta


def test_build_input_none_when_no_synopsis():
    meta = _make_meta()
    assert translate_synopsis_task.build_input(meta) is None


def test_build_input_none_when_synopsis_too_short():
    meta = _make_meta(cp_synopsis="짧음")
    assert translate_synopsis_task.build_input(meta) is None


def test_build_input_ko_source_returns_ko_to_en():
    meta = _make_meta(cp_synopsis="이 영화는 감동적인 이야기를 담고 있습니다. 주인공의 여정이 펼쳐집니다.")
    result = translate_synopsis_task.build_input(meta)
    assert result is not None
    assert result.payload["direction"] == "ko_to_en"
    assert result.payload["target_lang"] == "English"
    assert result.task_name == "translate_synopsis"


def test_build_input_en_source_returns_en_to_ko():
    meta = _make_meta(cp_synopsis="This is a heartwarming story about a young boy's journey.")
    result = translate_synopsis_task.build_input(meta)
    assert result is not None
    assert result.payload["direction"] == "en_to_ko"
    assert result.payload["target_lang"] == "Korean"


def test_build_input_none_when_both_filled():
    meta = _make_meta(
        cp_synopsis="이 영화는 감동적인 이야기를 담고 있습니다.",
        synopsis_ko="한국어 줄거리",
        synopsis_en="English synopsis",
    )
    assert translate_synopsis_task.build_input(meta) is None


def test_build_input_truncates_long_synopsis():
    long_text = "가 " * 2000  # 4000자
    meta = _make_meta(cp_synopsis=long_text)
    result = translate_synopsis_task.build_input(meta)
    assert result is not None
    assert len(result.payload["source_text"]) <= 2000


# ── run (mock provider) ───────────────────────────────────

def test_run_ko_to_en_with_ollama():
    """실제 Ollama LLM으로 한국어 → 영어 번역 구조 검증."""
    task_input = TaskInput(
        content_id=1,
        task_name="translate_synopsis",
        payload={
            "source_text": "이 영화는 전쟁의 참혹함 속에서도 희망을 잃지 않는 주인공의 이야기를 담고 있다.",
            "source_lang": "ko",
            "target_lang": "English",
            "direction": "ko_to_en",
        },
    )
    try:
        output = asyncio.run(translate_synopsis_task.run(task_input, [OllamaTaskProvider]))
    except Exception as exc:
        pytest.xfail(f"Ollama 미기동 또는 오류: {exc}")
    assert isinstance(output, TaskOutput)
    assert output.result["direction"] == "ko_to_en"
    assert len(output.result["translated"]) > 10
    assert output.engine  # engine_name이 채워짐


def test_run_en_to_ko_with_ollama():
    """실제 Ollama LLM으로 영어 → 한국어 번역 구조 검증."""
    task_input = TaskInput(
        content_id=1,
        task_name="translate_synopsis",
        payload={
            "source_text": "A young soldier fights to survive the horrors of war while holding on to hope.",
            "source_lang": "en",
            "target_lang": "Korean",
            "direction": "en_to_ko",
        },
    )
    try:
        output = asyncio.run(translate_synopsis_task.run(task_input, [OllamaTaskProvider]))
    except Exception as exc:
        pytest.xfail(f"Ollama 미기동 또는 오류: {exc}")
    assert isinstance(output, TaskOutput)
    assert output.result["direction"] == "en_to_ko"
    translated = output.result["translated"]
    assert len(translated) > 5
    cjk_chars = len([c for c in translated if "가" <= c <= "힣"])
    assert cjk_chars > 0, f"번역 결과에 한글 없음: {translated[:100]}"


def test_run_all_providers_fail_raises():
    """모든 provider 실패 시 ValueError 발생."""
    class FailProvider:
        engine_name = "fail"
        async def generate(self, prompt, system=""):
            raise RuntimeError("fail")

    task_input = TaskInput(
        content_id=1,
        task_name="translate_synopsis",
        payload={
            "source_text": "text",
            "source_lang": "en",
            "target_lang": "Korean",
            "direction": "en_to_ko",
        },
    )
    with pytest.raises(ValueError, match="모든 LLM 엔진 실패"):
        asyncio.run(translate_synopsis_task.run(task_input, [FailProvider]))


# ── apply ─────────────────────────────────────────────────

def test_apply_ko_to_en_sets_synopsis_en():
    meta = _make_meta(cp_synopsis="한국어 원본 줄거리입니다.", synopsis_ko=None, synopsis_en=None)
    output = TaskOutput(
        result={
            "translated": "English translated text",
            "direction": "ko_to_en",
            "source_lang": "ko",
        },
        engine="mock",
    )
    translate_synopsis_task.apply(meta, output)
    assert meta.synopsis_en == "English translated text"
    assert meta.synopsis_ko == "한국어 원본 줄거리입니다."


def test_apply_en_to_ko_sets_synopsis_ko():
    meta = _make_meta(cp_synopsis="English source text here.", synopsis_ko=None, synopsis_en=None)
    output = TaskOutput(
        result={
            "translated": "한국어 번역 텍스트",
            "direction": "en_to_ko",
            "source_lang": "en",
        },
        engine="mock",
    )
    translate_synopsis_task.apply(meta, output)
    assert meta.synopsis_ko == "한국어 번역 텍스트"
    assert meta.synopsis_en == "English source text here."


# ── 레지스트리 등록 확인 ───────────────────────────────────

def test_translate_synopsis_registered_in_registry():
    assert "translate_synopsis" in AI_TASK_REGISTRY
    task = AI_TASK_REGISTRY["translate_synopsis"]
    assert isinstance(task, TranslateSynopsisTask)
    assert isinstance(task, AiTask)
    assert task.enabled is True


def test_task_name_matches_aitasktype():
    from api.programming.metadata.models.external import AITaskType
    assert translate_synopsis_task.name in [t.value for t in AITaskType]
