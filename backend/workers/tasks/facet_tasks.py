"""facet_tasks.py — MediSearch facet 배치 평가 (마스터 플랜 Step 5).

dispatch_facet_batch (Beat 21:40 또는 수동 트리거):
  미평가/stale 영화 콘텐츠를 대상으로 evaluate_content_facet 태스크를 일괄 enqueue.
  FACET_BATCH_ENABLED=False 이면 beat 트리거 시 no-op.

evaluate_content_facet (rate_limit 30/h, facet 큐):
  MediSearch /api/movies/evaluate 호출 → facet JSON 수신 → content_ai_results 저장.
  기존 final 결과를 강등(is_final=False)한 뒤 신규 final 결과를 삽입.

NOTE: rate_limit="30/h" 는 워커 인스턴스당 적용된다. facet 큐 소비 워커가
늘어나면 실효 rate 가 배수 증가하므로, 워커 확장 시 rate_limit 를 조정하거나
전용 worker-facet 컨테이너를 분리한다.
"""
import logging
from datetime import datetime, timedelta, timezone

import httpx
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import update

from shared.config import settings
from shared.database import SessionLocal

logger = logging.getLogger(__name__)

_MEDISEARCH_EVALUATE_PATH = "/api/movies/evaluate"


# ── 헬퍼 ─────────────────────────────────────────────────────────────────────

def _build_evaluate_payload(content_id: int, db) -> dict:
    """content_id 에 연결된 외부 ID 포함 평가 요청 payload 구성."""
    from api.programming.metadata.models import ExternalMetaSource, ExternalSourceType
    from api.programming.metadata.models.content import Content, ContentType

    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise ValueError(f"content {content_id} not found")

    sources = (
        db.query(ExternalMetaSource)
        .filter(ExternalMetaSource.content_id == content_id)
        .all()
    )

    tmdb_id = None
    kmdb_docid = None
    production_year = getattr(content, "production_year", None)

    for src in sources:
        if src.source_type == ExternalSourceType.tmdb and src.external_id:
            try:
                tmdb_id = int(src.external_id)
            except ValueError:
                pass
        elif src.source_type == ExternalSourceType.kmdb and src.external_id:
            kmdb_docid = src.external_id

    return {
        "title": content.title,
        "production_year": production_year,
        "tmdb_id": tmdb_id,
        "kmdb_docid": kmdb_docid,
        "content_id": content_id,
    }


def _select_targets(db, limit: int, content_ids: list[int] | None,
                    force: bool, staleness_days: int) -> list[int]:
    """평가 대상 content_id 목록 반환.

    조건:
    - content_type = movie
    - external_meta_sources (tmdb/kmdb/kobis) 보유
    - force=False: staleness_days 이내 final facet_analysis 결과 없음
    - content_ids 지정 시 해당 목록으로 제한
    """
    from sqlalchemy import exists
    from api.programming.metadata.models import (
        ExternalMetaSource, ExternalSourceType,
        ContentAIResult, AITaskType,
    )
    from api.programming.metadata.models.content import Content, ContentType

    cutoff = datetime.now(timezone.utc) - timedelta(days=staleness_days)

    # 외부 소스 보유 서브쿼리
    has_external = exists().where(
        ExternalMetaSource.content_id == Content.id,
        ExternalMetaSource.source_type.in_([
            ExternalSourceType.tmdb,
            ExternalSourceType.kmdb,
            ExternalSourceType.kobis,
        ]),
    )

    q = (
        db.query(Content.id)
        .filter(Content.content_type == ContentType.movie)
        .filter(has_external)
    )

    if content_ids:
        q = q.filter(Content.id.in_(content_ids))

    if not force:
        # 신선한 final facet_analysis 결과가 없는 콘텐츠만
        has_fresh_facet = exists().where(
            ContentAIResult.content_id == Content.id,
            ContentAIResult.task_type == AITaskType.facet_analysis,
            ContentAIResult.is_final.is_(True),
            ContentAIResult.processed_at >= cutoff,
        )
        q = q.filter(~has_fresh_facet)

    rows = q.limit(limit).all()
    return [r[0] for r in rows]


def _handle_stale_running_runs(db) -> None:
    """24h+ running 상태 run → failed 처리 (유실 태스크 방어)."""
    from api.programming.metadata.models.external import FacetBatchRun

    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    stale = (
        db.query(FacetBatchRun)
        .filter(
            FacetBatchRun.status == "running",
            FacetBatchRun.created_at < cutoff,
        )
        .all()
    )
    for run in stale:
        run.status = "failed"
        run.finished_at = datetime.now(timezone.utc)
    if stale:
        db.commit()
        logger.warning("[facet_batch] %d stale running→failed", len(stale))


# ── 태스크 ───────────────────────────────────────────────────────────────────

@shared_task(
    name="workers.tasks.facet_tasks.dispatch_facet_batch",
    queue="facet",
    bind=True,
    max_retries=0,
    acks_late=True,
)
def dispatch_facet_batch(
    self,
    limit: int | None = None,
    content_ids: list[int] | None = None,
    force: bool = False,
    trigger: str = "manual",
) -> dict:
    """facet 배치 오케스트레이터.

    beat 트리거: FACET_BATCH_ENABLED=False 이면 즉시 no-op.
    수동 트리거: FACET_BATCH_ENABLED 무관하게 실행.
    """
    from api.programming.metadata.models.external import FacetBatchRun

    if trigger == "beat" and not settings.FACET_BATCH_ENABLED:
        logger.info("[facet_batch] beat skip — FACET_BATCH_ENABLED=False")
        return {"skipped": True, "reason": "FACET_BATCH_ENABLED=False"}

    effective_limit = limit or settings.FACET_BATCH_SIZE

    with SessionLocal() as db:
        _handle_stale_running_runs(db)

        # 실행 중 run 있으면 skip (멱등)
        running = (
            db.query(FacetBatchRun)
            .filter(FacetBatchRun.status == "running")
            .first()
        )
        if running:
            logger.info(
                "[facet_batch] skip — run %d already running (created %s)",
                running.id, running.created_at,
            )
            return {"skipped": True, "reason": "run_in_progress", "run_id": running.id}

        targets = _select_targets(
            db, effective_limit, content_ids, force, settings.FACET_STALENESS_DAYS
        )

        if not targets:
            logger.info("[facet_batch] no targets found (limit=%d, force=%s)", effective_limit, force)
            return {"skipped": True, "reason": "no_targets"}

        run = FacetBatchRun(
            status="running",
            trigger=trigger,
            total_count=len(targets),
            params={"limit": effective_limit, "content_ids": content_ids, "force": force},
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        run_id = run.id

    logger.info("[facet_batch] run %d started — %d targets", run_id, len(targets))

    for cid in targets:
        evaluate_content_facet.apply_async(
            kwargs={"content_id": cid, "run_id": run_id},
            queue="facet",
        )

    return {"run_id": run_id, "total": len(targets), "trigger": trigger}


@shared_task(
    name="workers.tasks.facet_tasks.evaluate_content_facet",
    queue="facet",
    bind=True,
    max_retries=2,
    default_retry_delay=180,
    rate_limit="30/h",
    acks_late=True,
    soft_time_limit=540,
    time_limit=600,
)
def evaluate_content_facet(self, content_id: int, run_id: int) -> dict:
    """콘텐츠 1건 facet 평가 → content_ai_results 저장.

    MediSearch /api/movies/evaluate 호출 → facet JSON 수신.
    source_count==0 또는 confidence==0 → 저장 없이 실패 처리.
    """
    from api.programming.metadata.models import ContentAIResult, AITaskType
    from api.programming.metadata.models.external import FacetBatchRun

    def _fail_run_counter(err_entry: dict) -> None:
        with SessionLocal() as db:
            db.execute(
                update(FacetBatchRun)
                .where(FacetBatchRun.id == run_id)
                .values(
                    failed_count=FacetBatchRun.failed_count + 1,
                    error_log=db.query(FacetBatchRun)
                    .filter(FacetBatchRun.id == run_id)
                    .with_entities(FacetBatchRun.error_log)
                    .scalar() or [] + [err_entry],
                )
                .execution_options(synchronize_session=False)
            )
            _maybe_close_run(db, run_id)
            db.commit()

    def _maybe_close_run(db, rid: int) -> None:
        run = db.query(FacetBatchRun).filter(FacetBatchRun.id == rid).first()
        if not run:
            return
        done = run.success_count + run.failed_count
        if done >= run.total_count:
            run.status = "done"
            run.finished_at = datetime.now(timezone.utc)
            logger.info("[facet_batch] run %d done (%d/%d)", rid, run.success_count, run.failed_count)

    try:
        with SessionLocal() as db:
            payload = _build_evaluate_payload(content_id, db)
    except ValueError as exc:
        logger.error("[facet] content %d not found: %s", content_id, exc)
        _fail_run_counter({"content_id": content_id, "error": str(exc)})
        return {"content_id": content_id, "status": "failed", "error": str(exc)}

    url = f"{settings.MEDISEARCH_URL.rstrip('/')}{_MEDISEARCH_EVALUATE_PATH}"
    try:
        with httpx.Client(timeout=settings.MEDISEARCH_TIMEOUT_S) as client:
            resp = client.post(url, json=payload)

        if resp.status_code in (429, 500, 502, 503, 504):
            raise self.retry(
                exc=httpx.HTTPStatusError(
                    f"HTTP {resp.status_code}", request=resp.request, response=resp
                ),
                countdown=180,
            )
        resp.raise_for_status()
        data = resp.json()

    except SoftTimeLimitExceeded:
        logger.warning("[facet] content %d soft timeout", content_id)
        _fail_run_counter({"content_id": content_id, "error": "soft_timeout"})
        return {"content_id": content_id, "status": "timeout"}

    except httpx.RequestError as exc:
        logger.warning("[facet] content %d network error: %s", content_id, exc)
        raise self.retry(exc=exc, countdown=180)

    except httpx.HTTPStatusError as exc:
        if exc.response.status_code not in (429, 500, 502, 503, 504):
            logger.error("[facet] content %d HTTP error %d", content_id, exc.response.status_code)
            _fail_run_counter({"content_id": content_id, "error": f"http_{exc.response.status_code}"})
            return {"content_id": content_id, "status": "failed"}
        raise

    # 품질 검사
    source_count = data.get("source_count", 0)
    confidence = data.get("confidence", 0.0)
    if source_count == 0 or confidence == 0:
        logger.warning("[facet] content %d low quality source_count=%d confidence=%.2f", content_id, source_count, confidence)
        _fail_run_counter({"content_id": content_id, "error": "low_quality", "source_count": source_count, "confidence": confidence})
        return {"content_id": content_id, "status": "failed", "reason": "low_quality"}

    # 저장: 기존 final → is_final=False 강등 + 신규 final 삽입
    with SessionLocal() as db:
        db.execute(
            update(ContentAIResult)
            .where(
                ContentAIResult.content_id == content_id,
                ContentAIResult.task_type == AITaskType.facet_analysis,
                ContentAIResult.is_final.is_(True),
            )
            .values(is_final=False)
            .execution_options(synchronize_session=False)
        )

        result_json = {
            **data.get("facet", data),
            "_meta": {
                "source_count": source_count,
                "confidence": confidence,
                "engine": "medisearch",
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        new_result = ContentAIResult(
            content_id=content_id,
            engine="medisearch",
            task_type=AITaskType.facet_analysis,
            result_json=result_json,
            quality_score=confidence,
            is_final=True,
        )
        db.add(new_result)

        # 원자적 카운터 증가
        db.execute(
            update(FacetBatchRun)
            .where(FacetBatchRun.id == run_id)
            .values(success_count=FacetBatchRun.success_count + 1)
            .execution_options(synchronize_session=False)
        )
        _maybe_close_run(db, run_id)
        db.commit()

    logger.info("[facet] content %d saved confidence=%.2f", content_id, confidence)
    return {"content_id": content_id, "status": "ok", "confidence": confidence}
