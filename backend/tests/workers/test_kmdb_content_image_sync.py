"""sync_kmdb_poster_to_content_images 단위 테스트"""
import pytest

from api.programming.metadata.models import ContentImage, ImageType
from api.programming.metadata.models.external import ExternalMetaSource, ExternalSourceType
from api.programming.metadata.models.kmdb_cache import KmdbMovieCache
from api.programming.metadata.models.content import Content, ContentType, ContentStatus


def _make_content(db, content_id: int, title: str = "테스트 영화") -> Content:
    c = Content(id=content_id, title=title, content_type=ContentType.movie,
                status=ContentStatus.ai)
    db.add(c)
    db.flush()
    return c


def _make_kmdb_cache(db, docid: str, poster_urls: list, stillcut_urls: list) -> KmdbMovieCache:
    cache = KmdbMovieCache(
        docid=docid,
        title="테스트 영화",
        poster_url=poster_urls[0] if poster_urls else None,
        poster_urls=poster_urls,
        stillcut_urls=stillcut_urls,
        raw_json={"DOCID": docid},
    )
    db.add(cache)
    db.flush()
    return cache


def _link(db, content_id: int, docid: str) -> None:
    db.add(ExternalMetaSource(
        content_id=content_id,
        source_type=ExternalSourceType.kmdb,
        external_id=docid,
    ))
    db.flush()


def _run_sync(db):
    """태스크를 DB 픽스처 세션에서 직접 실행 (Celery 없이)."""
    from workers.tasks.kmdb_cache import sync_kmdb_poster_to_content_images
    from unittest.mock import patch
    # SessionLocal을 테스트 db 세션으로 교체
    with patch("workers.tasks.kmdb_cache.SessionLocal", return_value=db):
        return sync_kmdb_poster_to_content_images()


# ── 테스트 케이스 ────────────────────────────────────────────────────────────

class TestSyncKmdbPosterToContentImages:
    def test_poster_urls_inserted(self, db):
        """poster_urls가 있는 캐시 → ContentImage(poster) 정상 삽입."""
        _make_content(db, 1)
        _make_kmdb_cache(db, "K|001",
                         poster_urls=["http://a.com/1.jpg", "http://a.com/2.jpg"],
                         stillcut_urls=[])
        _link(db, 1, "K|001")
        db.commit()

        _run_sync(db)

        images = db.query(ContentImage).filter(
            ContentImage.content_id == 1,
            ContentImage.image_type == ImageType.poster,
        ).all()
        assert len(images) == 2
        urls = {img.url for img in images}
        assert "http://a.com/1.jpg" in urls
        assert "http://a.com/2.jpg" in urls
        assert all(img.source == "kmdb" for img in images)

    def test_first_poster_is_primary_when_no_existing(self, db):
        """기존 is_primary poster가 없으면 첫 번째 URL이 is_primary=True."""
        _make_content(db, 2)
        _make_kmdb_cache(db, "K|002",
                         poster_urls=["http://a.com/1.jpg", "http://a.com/2.jpg"],
                         stillcut_urls=[])
        _link(db, 2, "K|002")
        db.commit()

        _run_sync(db)

        primary = db.query(ContentImage).filter(
            ContentImage.content_id == 2,
            ContentImage.image_type == ImageType.poster,
            ContentImage.is_primary == True,  # noqa: E712
        ).all()
        assert len(primary) == 1
        assert primary[0].url == "http://a.com/1.jpg"

    def test_first_poster_not_primary_when_existing_primary(self, db):
        """이미 is_primary=True poster가 있으면 KMDB 첫 URL도 is_primary=False."""
        _make_content(db, 3)
        db.add(ContentImage(content_id=3, image_type=ImageType.poster,
                            url="http://existing.com/p.jpg", source="tmdb", is_primary=True))
        _make_kmdb_cache(db, "K|003",
                         poster_urls=["http://a.com/1.jpg"],
                         stillcut_urls=[])
        _link(db, 3, "K|003")
        db.commit()

        _run_sync(db)

        kmdb_images = db.query(ContentImage).filter(
            ContentImage.content_id == 3,
            ContentImage.source == "kmdb",
        ).all()
        assert len(kmdb_images) == 1
        assert kmdb_images[0].is_primary is False

    def test_idempotent_rerun(self, db):
        """동일 태스크 2번 실행 → 중복 없음."""
        _make_content(db, 4)
        _make_kmdb_cache(db, "K|004",
                         poster_urls=["http://a.com/1.jpg"],
                         stillcut_urls=["http://s.com/s1.jpg"])
        _link(db, 4, "K|004")
        db.commit()

        _run_sync(db)
        _run_sync(db)

        posters = db.query(ContentImage).filter(
            ContentImage.content_id == 4,
            ContentImage.image_type == ImageType.poster,
        ).count()
        stillcuts = db.query(ContentImage).filter(
            ContentImage.content_id == 4,
            ContentImage.image_type == ImageType.stillcut,
        ).count()
        assert posters == 1
        assert stillcuts == 1

    def test_stillcut_urls_inserted(self, db):
        """stillcut_urls → ImageType.stillcut 로 삽입."""
        _make_content(db, 5)
        _make_kmdb_cache(db, "K|005",
                         poster_urls=[],
                         stillcut_urls=["http://s.com/s1.jpg", "http://s.com/s2.jpg"])
        _link(db, 5, "K|005")
        db.commit()

        _run_sync(db)

        stillcuts = db.query(ContentImage).filter(
            ContentImage.content_id == 5,
            ContentImage.image_type == ImageType.stillcut,
        ).all()
        assert len(stillcuts) == 2
        assert all(img.source == "kmdb" for img in stillcuts)
        assert all(img.is_primary is False for img in stillcuts)

    def test_no_external_meta_source_skipped(self, db):
        """ExternalMetaSource 없는 캐시(링크 안 된 것) → ContentImage 없음."""
        _make_kmdb_cache(db, "K|006",
                         poster_urls=["http://a.com/1.jpg"],
                         stillcut_urls=[])
        # _link 미호출
        db.commit()

        _run_sync(db)

        count = db.query(ContentImage).count()
        assert count == 0

    def test_empty_poster_and_stillcut_skipped(self, db):
        """poster_urls=[], stillcut_urls=[] → ContentImage 없음."""
        _make_content(db, 7)
        _make_kmdb_cache(db, "K|007", poster_urls=[], stillcut_urls=[])
        _link(db, 7, "K|007")
        db.commit()

        result = _run_sync(db)

        assert result["posters_added"] == 0
        assert result["stillcuts_added"] == 0
        count = db.query(ContentImage).filter(ContentImage.content_id == 7).count()
        assert count == 0
