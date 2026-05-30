"""
enrich_content 단위 테스트 — 외부 HTTP 호출을 monkeypatch 로 차단

시나리오:
  1. TMDB 키 없음 → sources_skipped 에 "tmdb:no_key"
  2. KMDb 키 없음 → sources_skipped 에 "kmdb:no_key"
  3. TMDB 결과 있음 → candidate + edge + suggestion 생성
  4. KMDb 결과 있음 → candidate + edge + suggestion 생성
  5. 갭 없는 콘텐츠 → 아무것도 생성 안 함
  6. candidate upsert 중복 제거
  7. KMDb raw dict 파싱 확인
"""

import pytest
from unittest.mock import MagicMock, patch

from api.meta_core.enrich import enrich_content, _upsert_candidate, _parse_candidate_fields, _needed_sources, _fetch_tmdb
from api.meta_core.models.intelligence import MetadataCandidate, MatchEdge, FieldSuggestion
from api.programming.metadata.models.content import Content, ContentType, ContentStatus, ContentMetadata
from api.programming.metadata.models.external import ExternalMetaSource, ExternalSourceType
from api.programming.metadata.models.image import ContentImage, ImageType
from api.programming.metadata.models.person import ContentCredit, CreditRole, PersonMaster
from api.programming.metadata.models.taxonomy import ContentGenre


# ── fixtures ──────────────────────────────────────────────────────────────────

def _content(db, title="기생충", year=2019) -> Content:
    c = Content(title=title, content_type=ContentType.movie,
                status=ContentStatus.ai, production_year=year)
    db.add(c)
    db.flush()
    return c


_TMDB_RAW = {
    "id": 496243,
    "title": "기생충",
    "original_title": "Parasite",
    "release_date": "2019-05-30",
    "overview": "A" * 80,
    "poster_path": "/some_poster.jpg",
}

_KMDB_RAW = {
    "DOCID": "K|W|00001",
    "title": "기생충",
    "titleEng": "Parasite",
    "prodYear": "2019",
    "genre": "드라마,스릴러",
    "directors": {"director": [{"directorNm": "봉준호"}]},
    "actors": {"actor": [{"actorNm": "송강호"}, {"actorNm": "이선균"}]},
    "plots": {"plot": [{"plotText": "A" * 80}]},
}


# ── helpers ───────────────────────────────────────────────────────────────────

def _no_keys(settings_mock):
    settings_mock.TMDB_API_KEY = ""
    settings_mock.KMDB_API_KEY = ""


# ── 1. 키 없음 → skip ─────────────────────────────────────────────────────────

def test_no_tmdb_key_skipped(db):
    c = _content(db)
    with patch("api.meta_core.enrich.settings") as s:
        s.TMDB_API_KEY = ""
        s.KMDB_API_KEY = ""
        result = enrich_content(c.id, db)

    assert "tmdb:no_key" in result.sources_skipped
    assert "kmdb:no_key" in result.sources_skipped
    assert result.candidates_upserted == 0


def test_no_kmdb_key_skipped(db):
    c = _content(db)
    with patch("api.meta_core.enrich.settings") as s:
        s.TMDB_API_KEY = "fake_key"
        s.KMDB_API_KEY = ""
        with patch("api.meta_core.enrich._fetch_tmdb", return_value=None):
            result = enrich_content(c.id, db)

    assert "kmdb:no_key" in result.sources_skipped


# ── 2. TMDB 결과 있음 → candidate/edge/suggestion ────────────────────────────

def test_tmdb_hit_creates_candidate_and_suggestions(db):
    c = _content(db)
    with patch("api.meta_core.enrich.settings") as s:
        s.TMDB_API_KEY = "fake_key"
        s.KMDB_API_KEY = ""
        with patch("api.meta_core.enrich._fetch_tmdb", return_value=_TMDB_RAW):
            result = enrich_content(c.id, db)

    assert result.candidates_upserted == 1
    assert result.match_edges_created == 1
    assert result.suggestions_created > 0
    assert "tmdb" in result.sources_hit

    candidates = db.query(MetadataCandidate).all()
    assert len(candidates) == 1
    assert candidates[0].source_type == "tmdb"

    suggestions = db.query(FieldSuggestion).filter(FieldSuggestion.content_id == c.id).all()
    field_names = {s2.field_name for s2 in suggestions}
    assert "synopsis" in field_names
    assert "poster" in field_names


# ── 3. KMDb 결과 있음 → candidate/edge/suggestion ────────────────────────────

def test_kmdb_hit_creates_candidate_and_suggestions(db):
    c = _content(db)
    with patch("api.meta_core.enrich.settings") as s:
        s.TMDB_API_KEY = ""
        s.KMDB_API_KEY = "fake_kmdb_key"
        with patch("api.meta_core.clients.kmdb_client.httpx.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"Data": [{"Result": [_KMDB_RAW]}]}
            mock_resp.raise_for_status.return_value = None
            mock_get.return_value = mock_resp

            result = enrich_content(c.id, db)

    assert result.candidates_upserted >= 1
    assert "kmdb" in result.sources_hit

    candidates = db.query(MetadataCandidate).all()
    assert any(c2.source_type == "kmdb" for c2 in candidates)

    suggestions = db.query(FieldSuggestion).filter(FieldSuggestion.content_id == c.id).all()
    field_names = {s2.field_name for s2 in suggestions}
    assert "director" in field_names
    assert "cast" in field_names


# ── 4. 갭 없는 콘텐츠 → 아무것도 생성 안 함 ──────────────────────────────────

def _populate_all(db, c: Content):
    db.add(ExternalMetaSource(content_id=c.id, source_type=ExternalSourceType.tmdb, external_id="1"))
    db.add(ContentImage(content_id=c.id, image_type=ImageType.poster,
                        url="http://example.com/p.jpg", is_primary=True))
    db.add(ContentMetadata(content_id=c.id, cp_synopsis="A" * 60))
    p1 = PersonMaster(name_ko="배우"); db.add(p1); db.flush()
    p2 = PersonMaster(name_ko="감독"); db.add(p2); db.flush()
    db.add(ContentCredit(content_id=c.id, person_id=p1.id, role=CreditRole.actor))
    db.add(ContentCredit(content_id=c.id, person_id=p2.id, role=CreditRole.director))
    db.add(ContentGenre(content_id=c.id, genre_id=1, is_primary=True))
    db.flush()


def test_no_gap_skips_enrich(db):
    c = _content(db)
    _populate_all(db, c)
    with patch("api.meta_core.enrich.settings") as s:
        s.TMDB_API_KEY = "fake_key"
        s.KMDB_API_KEY = "fake_kmdb"
        result = enrich_content(c.id, db)

    assert result.candidates_upserted == 0
    assert result.match_edges_created == 0
    assert result.suggestions_created == 0


# ── 5. candidate upsert 중복 처리 ────────────────────────────────────────────

def test_upsert_candidate_deduplicates(db):
    raw1 = {**_TMDB_RAW}
    raw2 = {**_TMDB_RAW, "overview": "Updated overview"}

    c1 = _upsert_candidate(db, ExternalSourceType.tmdb, raw1)
    c2 = _upsert_candidate(db, ExternalSourceType.tmdb, raw2)

    assert c1.id == c2.id
    assert len(db.query(MetadataCandidate).all()) == 1


# ── 7. content_type-aware 라우팅 ──────────────────────────────────────────────

def test_needed_sources_tv_drops_kmdb_kobis():
    """series/season/episode gap_report 에서 kmdb·kobis 는 제거돼야 한다."""
    from dataclasses import dataclass, field as dc_field

    @dataclass
    class FakeGap:
        recommended_sources: list

    @dataclass
    class FakeReport:
        content_type: str
        missing_fields: list

    report_series = FakeReport(
        content_type="series",
        missing_fields=[FakeGap(["tmdb", "kmdb", "kobis"])],
    )
    sources = _needed_sources(report_series)
    assert "kmdb" not in sources
    assert "kobis" not in sources
    assert "tmdb" in sources

    report_episode = FakeReport(
        content_type="episode",
        missing_fields=[FakeGap(["tmdb", "kmdb"])],
    )
    sources_ep = _needed_sources(report_episode)
    assert "kmdb" not in sources_ep
    assert "tmdb" in sources_ep


def test_fetch_tmdb_episode_uses_tv_endpoint(db):
    """episode content 는 /search/tv 를 호출하고 series 조상의 타이틀을 사용한다."""
    series = Content(title="오징어 게임", content_type=ContentType.series, production_year=2021)
    db.add(series); db.flush()
    season = Content(title="오징어 게임 시즌1", content_type=ContentType.season, parent_id=series.id)
    db.add(season); db.flush()
    episode = Content(title="오징어 게임 E01", content_type=ContentType.episode, parent_id=season.id)
    db.add(episode); db.flush()

    captured_url = {}

    def mock_get(url, params=None, timeout=None):
        captured_url["url"] = url
        captured_url["query"] = (params or {}).get("query")
        resp = MagicMock()
        resp.json.return_value = {"results": []}
        return resp

    with patch("api.meta_core.enrich.httpx.get", side_effect=mock_get):
        _fetch_tmdb(episode, "fake_key", db)

    assert "/search/tv" in captured_url["url"], f"Expected /search/tv, got {captured_url['url']}"
    assert captured_url["query"] == "오징어 게임", f"Expected series title, got {captured_url['query']}"


def test_fetch_tmdb_movie_uses_movie_endpoint(db):
    """movie content 는 /search/movie 를 호출한다."""
    movie = Content(title="기생충", content_type=ContentType.movie, production_year=2019)
    db.add(movie); db.flush()

    captured_url = {}

    def mock_get(url, params=None, timeout=None):
        captured_url["url"] = url
        resp = MagicMock()
        resp.json.return_value = {"results": []}
        return resp

    with patch("api.meta_core.enrich.httpx.get", side_effect=mock_get):
        _fetch_tmdb(movie, "fake_key", db)

    assert "/search/movie" in captured_url["url"]


# ── 6. parse_candidate_fields — KMDb 파싱 ────────────────────────────────────

def test_parse_kmdb_fields():
    parsed = _parse_candidate_fields(ExternalSourceType.kmdb, _KMDB_RAW)
    assert parsed["title_norm"] == "기생충"
    assert parsed["year"] == 2019
    assert any(d["name"] == "봉준호" for d in parsed["director_json"])
    assert any(a["name"] == "송강호" for a in parsed["cast_json"])
    assert "드라마" in parsed["genre_json"]
