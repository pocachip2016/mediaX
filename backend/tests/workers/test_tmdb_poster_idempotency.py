"""
TMDB enrich 워커 ContentImage 적재 멱등성 테스트
동일 콘텐츠를 2회 호출해도 poster ContentImage 는 1건만 존재해야 한다.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.programming.metadata.models import (
    Content, ContentImage, ContentMetadata, ContentStatus, ContentType, ImageType,
)
from workers.tasks.metadata import _tmdb_search_and_save


def _make_content(db) -> Content:
    c = Content(
        title="테스트 영화",
        content_type=ContentType.movie,
        status=ContentStatus.processing,
        production_year=2024,
        cp_name="Test CP",
    )
    db.add(c)
    db.flush()
    meta = ContentMetadata(content_id=c.id, quality_score=0.0)
    db.add(meta)
    db.flush()
    return c


def _mock_response(json_data: dict) -> MagicMock:
    resp = MagicMock()
    resp.json = MagicMock(return_value=json_data)
    return resp


class _MockClient:
    """httpx.AsyncClient 대체 — search 1회, detail 1회만 응답"""

    def __init__(self, search_json: dict, detail_json: dict):
        self.search_json = search_json
        self.detail_json = detail_json
        self.call_count = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url: str, params=None):
        self.call_count += 1
        if "/search/" in url:
            return _mock_response(self.search_json)
        return _mock_response(self.detail_json)


def test_tmdb_poster_idempotent_double_call(db):
    """동일 콘텐츠에 enrich 2회 → ContentImage(image_type=poster) 1건만 존재"""
    content = _make_content(db)

    search_json = {"results": [{"id": 12345, "title": "테스트 영화"}]}
    detail_json = {
        "id": 12345,
        "title": "테스트 영화",
        "poster_path": "/abc123.jpg",
        "credits": {"cast": [], "crew": []},
    }

    def make_client(*args, **kwargs):
        return _MockClient(search_json, detail_json)

    with patch("workers.tasks.metadata.httpx.AsyncClient", side_effect=make_client):
        asyncio.run(_tmdb_search_and_save(content, db, api_key="FAKE_KEY"))
        asyncio.run(_tmdb_search_and_save(content, db, api_key="FAKE_KEY"))

    db.flush()
    images = (
        db.query(ContentImage)
        .filter(
            ContentImage.content_id == content.id,
            ContentImage.image_type == ImageType.poster,
        )
        .all()
    )
    assert len(images) == 1, f"멱등성 실패: {len(images)} 건 적재됨"
    assert images[0].source == "tmdb"
    assert images[0].is_primary is True
    assert "image.tmdb.org" in images[0].url


def test_tmdb_no_poster_path_skips_image(db):
    """detail.poster_path 가 없으면 ContentImage 미생성"""
    content = _make_content(db)

    search_json = {"results": [{"id": 12345}]}
    detail_json = {"id": 12345, "title": "x", "credits": {"cast": [], "crew": []}}

    def make_client(*args, **kwargs):
        return _MockClient(search_json, detail_json)

    with patch("workers.tasks.metadata.httpx.AsyncClient", side_effect=make_client):
        asyncio.run(_tmdb_search_and_save(content, db, api_key="FAKE_KEY"))

    db.flush()
    count = (
        db.query(ContentImage)
        .filter(ContentImage.content_id == content.id)
        .count()
    )
    assert count == 0
