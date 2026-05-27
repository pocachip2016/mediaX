"""distribution-step2.2 — WatchaTopSource 테스트 (mocked HTTP)"""
from unittest.mock import MagicMock, patch

import pytest

from api.distribution.ott.watcha import WatchaTopSource

_MOCK_HTML = """
<html><body>
<a href="/ko/contents/abc1234">기생충</a>
<a href="/ko/contents/def5678">버닝</a>
<a href="/ko/contents/ghi9012">아가씨</a>
<a href="/ko/contents/jkl3456">올드보이</a>
</body></html>
"""

_HTTP_ERROR_HTML = ""


def _mock_response(text: str, status_code: int = 200):
    resp = MagicMock()
    resp.text = text
    resp.status_code = status_code
    if status_code >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    else:
        resp.raise_for_status.return_value = None
    return resp


def test_fetch_top_parses_cards():
    with patch("api.distribution.ott.watcha.requests.get") as mock_get:
        mock_get.return_value = _mock_response(_MOCK_HTML)
        source = WatchaTopSource()
        items = source.fetch_top(limit=20)
    assert len(items) == 4
    assert items[0].rank == 1
    assert items[1].rank == 2


def test_fetch_top_slug_extracted():
    with patch("api.distribution.ott.watcha.requests.get") as mock_get:
        mock_get.return_value = _mock_response(_MOCK_HTML)
        source = WatchaTopSource()
        items = source.fetch_top()
    assert items[0].external_id == "abc1234"
    assert items[1].external_id == "def5678"


def test_fetch_top_limit_respected():
    with patch("api.distribution.ott.watcha.requests.get") as mock_get:
        mock_get.return_value = _mock_response(_MOCK_HTML)
        source = WatchaTopSource()
        items = source.fetch_top(limit=2)
    assert len(items) == 2


def test_fetch_top_http_failure_returns_empty():
    with patch("api.distribution.ott.watcha.requests.get") as mock_get:
        mock_get.side_effect = Exception("connection error")
        source = WatchaTopSource()
        items = source.fetch_top()
    assert items == []


def test_fetch_top_run_source_matched_dropped(db):
    from api.distribution.ott.runner import run_source
    from api.programming.metadata.models.content import Content

    c = Content(title="기생충")
    db.add(c)
    db.flush()

    with patch("api.distribution.ott.watcha.requests.get") as mock_get:
        mock_get.return_value = _mock_response(_MOCK_HTML)
        source = WatchaTopSource()
        summary = run_source(db, source)

    assert summary.matched >= 1
    assert summary.dropped >= 1
    assert summary.matched + summary.dropped == summary.fetched
