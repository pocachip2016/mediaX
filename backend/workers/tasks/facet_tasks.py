"""facet_tasks.py — MediSearch facet 배치 평가 (TMDB 캐시 모집단 전체).

dispatch_facet_batch (Beat 21:40 또는 수동/auto 트리거):
  vote_count >= FACET_MIN_VOTE_COUNT + 개봉일 <= 오늘 기준 tmdb_movie_cache를 모집단으로
  evaluate_tmdb_facet 태스크를 일괄 enqueue.
  FACET_BATCH_ENABLED=False 이면 beat/auto 트리거 시 no-op (수동 트리거는 무관).

evaluate_tmdb_facet (rate_limit 30/h, facet 큐):
  MediSearch /api/movies/evaluate 호출 (require_namu=True).
  - skipped_reason=no_namu | source_count=0(신작 source 미확보) → status=skipped 영구 기록 — 재선정 방지.
  - 성공(source_count>0) → status=success + Content 매핑 있으면 content_ai_results dual-write.
    (MediSearch confidence는 None 가능 — 품질 게이트는 source_count만 사용.)
  - 오류(HTTP/타임아웃/네트워크) → status=failed, attempt_count+1 — FACET_MAX_ATTEMPTS 도달 시 자연 제외.

연속 디스패치:
  FACET_CONTINUOUS=True 이면 run done 시 countdown=FACET_CONTINUOUS_DELAY_S 후 다음 run 자동 체인.
  no_targets 이면 체인 중단 (Beat 21:40이 재점화 안전망).
"""
import logging
from datetime import date, datetime, timedelta, timezone

import httpx
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import update

from shared.config import settings
from shared.database import SessionLocal
from workers.celery_app import celery_app

logger = logging.getLogger(__name__)

_MEDISEARCH_EVALUATE_PATH = "/api/movies/evaluate"


# ── 헬퍼 ─────────────────────────────────────────────────────────────────────

def _decide_facet_outcome(data: dict) -> tuple[str, str | None, int, float | None]:
    """MediSearch /evaluate 응답 → (status, reason, source_count, confidence).

    status: 'skipped' | 'success'
      - skipped_reason 존재 → ('skipped', <reason>, ...)            # 나무위키 부재 등
      - source_count == 0 (or None) → ('skipped', 'no_sources', ...) # 신작: source 미확보 → 영구 제외
      - 그 외 → ('success', None, source_count, confidence)
    confidence는 MediSearch가 None을 반환할 수 있어 그대로 전달(품질 게이트에 쓰지 않음).
    """
    skipped_reason = data.get("skipped_reason")
    source_count = data.get("source_count") or 0
    confidence = data.get("confidence") or (data.get("facet") or {}).get("confidence")
    if skipped_reason:
        return "skipped", skipped_reason, source_count, confidence
    if source_count == 0:
        return "skipped", "no_sources", source_count, confidence
    return "success", None, source_count, confidence


def _fmt_conf(confidence: float | None) -> str:
    """confidence 표시용 포맷 — None이면 'n/a' (MediSearch가 None 반환 가능)."""
    return f"{confidence:.2f}" if isinstance(confidence, (int, float)) else "n/a"

def _select_targets(
    db,
    limit: int,
    tmdb_ids: list[int] | None,
    force: bool,
    staleness_days: int,
) -> list[int]:
    """평가 대상 tmdb_id 목록 반환.

    모집단: tmdb_movie_cache (release_date <= 오늘) 중
      - 한국영화(original_language='ko'): vote_count 필터 면제 (나무위키 적중률 높음)
      - 그 외: vote_count >= FACET_MIN_VOTE_COUNT
    정렬: 한국영화 우선 → release_date DESC (한국작부터 채우고 점진 해외 확대).
    제외:
      - status=skipped (force=True 시에만 포함)
      - status=failed + attempt_count >= FACET_MAX_ATTEMPTS
      - status=failed + last_attempted_at >= now - FACET_RETRY_BACKOFF_DAYS (백오프 중)
    """
    from sqlalchemy import func, and_, or_, not_, case
    from api.programming.metadata.models.tmdb_cache import TmdbMovieCache, TmdbMovieFacet

    today = date.today()
    backoff_cutoff = datetime.now(timezone.utc) - timedelta(days=settings.FACET_RETRY_BACKOFF_DAYS)
    freshness_cutoff = datetime.now(timezone.utc) - timedelta(days=staleness_days)

    # 모집단: 한국영화는 vote 무관, 해외영화는 vote>=N
    population_filter = or_(
        TmdbMovieCache.original_language == "ko",
        TmdbMovieCache.vote_count >= settings.FACET_MIN_VOTE_COUNT,
    )

    # tmdb_movie_cache LEFT JOIN tmdb_movie_facets
    q = (
        db.query(TmdbMovieCache.id)
        .outerjoin(TmdbMovieFacet, TmdbMovieFacet.tmdb_id == TmdbMovieCache.id)
        .filter(
            TmdbMovieCache.release_date.isnot(None),
            TmdbMovieCache.release_date <= today,
            population_filter,
        )
    )

    if tmdb_ids:
        q = q.filter(TmdbMovieCache.id.in_(tmdb_ids))

    if force:
        # force: skipped 포함, 모든 기존 상태 무시
        pass
    else:
        from sqlalchemy import or_
        # NULL (facet row 없음)은 모든 제외 조건에서 살아남아야 함.
        # SQL NOT (col = val) WHERE col IS NULL → NULL → 필터 아웃됨
        # → 각 조건을 "facet row 없음(NULL) OR NOT(조건)"으로 표현

        no_facet = TmdbMovieFacet.status.is_(None)

        fresh_success = and_(
            TmdbMovieFacet.status == "success",
            TmdbMovieFacet.evaluated_at >= freshness_cutoff,
        )
        skip_condition = TmdbMovieFacet.status == "skipped"
        failed_exhausted = and_(
            TmdbMovieFacet.status == "failed",
            TmdbMovieFacet.attempt_count >= settings.FACET_MAX_ATTEMPTS,
        )
        failed_backoff = and_(
            TmdbMovieFacet.status == "failed",
            TmdbMovieFacet.last_attempted_at >= backoff_cutoff,
        )

        q = q.filter(
            or_(no_facet, not_(fresh_success)),      # 신선한 success 제외
            or_(no_facet, not_(skip_condition)),      # skipped 영구 제외
            or_(no_facet, not_(failed_exhausted)),    # attempt 상한 도달 제외
            or_(no_facet, not_(failed_backoff)),      # 백오프 중 failed 제외
        )

    # 한국영화 우선 → 최신순
    ko_priority = case((TmdbMovieCache.original_language == "ko", 0), else_=1)
    q = q.order_by(ko_priority, TmdbMovieCache.release_date.desc(), TmdbMovieCache.id.desc())
    rows = q.limit(limit).all()
    return [r[0] for r in rows]


def _upsert_tmdb_facet(
    db,
    tmdb_id: int,
    status: str,
    *,
    facet_json: dict | None = None,
    confidence: float | None = None,
    source_count: int | None = None,
    last_error: str | None = None,
) -> None:
    """tmdb_movie_facets row upsert."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from api.programming.metadata.models.tmdb_cache import TmdbMovieFacet

    now = datetime.now(timezone.utc)
    values: dict = {
        "tmdb_id": tmdb_id,
        "status": status,
        "last_attempted_at": now,
    }
    if facet_json is not None:
        values["facet_json"] = facet_json
    if confidence is not None:
        values["confidence"] = confidence
    if source_count is not None:
        values["source_count"] = source_count
    if last_error is not None:
        values["last_error"] = last_error
    if status == "success":
        values["evaluated_at"] = now

    stmt = pg_insert(TmdbMovieFacet).values(**values)
    if status in ("success", "skipped"):
        stmt = stmt.on_conflict_do_update(
            index_elements=["tmdb_id"],
            set_={k: stmt.excluded[k] for k in values if k != "tmdb_id"},
        )
    else:  # failed — attempt_count 증가
        stmt = stmt.on_conflict_do_update(
            index_elements=["tmdb_id"],
            set_={
                "status": stmt.excluded.status,
                "last_attempted_at": stmt.excluded.last_attempted_at,
                "last_error": stmt.excluded.last_error,
                "attempt_count": TmdbMovieFacet.attempt_count + 1,
            },
        )
    db.execute(stmt)


def _dual_write_content_ai_result(db, tmdb_id: int, facet_json: dict, confidence: float) -> None:
    """tmdb_id로 매핑된 Content 있으면 content_ai_results에도 final 기록."""
    from sqlalchemy import update as sa_update
    from api.programming.metadata.models import (
        ExternalMetaSource, ExternalSourceType,
        ContentAIResult, AITaskType,
    )

    sources = (
        db.query(ExternalMetaSource)
        .filter(
            ExternalMetaSource.source_type == ExternalSourceType.tmdb,
            ExternalMetaSource.external_id == str(tmdb_id),
        )
        .all()
    )
    if not sources:
        return

    for src in sources:
        content_id = src.content_id
        if not content_id:
            continue

        db.execute(
            sa_update(ContentAIResult)
            .where(
                ContentAIResult.content_id == content_id,
                ContentAIResult.task_type == AITaskType.facet_analysis,
                ContentAIResult.is_final.is_(True),
            )
            .values(is_final=False)
            .execution_options(synchronize_session=False)
        )

        result_entry = {
            **facet_json,
            "_meta": {
                "tmdb_id": tmdb_id,
                "confidence": confidence,
                "engine": "medisearch",
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        db.add(ContentAIResult(
            content_id=content_id,
            engine="medisearch",
            task_type=AITaskType.facet_analysis,
            result_json=result_entry,
            quality_score=confidence,
            is_final=True,
        ))


def _summarize_sources(data: dict) -> list[dict] | None:
    """MediSearch 응답의 sources_detail → compact [{p, docs, eval}] 요약.

    입력 형태가 예상과 달라도 절대 raise하지 않음 — emit은 best-effort.
    """
    try:
        raw = data.get("sources_detail")
        if not raw:
            return None
        result = []
        for e in raw:
            if not isinstance(e, dict):
                continue
            result.append({
                "p": e.get("provider"),
                "docs": e.get("docs_count") or 0,
                "eval": bool(e.get("evaluated")),
            })
        return result or None
    except Exception:
        return None


def _emit_event(run_id: int, tmdb_id: int | None, event_type: str, message: str, detail: dict | None = None) -> None:
    """FacetPolicy.log_enabled=True 일 때만 FacetEvent 기록. 실패해도 배치 중단 안 함."""
    try:
        from api.programming.metadata.models.external import FacetEvent, FacetPolicy

        with SessionLocal() as db:
            policy = db.query(FacetPolicy).filter(FacetPolicy.id == 1).first()
            if not policy or not policy.log_enabled:
                return
            db.add(FacetEvent(
                run_id=run_id,
                content_id=tmdb_id,  # FacetEvent.content_id는 FK 없는 nullable Integer
                event_type=event_type,
                message=message,
                detail=detail,
            ))
            db.commit()
    except Exception as exc:
        logger.debug("[facet_event] emit failed (non-fatal): %s", exc)


def _handle_stale_running_runs(db) -> int:
    """stale running run → failed. 기준: max(2h, total_count × 240s) 경과.

    Returns:
        닫힌 run 수 (0이면 stale run 없음).
    """
    from api.programming.metadata.models.external import FacetBatchRun

    running_runs = (
        db.query(FacetBatchRun)
        .filter(FacetBatchRun.status == "running")
        .all()
    )
    now = datetime.now(timezone.utc)
    closed = 0
    for run in running_runs:
        dynamic_secs = max(7200, run.total_count * 240)
        created = run.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        threshold = created + timedelta(seconds=dynamic_secs)
        if now >= threshold:
            run.status = "failed"
            run.finished_at = now
            closed += 1
    if closed:
        db.commit()
        logger.warning("[facet_batch] %d stale running→failed", closed)
    return closed


# ── 태스크 ───────────────────────────────────────────────────────────────────

@celery_app.task(
    name="workers.tasks.facet_tasks.dispatch_facet_batch",
    queue="facet",
    bind=True,
    max_retries=0,
    acks_late=True,
)
def dispatch_facet_batch(
    self,
    limit: int | None = None,
    tmdb_ids: list[int] | None = None,
    force: bool = False,
    trigger: str = "manual",
) -> dict:
    """facet 배치 오케스트레이터.

    beat/auto 트리거: FACET_BATCH_ENABLED=False 이면 즉시 no-op.
    수동 트리거: FACET_BATCH_ENABLED 무관하게 실행.
    """
    from api.programming.metadata.models.external import FacetBatchRun

    if trigger in ("beat", "auto") and not settings.FACET_BATCH_ENABLED:
        logger.info("[facet_batch] %s skip — FACET_BATCH_ENABLED=False", trigger)
        return {"skipped": True, "reason": "FACET_BATCH_ENABLED=False"}

    effective_limit = limit or settings.FACET_BATCH_SIZE

    with SessionLocal() as db:
        _handle_stale_running_runs(db)

        running = (
            db.query(FacetBatchRun)
            .filter(FacetBatchRun.status == "running")
            .first()
        )
        if running:
            logger.info("[facet_batch] skip — run %d already running", running.id)
            return {"skipped": True, "reason": "run_in_progress", "run_id": running.id}

        targets = _select_targets(db, effective_limit, tmdb_ids, force, settings.FACET_STALENESS_DAYS)

        if not targets:
            logger.info("[facet_batch] no targets (limit=%d, force=%s)", effective_limit, force)
            return {"skipped": True, "reason": "no_targets"}

        run = FacetBatchRun(
            status="running",
            trigger=trigger,
            total_count=len(targets),
            params={"limit": effective_limit, "tmdb_ids": tmdb_ids, "force": force},
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        run_id = run.id

    logger.info("[facet_batch] run %d started — %d targets (trigger=%s)", run_id, len(targets), trigger)
    _emit_event(run_id, None, "batch_started", f"배치 시작 — 대상 {len(targets)}건", {"total": len(targets), "trigger": trigger})

    for tid in targets:
        evaluate_tmdb_facet.apply_async(
            kwargs={"tmdb_id": tid, "run_id": run_id},
            queue="facet",
        )

    return {"run_id": run_id, "total": len(targets), "trigger": trigger}


@celery_app.task(
    name="workers.tasks.facet_tasks.evaluate_tmdb_facet",
    queue="facet",
    bind=True,
    max_retries=2,
    default_retry_delay=180,
    # rate_limit 제거 — 페이싱은 MediSearch 단일 throttle(MAX_CONCURRENT_EVALS=1 +
    # NAMU_MIN_INTERVAL_S)에 일원화. 평가 완료 즉시 다음 항목으로 진행(~3배 처리량).
    acks_late=True,
    soft_time_limit=540,
    time_limit=600,
)
def evaluate_tmdb_facet(self, tmdb_id: int, run_id: int) -> dict:
    """TMDB 캐시 1건 facet 평가 → tmdb_movie_facets 저장 + dual-write.

    skipped_reason=no_namu | source_count=0 → status=skipped (영구 제외).
    성공(source_count>0) → status=success + Content 매핑 있으면 content_ai_results dual-write.
    오류(HTTP/타임아웃/네트워크) → status=failed, attempt_count+1.
    """
    from api.programming.metadata.models.external import FacetBatchRun
    from api.programming.metadata.models.tmdb_cache import TmdbMovieCache

    def _inc_counter(field: str) -> None:
        with SessionLocal() as db:
            col = getattr(FacetBatchRun, field)
            db.execute(
                update(FacetBatchRun)
                .where(FacetBatchRun.id == run_id)
                .values({field: col + 1})
                .execution_options(synchronize_session=False)
            )
            _maybe_close_run(db, run_id)
            db.commit()

    def _maybe_close_run(db, rid: int) -> None:
        run = db.query(FacetBatchRun).filter(FacetBatchRun.id == rid).first()
        if not run:
            return
        done = run.success_count + run.failed_count + run.skipped_count
        if done >= run.total_count:
            run.status = "done"
            run.finished_at = datetime.now(timezone.utc)
            logger.info("[facet_batch] run %d done (s=%d f=%d sk=%d)", rid, run.success_count, run.failed_count, run.skipped_count)
            _emit_event(rid, None, "batch_done", f"배치 완료 성공={run.success_count} 실패={run.failed_count} 스킵={run.skipped_count}")
            # 연속 디스패치 (cancelled run은 재체인 차단)
            if settings.FACET_CONTINUOUS and run.status == "done":
                dispatch_facet_batch.apply_async(
                    kwargs={"trigger": "auto"},
                    countdown=settings.FACET_CONTINUOUS_DELAY_S,
                )
                logger.info("[facet_batch] 연속 dispatch 예약 (countdown=%ds)", settings.FACET_CONTINUOUS_DELAY_S)

    # 중지 guard — run이 running이 아니면(취소/완료) 즉시 no-op.
    # cancelled run의 잔여 enqueue 태스크가 카운터 미증가로 빠르게 소진되어 체인이 끊긴다.
    with SessionLocal() as db:
        run = db.query(FacetBatchRun).filter(FacetBatchRun.id == run_id).first()
    if not run or run.status != "running":
        logger.debug("[facet] tmdb %d skip — run %d not running (%s)", tmdb_id, run_id, run and run.status)
        return {"tmdb_id": tmdb_id, "status": "cancelled"}

    _emit_event(run_id, tmdb_id, "item_started", f"평가 시작 tmdb_id={tmdb_id}")

    # 캐시 row에서 payload 구성
    try:
        with SessionLocal() as db:
            cache_row = db.query(TmdbMovieCache).filter(TmdbMovieCache.id == tmdb_id).first()
        if not cache_row:
            raise ValueError(f"tmdb_id {tmdb_id} not in cache")
        production_year = cache_row.release_date.year if cache_row.release_date else None
        payload = {
            "title": cache_row.title,
            "production_year": production_year,
            "tmdb_id": tmdb_id,
            "require_namu": False,
        }
    except ValueError as exc:
        logger.error("[facet] tmdb %d not found in cache: %s", tmdb_id, exc)
        _emit_event(run_id, tmdb_id, "item_failed", f"캐시 없음: {exc}")
        _inc_counter("failed_count")
        return {"tmdb_id": tmdb_id, "status": "failed", "error": str(exc)}

    url = f"{settings.MEDISEARCH_URL.rstrip('/')}{_MEDISEARCH_EVALUATE_PATH}"
    try:
        with httpx.Client(timeout=settings.MEDISEARCH_TIMEOUT_S) as client:
            resp = client.post(url, json=payload)

        if resp.status_code in (429, 500, 502, 503, 504):
            raise self.retry(
                exc=httpx.HTTPStatusError(f"HTTP {resp.status_code}", request=resp.request, response=resp),
                countdown=180,
            )
        resp.raise_for_status()
        data = resp.json()

    except SoftTimeLimitExceeded:
        logger.warning("[facet] tmdb %d soft timeout", tmdb_id)
        with SessionLocal() as db:
            _upsert_tmdb_facet(db, tmdb_id, "failed", last_error="soft_timeout")
            db.commit()
        _emit_event(run_id, tmdb_id, "item_failed", "soft timeout")
        _inc_counter("failed_count")
        return {"tmdb_id": tmdb_id, "status": "timeout"}

    except httpx.RequestError as exc:
        logger.warning("[facet] tmdb %d network error: %s", tmdb_id, exc)
        raise self.retry(exc=exc, countdown=180)

    except httpx.HTTPStatusError as exc:
        if exc.response.status_code not in (429, 500, 502, 503, 504):
            logger.error("[facet] tmdb %d HTTP %d", tmdb_id, exc.response.status_code)
            with SessionLocal() as db:
                _upsert_tmdb_facet(db, tmdb_id, "failed", last_error=f"http_{exc.response.status_code}")
                db.commit()
            _emit_event(run_id, tmdb_id, "item_failed", f"HTTP {exc.response.status_code}")
            _inc_counter("failed_count")
            return {"tmdb_id": tmdb_id, "status": "failed"}
        raise

    # 응답 분류: skipped(나무위키 부재 / source 미확보 신작) vs success
    status, reason, source_count, confidence = _decide_facet_outcome(data)

    if status == "skipped":
        logger.info("[facet] tmdb %d skipped: %s", tmdb_id, reason)
        with SessionLocal() as db:
            _upsert_tmdb_facet(db, tmdb_id, "skipped", last_error=reason)
            db.commit()
        _emit_event(run_id, tmdb_id, "item_skipped", f"skipped: {reason}", {"reason": reason, "providers": _summarize_sources(data)})
        _inc_counter("skipped_count")
        return {"tmdb_id": tmdb_id, "status": "skipped", "reason": reason}

    # 성공 저장
    facet_json = data.get("facet", data)
    with SessionLocal() as db:
        _upsert_tmdb_facet(db, tmdb_id, "success", facet_json=facet_json, confidence=confidence, source_count=source_count)
        _dual_write_content_ai_result(db, tmdb_id, facet_json, confidence)
        db.execute(
            update(FacetBatchRun)
            .where(FacetBatchRun.id == run_id)
            .values(success_count=FacetBatchRun.success_count + 1)
            .execution_options(synchronize_session=False)
        )
        _maybe_close_run(db, run_id)
        db.commit()

    _emit_event(run_id, tmdb_id, "item_success", f"저장 완료 tmdb_id={tmdb_id} confidence={_fmt_conf(confidence)}", {"confidence": confidence, "providers": _summarize_sources(data)})
    logger.info("[facet] tmdb %d saved confidence=%s", tmdb_id, _fmt_conf(confidence))
    return {"tmdb_id": tmdb_id, "status": "ok", "confidence": confidence}


@celery_app.task(
    name="workers.tasks.facet_tasks.check_stale_facet_runs",
    queue="facet",
    bind=False,
    max_retries=0,
    acks_late=False,
)
def check_stale_facet_runs() -> dict:
    """stale running run 감지 Beat 태스크 (10분 주기).

    워커 재시작/크래시로 unacked 메시지가 고아가 되어 run이 닫히지 않는 경우를
    주기적으로 감지해 failed로 마킹하고, FACET_CONTINUOUS=True면 즉시 재디스패치.
    """
    with SessionLocal() as db:
        closed = _handle_stale_running_runs(db)

    if closed and settings.FACET_CONTINUOUS and settings.FACET_BATCH_ENABLED:
        dispatch_facet_batch.apply_async(
            kwargs={"trigger": "auto"},
            countdown=settings.FACET_CONTINUOUS_DELAY_S,
        )
        logger.info("[facet_watchdog] %d stale run(s) closed → 재디스패치 예약 (countdown=%ds)", closed, settings.FACET_CONTINUOUS_DELAY_S)
    else:
        logger.info("[facet_watchdog] closed=%d (no redispatch: continuous=%s enabled=%s)", closed, settings.FACET_CONTINUOUS, settings.FACET_BATCH_ENABLED)

    return {"closed": closed}
