"""KMDB poster URL 파싱 + _upsert_kmdb_movie 단위 테스트"""
import pytest

from workers.tasks.kmdb_cache import _split_pipe_urls, _upsert_kmdb_movie


# ── _split_pipe_urls ────────────────────────────────────────────────────────

class TestSplitPipeUrls:
    def test_pipe_separated(self):
        result = _split_pipe_urls("http://a.com/1.jpg|http://b.com/2.jpg")
        assert result == ["http://a.com/1.jpg", "http://b.com/2.jpg"]

    def test_single_url(self):
        result = _split_pipe_urls("http://a.com/1.jpg")
        assert result == ["http://a.com/1.jpg"]

    def test_none(self):
        assert _split_pipe_urls(None) == []

    def test_empty_string(self):
        assert _split_pipe_urls("") == []

    def test_strips_whitespace(self):
        result = _split_pipe_urls(" http://a.com/1.jpg | http://b.com/2.jpg ")
        assert result == ["http://a.com/1.jpg", "http://b.com/2.jpg"]

    def test_trailing_pipe(self):
        result = _split_pipe_urls("http://a.com/1.jpg|")
        assert result == ["http://a.com/1.jpg"]

    def test_non_string(self):
        # dict 타입 (버그 수정 이전 코드가 기대하던 잘못된 타입)
        assert _split_pipe_urls({"poster": []}) == []


# ── _upsert_kmdb_movie ──────────────────────────────────────────────────────

_SAMPLE_RAW = {
    "DOCID": "K|12345",
    "title": "테스트 영화",
    "titleEng": "Test Movie",
    "prodYear": "2023",
    "posters": "http://file.koreafilm.or.kr/thm/01.jpg|http://file.koreafilm.or.kr/thm/02.jpg",
    "stlls": "http://file.koreafilm.or.kr/stl/01.jpg|http://file.koreafilm.or.kr/stl/02.jpg|http://file.koreafilm.or.kr/stl/03.jpg",
    "plots": {"plot": [{"plotText": "줄거리 텍스트"}]},
    "directors": {"director": []},
    "actors": {"actor": []},
}


def test_upsert_insert_poster_urls(db):
    result = _upsert_kmdb_movie(db, _SAMPLE_RAW)
    db.commit()

    assert result == "inserted"

    from api.programming.metadata.models.kmdb_cache import KmdbMovieCache
    row = db.get(KmdbMovieCache, "K|12345")

    # 단일 poster_url (하위호환)
    assert row.poster_url == "http://file.koreafilm.or.kr/thm/01.jpg"

    # 다중 poster_urls
    assert row.poster_urls == [
        "http://file.koreafilm.or.kr/thm/01.jpg",
        "http://file.koreafilm.or.kr/thm/02.jpg",
    ]

    # stillcut_urls
    assert len(row.stillcut_urls) == 3


def test_upsert_idempotent_unchanged(db):
    _upsert_kmdb_movie(db, _SAMPLE_RAW)
    db.commit()

    result = _upsert_kmdb_movie(db, _SAMPLE_RAW)
    assert result == "unchanged"


def test_upsert_none_posters(db):
    raw = {**_SAMPLE_RAW, "DOCID": "K|00000", "posters": None, "stlls": None}
    _upsert_kmdb_movie(db, raw)
    db.commit()

    from api.programming.metadata.models.kmdb_cache import KmdbMovieCache
    row = db.get(KmdbMovieCache, "K|00000")

    assert row.poster_url is None
    assert row.poster_urls == []
    assert row.stillcut_urls == []
