"""
enrich_content — KMDB 일일 한도 초과 graceful degrade 회귀 가드.

계약(dev-auto-headless, 커밋 PR #18):
  KMDB 일일 한도 초과 시 enrich_content는 KmdbDailyLimitExceeded를 **잡아서**
  KMDB만 스킵("kmdb:daily_limit")하고 정상 반환해야 한다.
  잡지 않으면 500이 전파되어 S2 autofill 전체가 브라우저에서 'Failed to fetch'로 실패.

KMDB 한도 소진은 외부 상태라 실제 재현 불가 → _fetch_kmdb_with_cache가 예외를
던지도록 단 1개 함수만 monkeypatch로 시뮬레이션(네트워크 무관).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import api.meta_core.enrich as enrich_mod
from api.meta_core.clients.kmdb_client import KmdbDailyLimitExceeded, KmdbApiKeyMissing
from api.programming.metadata.models.content import Content, ContentType, ContentStatus
from shared.config import settings


def _content(db):
    c = Content(title="베테랑", content_type=ContentType.movie,
                cp_name="TEST_QUOTA", status=ContentStatus.raw)
    db.add(c)
    db.flush()
    return c


def test_kmdb_daily_limit_caught_not_raised(db, monkeypatch):
    """일일 한도 초과 → 예외 전파 없이 'kmdb:daily_limit'로 스킵 기록."""
    def _raise(*a, **k):
        raise KmdbDailyLimitExceeded("KMDB daily limit (500) exceeded")
    monkeypatch.setattr(enrich_mod, "_fetch_kmdb_with_cache", _raise)

    c = _content(db)
    # only_sources={"kmdb"} → KMDB만 실행. 예외가 잡히지 않으면 여기서 raise되어 테스트 실패.
    result = enrich_mod.enrich_content(c.id, db, only_sources={"kmdb"})

    assert "kmdb:daily_limit" in result.sources_skipped
    assert "kmdb" not in result.sources_hit


def test_kmdb_api_key_missing_caught(db, monkeypatch):
    """기존 동작 가드 — API 키 없음도 'kmdb:no_key'로 스킵(전파 안 함)."""
    def _raise(*a, **k):
        raise KmdbApiKeyMissing("KMDB_API_KEY is not set")
    monkeypatch.setattr(enrich_mod, "_fetch_kmdb_with_cache", _raise)

    c = _content(db)
    result = enrich_mod.enrich_content(c.id, db, only_sources={"kmdb"})

    assert "kmdb:no_key" in result.sources_skipped


def test_kmdb_limit_does_not_abort_other_sources(db, monkeypatch):
    """KMDB 한도 초과가 같은 호출의 다른 소스(TMDB) 처리를 막지 않음 — graceful degrade."""
    def _raise(*a, **k):
        raise KmdbDailyLimitExceeded("KMDB daily limit (500) exceeded")
    monkeypatch.setattr(enrich_mod, "_fetch_kmdb_with_cache", _raise)
    # TMDB 키 없음 → tmdb:no_key 기록(네트워크 없이 TMDB 블록 통과 확인)
    monkeypatch.setattr(settings, "TMDB_API_KEY", "")

    c = _content(db)
    result = enrich_mod.enrich_content(c.id, db, only_sources={"tmdb", "kmdb"})

    # 두 소스 모두 스킵으로 기록되고 함수는 정상 반환(예외 없음)
    assert "tmdb:no_key" in result.sources_skipped
    assert "kmdb:daily_limit" in result.sources_skipped
