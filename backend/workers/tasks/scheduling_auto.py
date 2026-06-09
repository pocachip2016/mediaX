"""scheduling_auto.py — 자동편성 파이프라인 Beat + 이벤트 훅 태스크 (ADR-012).

auto_schedule_tick (Beat 2분):
  ScheduleAutoPolicy.auto_tick_enabled 가 True 인 경우에만 동작.
  버킷 1~4 에 claim 가능 노드가 있으면 process_schedule_bucket 을 dispatch.

process_schedule_bucket (bucket 단위 배치):
  claim_bucket → per-node advance_one 실행.

rematch_scheduling_nodes (이벤트 훅):
  콘텐츠 발행/프로파일 완료 시 매칭 가능한 auto_enabled 노드를 P3 재매칭 큐잉.
  auto_enabled=True + published NodeSet 에 속한 노드만 대상(과호출 방지).
"""
import logging

from celery import shared_task

from shared.database import SessionLocal

logger = logging.getLogger(__name__)


# ── 버킷 배치 태스크 ───────────────────────────────────────────────────────────

@shared_task(
    name="workers.tasks.scheduling_auto.process_schedule_bucket",
    queue="pipeline_fast",
    bind=True,
    max_retries=2,
    default_retry_delay=15,
    acks_late=True,
)
def process_schedule_bucket(self, bucket: int) -> dict:
    """bucket 내 ProgrammingNode 를 batch_size만큼 claim → advance_one."""
    from api.programming.scheduling.auto_service import (
        advance_one, claim_bucket, get_policy,
    )

    with SessionLocal() as db:
        policy = get_policy(db)
        if not policy.auto_tick_enabled:
            return {"skipped": "tick_disabled"}

        nodes = claim_bucket(
            db,
            bucket=bucket,
            batch_size=policy.batch_size,
            visibility_timeout=policy.visibility_timeout,
        )
        if not nodes:
            return {"bucket": bucket, "claimed": 0}

        ok = skipped = failed = 0
        for node in nodes:
            try:
                r = advance_one(db, node.id, actor="beat")
                if r["result"] == "ok":
                    ok += 1
                else:
                    skipped += 1
                db.commit()
            except Exception:
                logger.exception(
                    "process_schedule_bucket error node_id=%s bucket=%s", node.id, bucket
                )
                try:
                    node.auto_hold = True
                    node.auto_claimed_at = None
                    db.commit()
                except Exception:
                    db.rollback()
                failed += 1

        return {"bucket": bucket, "claimed": len(nodes), "ok": ok, "skipped": skipped, "failed": failed}


# ── Beat tick orchestrator ────────────────────────────────────────────────────

@shared_task(
    name="workers.tasks.scheduling_auto.auto_schedule_tick",
    queue="pipeline_fast",
)
def auto_schedule_tick() -> dict:
    """Beat tick: auto_tick_enabled=True 일 때 버킷별 dispatch.

    bucket 1(P1) / 2(P2+P3) / 3(P4) / 4(P5) 순서로 pending 확인 후 fan-out.
    빈 버킷은 dispatch 생략 (불필요한 task 발행 방지).
    """
    from api.programming.scheduling.auto_service import (
        claim_bucket, get_policy, _STAGE_BUCKET,
    )
    from api.programming.scheduling.models import (
        AutoStage, ProgrammingNode,
    )
    from datetime import datetime, timezone, timedelta
    from sqlalchemy import or_

    with SessionLocal() as db:
        policy = get_policy(db)
        if not policy.auto_tick_enabled:
            return {"skipped": "tick_disabled"}

        dispatched: dict[str, int] = {}
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=policy.visibility_timeout)

        for bucket in (1, 2, 3, 4):
            stages_in = [s for s, b in _STAGE_BUCKET.items() if b == bucket]
            q = db.query(ProgrammingNode).filter(
                ProgrammingNode.auto_enabled.is_(True),
                ProgrammingNode.auto_hold.is_(False),
                or_(
                    ProgrammingNode.auto_claimed_at.is_(None),
                    ProgrammingNode.auto_claimed_at < cutoff,
                ),
            )
            if bucket == 1:
                from sqlalchemy import or_ as _or
                q = q.filter(
                    _or(
                        ProgrammingNode.auto_stage.is_(None),
                        ProgrammingNode.auto_stage.in_(stages_in),
                    )
                )
            else:
                q = q.filter(ProgrammingNode.auto_stage.in_(stages_in))

            if bucket == 4:
                q = q.filter(ProgrammingNode.auto_skipped_at.is_(None))

            pending = q.count()
            if pending > 0:
                process_schedule_bucket.apply_async(args=[bucket], queue="pipeline_fast")
                dispatched[f"bucket_{bucket}"] = pending

        return {"dispatched": dispatched}


# ── 콘텐츠 이벤트 훅 ─────────────────────────────────────────────────────────

@shared_task(
    name="workers.tasks.scheduling_auto.rematch_scheduling_nodes",
    queue="pipeline_fast",
    bind=True,
    max_retries=1,
    default_retry_delay=30,
    acks_late=True,
)
def rematch_scheduling_nodes(self, content_id: int) -> dict:
    """콘텐츠 발행/프로파일 완료 시 해당 content_id 를 담을 수 있는 auto_enabled 노드를 P3 재매칭.

    대상 한정 조건 (과호출 방지):
      - ProgrammingNode.auto_enabled = True
      - ProgrammingNode.auto_hold = False
      - ProgrammingNode.auto_stage IN (p2_candidate, p3_match, p4_autoconfirm) — P4 잔류 재평가 포함
      - 해당 노드의 set 가 published 상태인 경우는 제외(이미 발행 완료 세트는 건드리지 않음)

    P3 실행: advance_one 이 아니라 직접 suggest_links 재실행 후 stage = p3_match 로 고정.
    (노드가 이미 p4/p5 이면 건드리지 않음 — p2/p3 잔류만 대상)
    """
    from api.programming.scheduling.auto_service import advance_one, get_policy
    from api.programming.scheduling.models import (
        AutoStage, ProgrammingNode, ProgrammingNodeSet,
    )
    from api.programming.scheduling.suggest_service import suggest_links

    REMATCH_STAGES = {
        AutoStage.P2_CANDIDATE.value,
        AutoStage.P3_MATCH.value,
    }

    with SessionLocal() as db:
        policy = get_policy(db)

        # 재매칭 대상 노드 조회 (published set 제외, p2/p3 위치 노드만)
        nodes = (
            db.query(ProgrammingNode)
            .join(ProgrammingNodeSet, ProgrammingNode.set_id == ProgrammingNodeSet.id, isouter=True)
            .filter(
                ProgrammingNode.auto_enabled.is_(True),
                ProgrammingNode.auto_hold.is_(False),
                ProgrammingNode.auto_stage.in_(list(REMATCH_STAGES)),
                # published 세트에 속한 노드는 제외
                ~(ProgrammingNodeSet.status == "published"),
            )
            .all()
        )

        if not nodes:
            return {"content_id": content_id, "matched": 0}

        matched = 0
        for node in nodes:
            try:
                # rule_query 있는 노드만 re-suggest (의미 있는 필터)
                if not node.rule_query and not node.headline_copy:
                    continue
                suggest_links(db, node, threshold=policy.confidence_threshold)
                # stage 는 p3_match 로 고정 (p2 → p3 전이만)
                if node.auto_stage == AutoStage.P2_CANDIDATE:
                    node.auto_stage = AutoStage.P3_MATCH
                db.commit()
                matched += 1
            except Exception:
                logger.exception("rematch_scheduling_nodes error node_id=%s", node.id)
                db.rollback()

        return {"content_id": content_id, "matched": matched}
