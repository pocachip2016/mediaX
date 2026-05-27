"""distribution-step2.1 — OTT 기반 인프라 (base / matcher / writer / runner) 테스트"""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from api.distribution.models import ContentDistribution
from api.distribution.ott.base import OttItem, OttSource
from api.distribution.ott.matcher import match_content
from api.distribution.ott.runner import SyncSummary, run_source
from api.distribution.ott.writer import upsert_distribution
from api.programming.metadata.models.content import Content


# ── 픽스처 ──────────────────────────────────────────────────

def _make_content(db, title: str, year: int | None = None, id_override: int | None = None) -> Content:
    c = Content(title=title, production_year=year)
    db.add(c)
    db.flush()
    return c


class _DummySource(OttSource):
    channel = "ott_dummy"

    def __init__(self, items: list[OttItem]):
        self._items = items

    def fetch_top(self, limit: int = 20) -> list[OttItem]:
        return self._items[:limit]


# ── match_content 테스트 ──────────────────────────────────

def test_match_hit(db):
    _make_content(db, "기생충", 2019)
    item = OttItem(title="기생충", rank=1, production_year=2019)
    assert match_content(db, item) is not None


def test_match_miss_title(db):
    _make_content(db, "기생충", 2019)
    item = OttItem(title="존재하지않는영화", rank=1)
    assert match_content(db, item) is None


def test_match_miss_year(db):
    _make_content(db, "기생충", 2019)
    item = OttItem(title="기생충", rank=1, production_year=2020)
    assert match_content(db, item) is None


def test_match_year_none_allows_title_only(db):
    _make_content(db, "기생충", 2019)
    item = OttItem(title="기생충", rank=1, production_year=None)
    assert match_content(db, item) is not None


def test_match_multiple_returns_latest_id(db):
    c1 = _make_content(db, "기생충")
    c2 = _make_content(db, "기생충")
    item = OttItem(title="기생충", rank=1)
    matched = match_content(db, item)
    assert matched == max(c1.id, c2.id)


# ── upsert_distribution 테스트 ──────────────────────────────

def test_upsert_insert(db):
    c = _make_content(db, "버닝")
    row = upsert_distribution(
        db, content_id=c.id, channel="ott_test",
        rank=1, score=1.0, raw={"r": 1}, external_id="ext1",
    )
    assert row.id is not None
    assert row.popularity_rank == 1


def test_upsert_update(db):
    c = _make_content(db, "버닝")
    upsert_distribution(db, content_id=c.id, channel="ott_test",
                        rank=1, score=1.0, raw={}, external_id="e1")
    row2 = upsert_distribution(db, content_id=c.id, channel="ott_test",
                               rank=3, score=0.9, raw={"upd": True}, external_id="e2")
    all_rows = db.query(ContentDistribution).filter_by(content_id=c.id).all()
    assert len(all_rows) == 1
    assert row2.popularity_rank == 3
    assert row2.external_id == "e2"


# ── run_source 테스트 ──────────────────────────────────────

def test_run_source_normal(db):
    _make_content(db, "버닝", 2018)
    items = [OttItem(title="버닝", rank=1, production_year=2018)]
    summary = run_source(db, _DummySource(items))
    assert summary.matched == 1
    assert summary.upserted == 1
    assert summary.dropped == 0


def test_run_source_item_exception_isolated(db):
    """한 건 예외가 발생해도 다른 건 처리 완료"""
    _make_content(db, "버닝", 2018)

    class _ErrSource(_DummySource):
        def fetch_top(self, limit=20):
            return [
                OttItem(title="폭발해라", rank=1),  # 미매칭 → dropped
                OttItem(title="버닝", rank=2, production_year=2018),
            ]

    summary = run_source(db, _ErrSource([]))
    assert summary.fetched == 2
    assert summary.matched == 1
    assert summary.dropped == 1
