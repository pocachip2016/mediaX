"""
dev-rag-field-extract Step 3 — reference_extract 로직 + 엔드포인트 테스트

가드:
  - Wikidata/Wikipedia 클라이언트 mock → ExternalMetaSource(wikidata/wikipedia) upsert
  - status 불변 확인
  - 소스 실패 시 sources_skipped 처리
  - 404 케이스 (content not found)
  - 동일 content_id 재호출 → upsert (중복 없음)

pytest tests/test_reference_extract.py -q
"""
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import api.programming.metadata.models          # noqa: F401
import api.meta_core.models                     # noqa: F401
import api.meta_core.public_api.models          # noqa: F401
import api.distribution.models                  # noqa: F401
from shared.database import Base, get_db
from main import app

from api.programming.metadata.models import Content, ContentMetadata, ContentStatus, ContentType
from api.programming.metadata.models.external import ExternalMetaSource, ExternalSourceType
from api.meta_core.reference_extract import reference_extract

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(bind=_engine)

_WD_FACTS = {"directors": ["봉준호"], "country": "대한민국", "genres": ["드라마"]}
_WP_RESULT = {"text": "기생충(Parasite)는 ...", "url": "https://ko.wikipedia.org/wiki/기생충", "lang": "ko"}


@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(_engine)

    def override():
        d = _Session()
        try:
            yield d
        finally:
            d.close()

    app.dependency_overrides[get_db] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    Base.metadata.drop_all(_engine)


@pytest.fixture
def db(client):
    session = _Session()
    yield session
    session.rollback()
    session.close()


def _make(db, title="기생충", year=2019, status=ContentStatus.raw):
    c = Content(title=title, content_type=ContentType.movie, cp_name="TEST_RAG",
                status=status, production_year=year)
    db.add(c)
    db.flush()
    db.add(ContentMetadata(content_id=c.id, quality_score=0.0))
    db.flush()
    return c


# ── reference_extract 서비스 직접 테스트 ─────────────────────────────────────

def test_reference_extract_both_hit(db):
    """Wikidata + Wikipedia 모두 성공 → sources_hit 2건, ExternalMetaSource 2건 upsert."""
    c = _make(db)
    db.commit()

    with patch("api.meta_core.reference_extract.WikidataClient") as MockWD, \
         patch("api.meta_core.reference_extract.WikipediaClient") as MockWP:
        MockWD.return_value.fetch_facts.return_value = {**_WD_FACTS, "_url": "https://wikidata.org/wiki/Q1"}
        MockWP.return_value.fetch.return_value = _WP_RESULT

        result = reference_extract(c.id, db)

    assert set(result.sources_hit) == {"wikidata", "wikipedia"}
    assert result.sources_skipped == []
    assert result.wikidata_facts == _WD_FACTS
    assert result.wikipedia_text == _WP_RESULT["text"]

    sources = db.query(ExternalMetaSource).filter(ExternalMetaSource.content_id == c.id).all()
    types = {s.source_type for s in sources}
    assert ExternalSourceType.wikidata in types
    assert ExternalSourceType.wikipedia in types


def test_reference_extract_status_unchanged(db):
    """reference_extract 실행 후 content status 불변."""
    c = _make(db, status=ContentStatus.enriched)
    db.commit()

    with patch("api.meta_core.reference_extract.WikidataClient") as MockWD, \
         patch("api.meta_core.reference_extract.WikipediaClient") as MockWP:
        MockWD.return_value.fetch_facts.return_value = {**_WD_FACTS}
        MockWP.return_value.fetch.return_value = _WP_RESULT

        reference_extract(c.id, db)

    db.refresh(c)
    assert c.status == ContentStatus.enriched


def test_reference_extract_wikidata_empty(db):
    """Wikidata 결과 없을 때 wikidata sources_skipped, wikipedia는 정상."""
    c = _make(db, title="알수없는영화")
    db.commit()

    with patch("api.meta_core.reference_extract.WikidataClient") as MockWD, \
         patch("api.meta_core.reference_extract.WikipediaClient") as MockWP:
        MockWD.return_value.fetch_facts.return_value = {}
        MockWP.return_value.fetch.return_value = _WP_RESULT

        result = reference_extract(c.id, db)

    assert "wikidata" in result.sources_skipped
    assert "wikipedia" in result.sources_hit


def test_reference_extract_upsert_idempotent(db):
    """동일 content_id 두 번 호출해도 ExternalMetaSource 중복 없음."""
    c = _make(db, title="부산행")
    db.commit()

    with patch("api.meta_core.reference_extract.WikidataClient") as MockWD, \
         patch("api.meta_core.reference_extract.WikipediaClient") as MockWP:
        MockWD.return_value.fetch_facts.return_value = {**_WD_FACTS}
        MockWP.return_value.fetch.return_value = _WP_RESULT

        reference_extract(c.id, db)
        reference_extract(c.id, db)

    count = db.query(ExternalMetaSource).filter(
        ExternalMetaSource.content_id == c.id,
        ExternalMetaSource.source_type == ExternalSourceType.wikidata,
    ).count()
    assert count == 1


# ── 엔드포인트 테스트 ──────────────────────────────────────────────────────────

def test_endpoint_404(client):
    """존재하지 않는 content_id → 404."""
    res = client.post("/api/test/pipeline/reference-extract", json={"content_id": 99999})
    assert res.status_code == 404


def test_endpoint_success(client, db):
    """엔드포인트 정상 호출 → 200 + 스키마 확인."""
    c = _make(db, title="올드보이", year=2003)
    db.commit()

    with patch("api.meta_core.reference_extract.WikidataClient") as MockWD, \
         patch("api.meta_core.reference_extract.WikipediaClient") as MockWP:
        MockWD.return_value.fetch_facts.return_value = {**_WD_FACTS, "_url": "https://wikidata.org/wiki/Q2"}
        MockWP.return_value.fetch.return_value = _WP_RESULT

        res = client.post("/api/test/pipeline/reference-extract", json={"content_id": c.id})

    assert res.status_code == 200
    data = res.json()
    assert data["content_id"] == c.id
    assert "wikidata" in data["sources_hit"]
    assert "wikipedia" in data["sources_hit"]
    assert isinstance(data["wikidata_facts"], dict)
    assert data["wikipedia_text"] is not None


def test_endpoint_no_title(client, db):
    """제목 없는 콘텐츠 → 200 + sources_skipped 2건."""
    c = Content(title="", content_type=ContentType.movie, cp_name="TEST_RAG",
                status=ContentStatus.raw)
    db.add(c)
    db.flush()
    db.add(ContentMetadata(content_id=c.id, quality_score=0.0))
    db.commit()

    res = client.post("/api/test/pipeline/reference-extract", json={"content_id": c.id})
    assert res.status_code == 200
    data = res.json()
    assert set(data["sources_skipped"]) == {"wikidata", "wikipedia"}
    assert data["sources_hit"] == []
