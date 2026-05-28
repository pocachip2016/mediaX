"""
dev-curation-workbench Step 8 — external curation backfill 테스트

검증 범위:
1. curation_runner: resolve 매칭/미매칭 처리
2. external-references: 영속 데이터 읽기 vs live 폴백
3. match-contents: external_content_ids 보너스
4. _external_score: content_id 정확 매칭 우선순위
"""
from unittest.mock import MagicMock, patch

import pytest

from api.distribution.curation_matcher import _external_score, match_contents
from api.distribution.models import ExternalCuration, ExternalCurationItem
from api.distribution.ott.base import OttItem, OttSection


# ── _external_score 확장 테스트 ───────────────────────────────────────────────

class TestExternalScoreExtended:
    def test_content_id_exact_match(self):
        score = _external_score("아무제목", set(), content_id=42, external_content_ids={42, 99})
        assert score == 1.0

    def test_content_id_not_in_set(self):
        score = _external_score("아무제목", set(), content_id=1, external_content_ids={42, 99})
        assert score == 0.0

    def test_title_fallback_when_no_content_ids(self):
        score = _external_score("파묘", {"파묘"}, content_id=None, external_content_ids=None)
        assert score == 1.0

    def test_content_id_match_combined_with_title_match(self):
        # content_id 일치 → 1.0 (title도 일치해도 동일 결과)
        score = _external_score("파묘", {"파묘"}, content_id=1, external_content_ids={1, 2})
        assert score == 1.0

    def test_no_external_info_returns_zero(self):
        assert _external_score("영화", set(), content_id=None, external_content_ids=None) == 0.0


# ── curation_runner 테스트 ────────────────────────────────────────────────────

class TestCurationRunner:
    def _make_source(self, channel: str, sections: list[OttSection]):
        src = MagicMock()
        src.channel = channel
        src.fetch_sections.return_value = sections
        return src

    def _make_db(self, existing_row=None):
        db = MagicMock()
        q = MagicMock()
        db.query.return_value = q
        q.filter.return_value = q
        q.first.return_value = existing_row
        return db

    def test_new_section_created(self):
        from api.distribution.ott.curation_runner import run_curation_source

        items = [OttItem(title="파묘", rank=1, production_year=2024)]
        sections = [OttSection(section_id="watcha:top", name="TOP10", category_type="ranking", items=items)]
        source = self._make_source("ott_watcha", sections)

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        db.query.return_value.filter.return_value.delete.return_value = 0

        with patch("api.distribution.ott.curation_runner.match_content", return_value=42):
            summary = run_curation_source(db, source)

        assert summary.sections == 1
        assert summary.items_total == 1
        assert summary.items_resolved == 1
        assert summary.errors == []

    def test_unresolved_item_stored_with_null_content_id(self):
        from api.distribution.ott.curation_runner import run_curation_source

        items = [OttItem(title="미매칭작품", rank=1, production_year=2020)]
        sections = [OttSection(section_id="watcha:new", name="신작", category_type="new_release", items=items)]
        source = self._make_source("ott_watcha", sections)

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        db.query.return_value.filter.return_value.delete.return_value = 0

        with patch("api.distribution.ott.curation_runner.match_content", return_value=None):
            summary = run_curation_source(db, source)

        assert summary.items_total == 1
        assert summary.items_resolved == 0

    def test_fetch_sections_failure_returns_empty_summary(self):
        from api.distribution.ott.curation_runner import run_curation_source

        source = MagicMock()
        source.channel = "ott_watcha"
        source.fetch_sections.side_effect = RuntimeError("크롤링 실패")

        db = MagicMock()
        summary = run_curation_source(db, source)

        assert summary.sections == 0
        assert len(summary.errors) == 1

    def test_existing_section_items_replaced(self):
        from api.distribution.ott.curation_runner import run_curation_source

        existing = MagicMock(spec=ExternalCuration)
        existing.id = 1
        existing.matched_count = 0

        items = [OttItem(title="파묘", rank=1, production_year=2024)]
        sections = [OttSection(section_id="watcha:top", name="TOP10", category_type="ranking", items=items)]
        source = self._make_source("ott_watcha", sections)

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = existing
        db.query.return_value.filter.return_value.delete.return_value = 3  # 기존 3건 삭제

        with patch("api.distribution.ott.curation_runner.match_content", return_value=42):
            summary = run_curation_source(db, source)

        assert summary.items_resolved == 1


# ── match_contents external_content_ids 통합 테스트 ──────────────────────────

class TestMatchContentsExtendedBonus:
    def _make_content(self, content_id: int, title: str):
        content = MagicMock()
        content.id = content_id
        content.title = title
        content.is_deleted = False
        content.content_type = MagicMock()
        content.content_type.value = "movie"
        content.production_year = 2023
        content.runtime_minutes = 100
        content.genres = []
        content.metadata_record = None
        return content

    def test_external_content_id_gives_bonus(self):
        c1 = self._make_content(1, "파묘")
        c2 = self._make_content(2, "서울의봄")

        db = MagicMock()
        db.query.return_value.filter.return_value.options.return_value.all.return_value = [c1, c2]

        results = match_contents(
            db,
            theme_features={},
            external_content_ids={1},
            limit=10,
        )
        # content_id=1(파묘)이 외부 참고 보너스로 상위에 있어야 함
        assert results[0].content_id == 1
        assert results[0].score_breakdown.get("external", 0.0) == 1.0

    def test_no_external_ids_no_bonus(self):
        c1 = self._make_content(1, "파묘")

        db = MagicMock()
        db.query.return_value.filter.return_value.options.return_value.all.return_value = [c1]

        results = match_contents(db, theme_features={}, limit=10)
        assert results[0].score_breakdown.get("external", 0.0) == 0.0
