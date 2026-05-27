"""
KMDB 캐시 Celery 태스크

태스크 목록:
  - backfill_kmdb                       : 연도별 슬라이싱 백필 (idempotent)
  - kmdb_quota_backfill_tick            : quota-aware Beat 트리거
  - sync_kmdb_poster_to_content_images  : KMDB poster/stillcut → content_images (07:15 KST Beat)

헬퍼:
  - _upsert_kmdb_movie       : KMDB Result dict → kmdb_movie_cache upsert
"""

import logging
import uuid
from datetime import datetime
from typing import Literal

from celery import shared_task

from shared.database import SessionLocal

logger = logging.getLogger(__name__)


def _split_pipe_urls(value) -> list:
    """KMDB pipe-separated URL string → list[str]. 빈 입력·None 안전."""
    if not value or not isinstance(value, str):
        return []
    return [u.strip() for u in value.split("|") if u.strip()]


# ── upsert 헬퍼 ────────────────────────────────────────────────────────────────

def _upsert_kmdb_movie(db, raw: dict) -> Literal["inserted", "updated", "unchanged"]:
    """KMDB Result 딕셔너리 → kmdb_movie_cache upsert.

    변경 감지 기준: title / poster_url / synopsis 중 하나라도 달라지면 'updated'.
    last_fetched_at 은 항상 갱신.
    """
    from api.programming.metadata.models.kmdb_cache import KmdbMovieCache

    docid = raw.get("DOCID") or raw.get("docid")
    if not docid:
        return "unchanged"

    title = (raw.get("title") or "").strip()
    title_eng = (raw.get("titleEng") or "").strip() or None
    title_org = (raw.get("titleOrg") or "").strip() or None

    prod_year_raw = raw.get("prodYear") or raw.get("prod_year") or ""
    try:
        prod_year = int(str(prod_year_raw)[:4]) if prod_year_raw else None
    except (ValueError, TypeError):
        prod_year = None

    nation = (raw.get("nation") or "").strip() or None
    genre = (raw.get("genre") or "").strip() or None

    runtime_raw = raw.get("runtime") or raw.get("runtime") or ""
    try:
        runtime = int(runtime_raw) if runtime_raw else None
    except (ValueError, TypeError):
        runtime = None

    # 포스터: "url1|url2|..." pipe-separated string → 리스트
    posters_list = _split_pipe_urls(raw.get("posters"))
    poster_url = posters_list[0] if posters_list else None
    stillcuts_list = _split_pipe_urls(raw.get("stlls"))

    # 시놉시스
    synopsis = None
    plots = raw.get("plots") or {}
    plot_list = plots.get("plot") if isinstance(plots, dict) else []
    if plot_list and isinstance(plot_list, list):
        synopsis = plot_list[0].get("plotText") or None

    # directors / actors — 중첩 구조 그대로 저장
    directors_raw = raw.get("directors") or {}
    directors = directors_raw.get("director") if isinstance(directors_raw, dict) else []

    actors_raw = raw.get("actors") or {}
    actors = actors_raw.get("actor") if isinstance(actors_raw, dict) else []

    existing = db.get(KmdbMovieCache, docid)

    if existing is None:
        db.add(KmdbMovieCache(
            docid=docid,
            title=title or docid,
            title_eng=title_eng,
            title_org=title_org,
            prod_year=prod_year,
            nation=nation,
            genre=genre,
            runtime=runtime,
            poster_url=poster_url,
            poster_urls=posters_list,
            stillcut_urls=stillcuts_list,
            synopsis=synopsis,
            directors=directors,
            actors=actors,
            raw_json=raw,
        ))
        return "inserted"

    existing.last_fetched_at = datetime.utcnow()

    changed = (
        existing.title != (title or docid)
        or existing.poster_url != poster_url
        or existing.poster_urls != posters_list
        or existing.stillcut_urls != stillcuts_list
        or existing.synopsis != synopsis
    )
    if changed:
        existing.title = title or docid
        existing.title_eng = title_eng
        existing.title_org = title_org
        existing.prod_year = prod_year
        existing.nation = nation
        existing.genre = genre
        existing.runtime = runtime
        existing.poster_url = poster_url
        existing.poster_urls = posters_list
        existing.stillcut_urls = stillcuts_list
        existing.synopsis = synopsis
        existing.directors = directors
        existing.actors = actors
        existing.raw_json = raw
        return "updated"

    return "unchanged"


# ── Celery 태스크 ────────────────────────────────────────────────────────────

_BATCH_COMMIT = 100   # N건마다 commit


@shared_task(
    name="workers.tasks.kmdb_cache.backfill_kmdb",
    bind=True,
    max_retries=0,      # quota 초과 등 실패 시 재시도 안 함 — 다음 날 Beat가 재실행
)
def backfill_kmdb(self, year: int):
    """1개 연도의 KMDB 영화를 페이지네이션으로 캐시에 적재 (idempotent).

    KmdbDailyLimitExceeded 발생 시 graceful 종료 (태스크 실패 아님).
    """
    from api.meta_core.clients.kmdb_client import KmdbClient, KmdbDailyLimitExceeded
    from api.programming.metadata.models.tmdb_cache import (
        TmdbSyncLog, TmdbSyncSource, TmdbSyncStatus,
    )
    from api.programming.metadata.models.external import ExternalSourceType
    from shared.config import settings

    db = SessionLocal()
    run_id = str(uuid.uuid4())
    log_row = TmdbSyncLog(
        run_id=run_id,
        source=TmdbSyncSource.kmdb_backfill,
        external_source=ExternalSourceType.kmdb,
        target_year=year,
        status=TmdbSyncStatus.running,
    )
    db.add(log_row)
    db.flush()

    client = KmdbClient(api_key=settings.KMDB_API_KEY)
    inserted = updated = unchanged = errors = 0
    start = 0
    list_count = 100
    quota_hit = False

    try:
        while True:
            try:
                items, total = client.search_year(year, start=start, list_count=list_count)
            except KmdbDailyLimitExceeded:
                logger.warning("[kmdb-backfill] year=%d quota 초과 — 중단 (start=%d)", year, start)
                quota_hit = True
                break

            if not items:
                break

            for raw in items:
                try:
                    outcome = _upsert_kmdb_movie(db, raw)
                    if outcome == "inserted":
                        inserted += 1
                    elif outcome == "updated":
                        updated += 1
                    else:
                        unchanged += 1
                except Exception as exc:
                    logger.warning("[kmdb-backfill] upsert 실패: %s", exc)
                    errors += 1

            start += list_count
            if start % _BATCH_COMMIT == 0:
                db.commit()

            if start >= total:
                break

        db.commit()
        log_row.status = TmdbSyncStatus.completed if not quota_hit else TmdbSyncStatus.failed
    except Exception as exc:
        logger.error("[kmdb-backfill] year=%d 실패: %s", year, exc)
        db.rollback()
        log_row.status = TmdbSyncStatus.failed
        errors += 1

    log_row.finished_at = datetime.utcnow()
    log_row.items_inserted = inserted
    log_row.items_updated = updated
    log_row.items_unchanged = unchanged
    log_row.errors = errors
    log_row.cache_inserted = inserted   # kmdb_backfill: items_* 는 캐시 카운터
    log_row.cache_updated = updated
    db.commit()
    db.close()

    summary = {
        "year": year,
        "inserted": inserted,
        "updated": updated,
        "unchanged": unchanged,
        "errors": errors,
        "quota_hit": quota_hit,
    }
    logger.info("[kmdb-backfill] year=%d 완료 — %s", year, summary)
    return summary


@shared_task(name="workers.tasks.kmdb_cache.backfill_kmdb_poster_urls", max_retries=0)
def backfill_kmdb_poster_urls():
    """기존 kmdb_movie_cache row 의 raw_json 에서 poster_urls/stillcut_urls 재파싱 (1회용 백필).

    _upsert_kmdb_movie 파싱 버그 수정 이전에 적재된 row 를 소급 보정한다.
    멱등 (재실행 안전). Beat 등록 없음.
    Returns: {updated, unchanged, errors}
    """
    from api.programming.metadata.models.kmdb_cache import KmdbMovieCache

    db = SessionLocal()
    updated = unchanged = errors = 0
    batch = 0

    try:
        rows = db.query(KmdbMovieCache).all()
        for row in rows:
            try:
                raw = row.raw_json or {}
                new_poster_urls = _split_pipe_urls(raw.get("posters"))
                new_stillcut_urls = _split_pipe_urls(raw.get("stlls"))
                new_poster_url = new_poster_urls[0] if new_poster_urls else None

                if (
                    row.poster_url == new_poster_url
                    and row.poster_urls == new_poster_urls
                    and row.stillcut_urls == new_stillcut_urls
                ):
                    unchanged += 1
                    continue

                row.poster_url = new_poster_url
                row.poster_urls = new_poster_urls
                row.stillcut_urls = new_stillcut_urls
                updated += 1
                batch += 1

                if batch >= 100:
                    db.commit()
                    batch = 0
            except Exception as exc:
                logger.warning("[kmdb-backfill-urls] docid=%s 실패: %s", row.docid, exc)
                errors += 1

        db.commit()
    except Exception as exc:
        logger.error("[kmdb-backfill-urls] 실패: %s", exc)
        db.rollback()
        raise
    finally:
        db.close()

    summary = {"updated": updated, "unchanged": unchanged, "errors": errors}
    logger.info("[kmdb-backfill-urls] 완료 — %s", summary)
    return summary


_QUOTA_THRESHOLD = 200   # 잔여 quota 가 이 값 미만이면 백필 스킵
_BACKFILL_START_YEAR = 1990


@shared_task(name="workers.tasks.kmdb_cache.kmdb_quota_backfill_tick")
def kmdb_quota_backfill_tick():
    """매일 06:00 KST Beat — quota 잔여 확인 후 미백필 연도 1개 비동기 트리거.

    잔여 quota < 200 이면 skip.
    """
    from datetime import date
    from api.programming.metadata.models.tmdb_cache import TmdbSyncSource
    from shared.quota_manager import QuotaManager

    quota = QuotaManager()
    remaining = quota.daily_remaining("kmdb", 500)
    if remaining < _QUOTA_THRESHOLD:
        logger.info("[kmdb-tick] quota 잔여 %d < %d — 백필 스킵", remaining, _QUOTA_THRESHOLD)
        return {"skipped": True, "remaining": remaining}

    # 미백필 연도 탐색 — external_sync_log 에서 kmdb_backfill completed 연도 조회
    db = SessionLocal()
    try:
        from sqlalchemy import text
        rows = db.execute(
            text("""
                SELECT DISTINCT target_year FROM external_sync_log
                WHERE source = :src AND status = 'completed' AND target_year IS NOT NULL
            """),
            {"src": TmdbSyncSource.kmdb_backfill.value},
        ).fetchall()
        done_years = {r[0] for r in rows}
    finally:
        db.close()

    current_year = date.today().year
    target_year = None
    for y in range(_BACKFILL_START_YEAR, current_year + 1):
        if y not in done_years:
            target_year = y
            break

    if target_year is None:
        logger.info("[kmdb-tick] 모든 연도(%d~%d) 백필 완료", _BACKFILL_START_YEAR, current_year)
        return {"skipped": True, "reason": "all_done"}

    logger.info("[kmdb-tick] quota=%d → year=%d 백필 트리거", remaining, target_year)
    backfill_kmdb.delay(year=target_year)
    return {"triggered_year": target_year, "remaining": remaining}


# ── KMDB poster → content_images 동기화 ─────────────────────────────────────

_IMAGE_BATCH_COMMIT = 100  # N개 content 처리마다 commit


@shared_task(
    name="workers.tasks.kmdb_cache.sync_kmdb_poster_to_content_images",
    max_retries=0,
)
def sync_kmdb_poster_to_content_images():
    """kmdb_movie_cache.poster_urls / stillcut_urls → content_images 동기화 (idempotent).

    전제: external_meta_sources (source_type=kmdb) 에 content_id 매핑이 존재해야 함.
    Beat link-kmdb-to-contents (07:00) 이후 07:15 KST 에 실행.

    is_primary 규칙:
      - poster_urls[0] → is_primary=True (단, 해당 content 에 이미 is_primary poster 가 있으면 False)
      - poster_urls[1:] → is_primary=False
      - stillcut_urls → ImageType.stillcut, is_primary=False (항상)

    중복 기준: (content_id, image_type, url) 조합 — 동일하면 insert 스킵.
    """
    from sqlalchemy import text

    from api.programming.metadata.models import ContentImage, ImageType
    from api.programming.metadata.models.external import ExternalMetaSource, ExternalSourceType
    from api.programming.metadata.models.kmdb_cache import KmdbMovieCache

    db = SessionLocal()
    posters_added = stillcuts_added = contents_processed = errors = 0
    batch = 0

    try:
        # content_id → docid 매핑 (ExternalMetaSource, kmdb 소스)
        links = (
            db.query(ExternalMetaSource.content_id, ExternalMetaSource.external_id)
            .filter(
                ExternalMetaSource.source_type == ExternalSourceType.kmdb,
                ExternalMetaSource.content_id.isnot(None),
            )
            .all()
        )

        for content_id, docid in links:
            cache = db.get(KmdbMovieCache, docid)
            if not cache:
                continue

            poster_urls = cache.poster_urls or []
            stillcut_urls = cache.stillcut_urls or []
            if not poster_urls and not stillcut_urls:
                continue

            try:
                # 기존 poster URL 세트 (중복 체크용)
                existing_poster_urls: set[str] = {
                    row[0]
                    for row in db.query(ContentImage.url).filter(
                        ContentImage.content_id == content_id,
                        ContentImage.image_type == ImageType.poster,
                    ).all()
                }
                # 기존 is_primary poster 존재 여부
                has_primary = db.query(ContentImage.id).filter(
                    ContentImage.content_id == content_id,
                    ContentImage.image_type == ImageType.poster,
                    ContentImage.is_primary == True,  # noqa: E712
                ).first() is not None

                # poster_urls 처리
                for idx, url in enumerate(poster_urls):
                    if url in existing_poster_urls:
                        continue
                    make_primary = (idx == 0) and (not has_primary)
                    db.add(ContentImage(
                        content_id=content_id,
                        image_type=ImageType.poster,
                        url=url,
                        source="kmdb",
                        is_primary=make_primary,
                    ))
                    existing_poster_urls.add(url)
                    if make_primary:
                        has_primary = True
                    posters_added += 1

                # stillcut_urls 처리
                existing_stillcut_urls: set[str] = {
                    row[0]
                    for row in db.query(ContentImage.url).filter(
                        ContentImage.content_id == content_id,
                        ContentImage.image_type == ImageType.stillcut,
                    ).all()
                }
                for url in stillcut_urls:
                    if url in existing_stillcut_urls:
                        continue
                    db.add(ContentImage(
                        content_id=content_id,
                        image_type=ImageType.stillcut,
                        url=url,
                        source="kmdb",
                        is_primary=False,
                    ))
                    existing_stillcut_urls.add(url)
                    stillcuts_added += 1

                contents_processed += 1
                batch += 1
                if batch >= _IMAGE_BATCH_COMMIT:
                    db.commit()
                    batch = 0

            except Exception as exc:
                logger.warning("[kmdb-image-sync] content_id=%d 처리 실패: %s", content_id, exc)
                db.rollback()
                errors += 1

        db.commit()

    except Exception as exc:
        logger.error("[kmdb-image-sync] 전체 실패: %s", exc)
        db.rollback()
        raise
    finally:
        db.close()

    summary = {
        "posters_added": posters_added,
        "stillcuts_added": stillcuts_added,
        "contents_processed": contents_processed,
        "errors": errors,
    }
    logger.info("[kmdb-image-sync] 완료 — %s", summary)
    return summary
