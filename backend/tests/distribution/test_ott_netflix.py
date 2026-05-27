"""distribution-step2.3 — NetflixTudumSource 테스트 (mocked HTTP)"""
from unittest.mock import MagicMock, patch

import pytest

from api.distribution.ott.netflix import NetflixTudumSource

_TSV_HEADER = "country_iso2\tweek\tcategory\trank\tshow_title\tseason_title\tcumulative_weeks_in_top_10\n"

_TSV_KR = (
    _TSV_HEADER
    + "KR\t2024-05-01\tfilms\t1\t기생충\t\t3\n"
    + "KR\t2024-05-01\tfilms\t2\t버닝\t\t1\n"
    + "US\t2024-05-01\tfilms\t1\tSome Movie\t\t5\n"
    + "KR\t2024-04-24\tfilms\t1\t올드보이\t\t2\n"
)

_TSV_MULTI_WEEK = (
    _TSV_HEADER
    + "KR\t2024-05-08\tfilms\t1\t아가씨\t\t1\n"
    + "KR\t2024-05-01\tfilms\t1\t기생충\t\t3\n"
)


def _mock_response(text: str, ok: bool = True):
    resp = MagicMock()
    resp.text = text
    if not ok:
        resp.raise_for_status.side_effect = Exception("HTTP error")
    else:
        resp.raise_for_status.return_value = None
    return resp


def test_kr_filter():
    with patch("api.distribution.ott.netflix.requests.get") as mock_get:
        mock_get.return_value = _mock_response(_TSV_KR)
        items = NetflixTudumSource().fetch_top()
    titles = [i.title for i in items]
    assert "기생충" in titles
    assert "버닝" in titles
    assert "Some Movie" not in titles  # US 제외


def test_latest_week_selected():
    with patch("api.distribution.ott.netflix.requests.get") as mock_get:
        mock_get.return_value = _mock_response(_TSV_MULTI_WEEK)
        items = NetflixTudumSource().fetch_top()
    # 최신 week(2024-05-08)의 아가씨만
    assert len(items) == 1
    assert items[0].title == "아가씨"


def test_empty_response_graceful():
    with patch("api.distribution.ott.netflix.requests.get") as mock_get:
        mock_get.return_value = _mock_response(_TSV_HEADER)  # 헤더만
        items = NetflixTudumSource().fetch_top()
    assert items == []


def test_missing_column_graceful():
    tsv = "week\trank\tshow_title\n2024-05-01\t1\t기생충\n"  # country_iso2 없음
    with patch("api.distribution.ott.netflix.requests.get") as mock_get:
        mock_get.return_value = _mock_response(tsv)
        items = NetflixTudumSource().fetch_top()
    assert items == []  # KR 필터 통과 row 없음


def test_http_failure_returns_empty():
    with patch("api.distribution.ott.netflix.requests.get") as mock_get:
        mock_get.side_effect = Exception("network error")
        items = NetflixTudumSource().fetch_top()
    assert items == []
