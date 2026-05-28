"""
Step 2 검증 — OttSection + fetch_sections + Watcha 파싱 (mock)
"""
from unittest.mock import MagicMock, patch

import pytest

from api.distribution.ott.base import OttItem, OttSection, OttSource
from api.distribution.ott.watcha import WatchaTopSource, _infer_category_type


# ── OttSection 구조 ──────────────────────────────────────────────────────────

def test_ott_section_fields():
    section = OttSection(
        section_id="ott_watcha:top",
        name="이번 주 TOP10",
        category_type="ranking",
        items=[OttItem(title="기생충", rank=1)],
    )
    assert section.section_id == "ott_watcha:top"
    assert section.name == "이번 주 TOP10"
    assert section.category_type == "ranking"
    assert len(section.items) == 1


def test_ott_section_empty_items_default():
    section = OttSection(section_id="x:y", name="테스트", category_type="recommendation")
    assert section.items == []


# ── OttSource.fetch_sections 기본 구현 ──────────────────────────────────────

class _DummySource(OttSource):
    channel = "ott_dummy"

    def fetch_top(self, limit: int = 20) -> list[OttItem]:
        return [OttItem(title="영화A", rank=1), OttItem(title="영화B", rank=2)]


def test_default_fetch_sections_wraps_fetch_top():
    src = _DummySource()
    sections = src.fetch_sections()
    assert len(sections) == 1
    assert sections[0].section_id == "ott_dummy:top"
    assert sections[0].name == "TOP"
    assert sections[0].category_type == "ranking"
    assert len(sections[0].items) == 2


def test_default_fetch_sections_empty_fetch_top():
    class _EmptySource(_DummySource):
        def fetch_top(self, limit=20):
            return []

    sections = _EmptySource().fetch_sections()
    assert len(sections) == 1
    assert sections[0].items == []


# ── _infer_category_type 헬퍼 ────────────────────────────────────────────────

@pytest.mark.parametrize("name,expected", [
    ("이번 주 TOP10", "ranking"),
    ("TOP 랭킹", "ranking"),
    ("신작 추천", "recommendation"),
    ("지금 뜨는 NEW", "recommendation"),
    ("오늘의 추천", "recommendation"),
    ("장르 - 코미디", "genre"),
    ("로맨스 genre", "genre"),
    ("모르는섹션", "recommendation"),  # 기본값
])
def test_infer_category_type(name, expected):
    assert _infer_category_type(name) == expected


# ── WatchaTopSource.fetch_sections (mock HTML) ───────────────────────────────

_WATCHA_HTML_WITH_SECTIONS = """
<html><body>
  <section>
    <h2>이번 주 TOP10</h2>
    <div>
      <a href="/ko/contents/abc123">기생충</a>
      <a href="/ko/contents/def456">버닝</a>
    </div>
  </section>
  <section>
    <h2>신작 추천</h2>
    <div>
      <a href="/ko/contents/ghi789">오펜하이머</a>
    </div>
  </section>
</body></html>
"""

_WATCHA_HTML_NO_HEADINGS = """
<html><body>
  <a href="/ko/contents/abc123">기생충</a>
  <a href="/ko/contents/def456">버닝</a>
</body></html>
"""


def test_watcha_fetch_sections_with_headings():
    src = WatchaTopSource()
    with patch.object(src, "_get_soup", return_value=__import__(
        "bs4", fromlist=["BeautifulSoup"]
    ).BeautifulSoup(_WATCHA_HTML_WITH_SECTIONS, "html.parser")):
        sections = src.fetch_sections()

    assert len(sections) == 2
    names = [s.name for s in sections]
    assert "이번 주 TOP10" in names
    assert "신작 추천" in names

    top10 = next(s for s in sections if s.name == "이번 주 TOP10")
    assert top10.category_type == "ranking"
    assert len(top10.items) == 2
    assert top10.items[0].title == "기생충"

    new_section = next(s for s in sections if s.name == "신작 추천")
    assert new_section.category_type == "recommendation"
    assert len(new_section.items) == 1


def test_watcha_fetch_sections_fallback_no_headings():
    src = WatchaTopSource()
    with patch.object(src, "_get_soup", return_value=__import__(
        "bs4", fromlist=["BeautifulSoup"]
    ).BeautifulSoup(_WATCHA_HTML_NO_HEADINGS, "html.parser")):
        sections = src.fetch_sections()

    assert len(sections) == 1
    assert sections[0].section_id == "ott_watcha:top"
    assert sections[0].name == "TOP"
    assert len(sections[0].items) == 2


def test_watcha_fetch_sections_http_fail():
    src = WatchaTopSource()
    with patch.object(src, "_get_soup", return_value=None):
        sections = src.fetch_sections()
    assert sections == []


def test_watcha_fetch_sections_section_ids_unique():
    src = WatchaTopSource()
    from bs4 import BeautifulSoup
    with patch.object(src, "_get_soup", return_value=BeautifulSoup(
        _WATCHA_HTML_WITH_SECTIONS, "html.parser"
    )):
        sections = src.fetch_sections()

    ids = [s.section_id for s in sections]
    assert len(ids) == len(set(ids)), "section_id가 중복됨"
