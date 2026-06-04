"""파이프라인 AUTO 워커 태스크 — ADR-010.

pipeline_auto_tick (Beat 15s):
  AUTO-ON bucket마다 처리 태스크를 개별 dispatch.
  빠른 단계(1/2/4) → process_fast_bucket (pipeline_fast 큐)
  AI 단계(3)        → process_ai_item (pipeline_ai 큐, per-item fan-out)

동시성 안전:
  claim_bucket: SELECT FOR UPDATE SKIP LOCKED + auto_hold 필터 + visibility_timeout 재claim
  advance_one / approve_one: FOR UPDATE + 선조건 체크
"""
import logging
from celery import shared_task
from shared.database import SessionLocal

logger = logging.getLogger(__name__)


# ── 빠른 단계 batch task (bucket 1/2/4) ──────────────────────────────────────

@shared_task(
    name="workers.tasks.pipeline_auto.process_fast_bucket",
    queue="pipeline_fast",
    bind=True,
    max_retries=2,
    default_retry_delay=10,
    acks_late=True,
)
def process_fast_bucket(self, bucket: int) -> dict:
    """bucket 1/2/4 내 콘텐츠를 batch_size만큼 claim → 처리 → advance.

    bucket 1: advance_one (S1→S2)
    bucket 2: enrich_autofill_one → advance_one (S2→S3)
    bucket 4: quality_score >= threshold → approve_one, else auto_review_skipped_at set
    """
    from api.test.pipeline_auto_service import (
        claim_bucket, advance_one, approve_one, enrich_autofill_one,
    )
    from api.programming.metadata.models.external import StageAutoPolicy

    with SessionLocal() as db:
        policy = db.query(StageAutoPolicy).filter(StageAutoPolicy.id == 1).first()
        if not policy or not policy.auto_tick_enabled:
            return {"skipped": "tick_disabled"}

        batch_size = policy.batch_size or 20
        visibility_timeout = policy.ai_visibility_timeout or 600
        threshold = policy.s4_quality_threshold or 90.0

        items = claim_bucket(db, bucket=bucket, batch_size=batch_size,
                             visibility_timeout=visibility_timeout)
        if not items:
            return {"bucket": bucket, "claimed": 0}

        ok = skipped = failed = 0
        for c in items:
            try:
                if bucket == 1:
                    r = advance_one(db, c.id, actor="auto")
                    if r["result"] == "ok":
                        ok += 1
                    else:
                        skipped += 1

                elif bucket == 2:
                    enrich_autofill_one(db, c.id)
                    r = advance_one(db, c.id, actor="auto")
                    if r["result"] == "ok":
                        ok += 1
                    else:
                        skipped += 1

                elif bucket == 4:
                    db.refresh(c)
                    # quality_score는 ContentMetadata(metadata_record)에 위치
                    score = (c.metadata_record.quality_score if c.metadata_record else 0.0) or 0.0
                    if score >= threshold:
                        r = approve_one(db, c.id, actor="auto")
                        if r["result"] == "ok":
                            ok += 1
                        else:
                            skipped += 1
                    else:
                        # 임계값 미달 → 잔류 영속 마킹
                        from datetime import datetime, timezone
                        c.auto_review_skipped_at = datetime.now(timezone.utc)
                        c.auto_claimed_at = None
                        db.flush()
                        skipped += 1

                db.commit()
            except Exception as exc:
                logger.exception("process_fast_bucket error content_id=%s bucket=%s", c.id, bucket)
                # hold 설정 — 무한 루프 방지
                try:
                    c.auto_hold = True
                    c.auto_claimed_at = None
                    db.commit()
                except Exception:
                    db.rollback()
                failed += 1

        return {"bucket": bucket, "claimed": len(items), "ok": ok, "skipped": skipped, "failed": failed}


# ── AI 단계 per-item task (bucket 3) ─────────────────────────────────────────

@shared_task(
    name="workers.tasks.pipeline_auto.process_ai_item",
    queue="pipeline_ai",
    bind=True,
    max_retries=1,
    default_retry_delay=30,
    acks_late=True,
)
def process_ai_item(self, content_id: int) -> dict:
    """AI 단계 단건 처리 — ai_autofill_one → advance_one (bucket 3 → 4)."""
    from api.test.pipeline_auto_service import advance_one, ai_autofill_one

    with SessionLocal() as db:
        try:
            ai_autofill_one(db, content_id)
            r = advance_one(db, content_id, actor="auto")
            db.commit()
            return {"content_id": content_id, "result": r["result"]}
        except Exception as exc:
            logger.exception("process_ai_item error content_id=%s", content_id)
            # hold 설정 — 무한 루프 방지
            from api.programming.metadata.models.content import Content
            try:
                c = db.get(Content, content_id)
                if c:
                    c.auto_hold = True
                    c.auto_claimed_at = None
                    db.commit()
            except Exception:
                db.rollback()
            raise self.retry(exc=exc)


# ── tick orchestrator (Beat 15s) ──────────────────────────────────────────────

@shared_task(
    name="workers.tasks.pipeline_auto.pipeline_auto_tick",
    queue="pipeline_fast",
)
def pipeline_auto_tick() -> dict:
    """Beat tick: AUTO-ON bucket별 처리 태스크를 개별 dispatch.

    빠른 단계(1/2/4)는 process_fast_bucket, AI 단계(3)는 per-item fan-out.
    auto_tick_enabled=False면 즉시 종료(kill switch).
    """
    from api.programming.metadata.models.external import StageAutoPolicy
    from api.test.pipeline_auto_service import claim_bucket

    with SessionLocal() as db:
        policy = db.query(StageAutoPolicy).filter(StageAutoPolicy.id == 1).first()
        if not policy or not policy.auto_tick_enabled:
            return {"skipped": "tick_disabled"}

        dispatched: dict[str, int] = {}

        # 빠른 단계 — bucket 단위 batch dispatch
        for bucket, flag_key in ((1, "s1_auto"), (2, "s2_auto"), (4, "s4_auto")):
            if not getattr(policy, flag_key, False):
                continue
            # pending 건 있을 때만 dispatch (빈 bucket에 task 안 보냄)
            pending = _pending_count(db, bucket, policy.ai_visibility_timeout or 600)
            if pending > 0:
                process_fast_bucket.apply_async(args=[bucket], queue="pipeline_fast")
                dispatched[f"bucket_{bucket}"] = pending

        # AI 단계 — per-item fan-out
        if getattr(policy, "s3_auto", False):
            items = claim_bucket(db, bucket=3,
                                 batch_size=policy.batch_size or 20,
                                 visibility_timeout=policy.ai_visibility_timeout or 600)
            for c in items:
                process_ai_item.apply_async(args=[c.id], queue="pipeline_ai")
            db.commit()
            if items:
                dispatched["bucket_3"] = len(items)

        return {"dispatched": dispatched}


def _pending_count(db, bucket: int, visibility_timeout: int) -> int:
    """bucket 내 처리 가능(미claim 또는 stuck) 건수. tick에서 빈 dispatch 방지."""
    from datetime import datetime, timezone, timedelta
    from api.programming.metadata.models.content import Content, ContentStatus
    from api.test.pipeline_auto_service import _STAGE_BUCKET
    from sqlalchemy import or_

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=visibility_timeout)
    stages_in_bucket = [s for s, b in _STAGE_BUCKET.items() if b == bucket]

    q = db.query(Content).filter(
        Content.is_deleted.is_(False),
        Content.auto_hold.is_(False),
        Content.status != ContentStatus.rejected,
        or_(
            Content.auto_claimed_at.is_(None),
            Content.auto_claimed_at < cutoff,
        ),
    )
    if bucket == 1:
        q = q.filter(
            or_(Content.current_stage.is_(None), Content.current_stage.in_(stages_in_bucket))
        )
    else:
        q = q.filter(Content.current_stage.in_(stages_in_bucket))

    # bucket 4: 잔류 판정 건은 처리 대상 아님 (claim_bucket과 동일 조건)
    if bucket == 4:
        q = q.filter(Content.auto_review_skipped_at.is_(None))

    return q.count()
