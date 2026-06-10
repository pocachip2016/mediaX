"""test_facet_classify.py — MediSearch 응답 분류/포맷 순수 단위 테스트.

celery/httpx/DB mock 불필요 — _decide_facet_outcome / _fmt_conf 만 직접 호출.
회귀 가드:
  - confidence=None 이어도 source_count>0 이면 success (TypeError 크래시 방지)
  - source_count=0 + skipped_reason 없음(신작 source 미확보) → skipped (failed 재시도 낭비 방지)
"""
from workers.tasks.facet_tasks import _decide_facet_outcome, _fmt_conf


# ── _decide_facet_outcome ────────────────────────────────────────────────────

def test_skipped_reason_present():
    status, reason, src, conf = _decide_facet_outcome(
        {"skipped_reason": "no_namu", "source_count": 0}
    )
    assert status == "skipped"
    assert reason == "no_namu"


def test_no_sources_is_skipped_not_failed():
    # 신작: source_count=0 + skipped_reason 없음 → 영구 skipped (③ 회귀 가드)
    status, reason, src, conf = _decide_facet_outcome(
        {"source_count": 0, "confidence": 0.0}
    )
    assert status == "skipped"
    assert reason == "no_sources"
    assert src == 0


def test_missing_source_count_treated_as_zero():
    # source_count 키 자체가 없거나 None → 0 으로 간주 → skipped
    assert _decide_facet_outcome({})[0] == "skipped"
    assert _decide_facet_outcome({"source_count": None})[0] == "skipped"


def test_success_with_confidence_none():
    # MediSearch는 source 있어도 confidence=None 반환 가능 → success 로 통과 (② 회귀 가드)
    status, reason, src, conf = _decide_facet_outcome(
        {"source_count": 5, "confidence": None, "facet": {"primary_genre": "drama"}}
    )
    assert status == "success"
    assert reason is None
    assert src == 5
    assert conf is None


def test_success_with_confidence_value():
    status, reason, src, conf = _decide_facet_outcome(
        {"source_count": 3, "confidence": 0.83}
    )
    assert status == "success"
    assert src == 3
    assert conf == 0.83


# ── _fmt_conf ─────────────────────────────────────────────────────────────────

def test_fmt_conf_none():
    assert _fmt_conf(None) == "n/a"


def test_fmt_conf_number():
    assert _fmt_conf(0.83) == "0.83"
    assert _fmt_conf(0) == "0.00"
