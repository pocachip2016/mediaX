"""
Field Aggregator 단위 테스트

시나리오:
  A. director auto_agreement (TMDB+KMDb 동의)
  B. synopsis pending (C형 항상)
  C. poster quality_pick (D형 source_priority)
  D. B형 멤버 union cap
  E. E형 외부 ID upsert
  F. manual_pick 보존 (덮어쓰기 금지)
  G. 가드 미충족 → pending (단일 소스)
"""

import pytest
from api.meta_core.aggregator import aggregate_content, AggregateReport
from api.meta_core.models.intelligence import FieldSuggestion, FieldResolution
from api.programming.metadata.models.content import Content, ContentType, ContentStatus
from api.programming.metadata.models.external import ExternalMetaSource, ExternalSourceType
from api.programming.metadata.models.image import ContentImage, ImageType


# ── fixtures ──────────────────────────────────────────────────────────────────

def _content(db) -> Content:
    c = Content(title="기생충", content_type=ContentType.movie, status=ContentStatus.ai)
    db.add(c)
    db.flush()
    return c


def _sug(db, content_id, field_name, value, source_type, confidence=0.9) -> FieldSuggestion:
    s = FieldSuggestion(
        content_id=content_id,
        field_name=field_name,
        value_json=value,
        source_type=source_type,
        confidence=confidence,
        status="pending",
    )
    db.add(s)
    db.flush()
    return s


# ── A. director auto_agreement ────────────────────────────────────────────────

def test_director_auto_agreement(db):
    """TMDB(1.0) + KMDb(0.95) 같은 감독 → auto_agreement, applied=True."""
    c = _content(db)
    _sug(db, c.id, "director", "봉준호", "tmdb")
    _sug(db, c.id, "director", "봉준호", "kmdb")

    report = aggregate_content(c.id, db)

    res = db.query(FieldResolution).filter_by(content_id=c.id, field_name="director").first()
    assert res is not None
    assert res.decision == "auto_agreement"
    assert res.applied_to_content is True
    assert res.agreement_count == 2

    field_results = {f.field_name: f for f in report.fields}
    assert field_results["director"].applied is True


def test_director_single_source_pending(db):
    """단일 소스(TMDB만) → agree_count=1 < 2 → pending."""
    c = _content(db)
    _sug(db, c.id, "director", "봉준호", "tmdb")

    aggregate_content(c.id, db)

    res = db.query(FieldResolution).filter_by(content_id=c.id, field_name="director").first()
    assert res.decision == "pending"
    assert res.applied_to_content is False


# ── B. synopsis pending (C형) ─────────────────────────────────────────────────

def test_synopsis_pending(db):
    """C형 synopsis — 소스 수에 관계없이 항상 pending."""
    c = _content(db)
    _sug(db, c.id, "synopsis", "A" * 80, "tmdb")
    _sug(db, c.id, "synopsis", "B" * 80, "kmdb")
    _sug(db, c.id, "synopsis", "C" * 80, "kobis")

    report = aggregate_content(c.id, db)

    res = db.query(FieldResolution).filter_by(content_id=c.id, field_name="synopsis").first()
    assert res.decision == "pending"
    assert res.applied_to_content is False

    field_results = {f.field_name: f for f in report.fields}
    assert field_results["synopsis"].decision == "pending"


# ── C. poster quality_pick (D형) ─────────────────────────────────────────────

def test_poster_quality_pick(db):
    """D형 — source_priority 순으로 tmdb 우선 채택."""
    c = _content(db)
    _sug(db, c.id, "poster", "http://kmdb.or.kr/poster.jpg", "kmdb")
    _sug(db, c.id, "poster", "http://tmdb.org/poster.jpg", "tmdb")

    report = aggregate_content(c.id, db)

    res = db.query(FieldResolution).filter_by(content_id=c.id, field_name="poster").first()
    assert res.decision == "auto_quality"
    assert res.applied_to_content is True
    assert "tmdb" in res.agreeing_sources_json

    # ContentImage 생성 확인
    img = db.query(ContentImage).filter_by(content_id=c.id, is_primary=True).first()
    assert img is not None
    assert "tmdb" in img.url

    field_results = {f.field_name: f for f in report.fields}
    assert field_results["poster"].applied is True


# ── D. cast B형 멤버 union ────────────────────────────────────────────────────

def test_cast_union_auto(db):
    """B형 — 2개 소스에 등장한 멤버만 auto union."""
    c = _content(db)
    # 송강호 TMDB+KMDb → auto. 이선균 TMDB만 → 단일 소스 제외
    _sug(db, c.id, "cast", [{"name": "송강호"}, {"name": "이선균"}], "tmdb")
    _sug(db, c.id, "cast", [{"name": "송강호"}], "kmdb")

    aggregate_content(c.id, db)

    res = db.query(FieldResolution).filter_by(content_id=c.id, field_name="cast").first()
    assert res.decision == "auto_agreement"
    chosen = res.chosen_value_json
    assert "송강호" in chosen
    assert "이선균" not in chosen


def test_cast_cap_applied(db):
    """B형 cap=20: 21번째 멤버는 채택 안 됨."""
    c = _content(db)
    members_a = [{"name": f"배우{i}"} for i in range(21)]
    members_b = [{"name": f"배우{i}"} for i in range(21)]
    _sug(db, c.id, "cast", members_a, "tmdb")
    _sug(db, c.id, "cast", members_b, "kmdb")

    aggregate_content(c.id, db)

    res = db.query(FieldResolution).filter_by(content_id=c.id, field_name="cast").first()
    assert len(res.chosen_value_json) <= 20


# ── E. 외부 ID (E형) ──────────────────────────────────────────────────────────

def test_external_id_upsert(db):
    """E형 — tmdb/kmdb ID를 ExternalMetaSource에 upsert."""
    c = _content(db)
    _sug(db, c.id, "external_id", {"tmdb": 496243, "kmdb_docid": "K|W|00001"}, "tmdb")

    aggregate_content(c.id, db)

    sources = db.query(ExternalMetaSource).filter_by(content_id=c.id).all()
    src_types = {s.source_type for s in sources}
    assert ExternalSourceType.tmdb in src_types
    assert ExternalSourceType.kmdb in src_types

    res = db.query(FieldResolution).filter_by(content_id=c.id, field_name="external_id").first()
    assert res.decision == "auto_agreement"
    assert res.applied_to_content is True


# ── F. manual_pick 보존 ───────────────────────────────────────────────────────

def test_manual_pick_not_overwritten(db):
    """manual_pick 상태 FieldResolution → auto 재실행해도 덮어쓰기 금지."""
    c = _content(db)
    # 미리 manual_pick 확정
    manual_res = FieldResolution(
        content_id=c.id,
        field_name="director",
        decision="manual_pick",
        chosen_value_json="홍길동",
        chosen_suggestion_ids=[],
        agreement_count=1,
        agreeing_sources_json=["manual"],
        applied_to_content=True,
        decided_by="editor",
    )
    db.add(manual_res)
    db.flush()

    # 이번엔 TMDB+KMDb 가 다른 감독 제안
    _sug(db, c.id, "director", "봉준호", "tmdb")
    _sug(db, c.id, "director", "봉준호", "kmdb")

    aggregate_content(c.id, db)

    res = db.query(FieldResolution).filter_by(content_id=c.id, field_name="director").first()
    assert res.decision == "manual_pick"
    assert res.chosen_value_json == "홍길동"


# ── G. AggregateReport 카운트 ─────────────────────────────────────────────────

def test_aggregate_report_counts(db):
    c = _content(db)
    # auto: director (A, TMDB+KMDb)
    _sug(db, c.id, "director", "봉준호", "tmdb")
    _sug(db, c.id, "director", "봉준호", "kmdb")
    # pending: synopsis (C)
    _sug(db, c.id, "synopsis", "줄거리", "tmdb")

    report = aggregate_content(c.id, db)

    assert report.auto_applied == 1
    assert report.pending == 1
