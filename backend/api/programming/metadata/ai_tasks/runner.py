"""
AiTask Runner — AI Task 플러그인 순회 실행기 (ADR-007)

흐름:
  1. AI_TASK_REGISTRY 활성 task 순회
  2. build_input() → None이면 skip
  3. input_hash 계산 → content_ai_results에 캐시 hit 체크
  4. LLM 호출 (provider_chain + QuotaManager)
  5. apply() → ContentMetadata 반영
  6. ContentAIResult 저장 (input_hash 포함)
  7. StageEvent 기록
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _compute_input_hash(content_id: int, task_name: str, payload: dict) -> str:
    """SHA-256(content_id + task_name + stable JSON payload)."""
    raw = f"{content_id}:{task_name}:{json.dumps(payload, sort_keys=True, ensure_ascii=False)}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _is_cached(db: "Session", content_id: int, task_name: str, input_hash: str) -> bool:
    """동일 input_hash + is_final=True 결과가 이미 있으면 True."""
    from api.programming.metadata.models.external import ContentAIResult, AITaskType
    return db.query(ContentAIResult).filter(
        ContentAIResult.content_id == content_id,
        ContentAIResult.task_type == task_name,
        ContentAIResult.input_hash == input_hash,
        ContentAIResult.is_final == True,
    ).first() is not None


def _save_result(
    db: "Session",
    content_id: int,
    task_name: str,
    engine: str,
    result: dict,
    input_hash: str,
) -> None:
    """ContentAIResult 저장 (이전 is_final 해제 후 신규 저장)."""
    from api.programming.metadata.models.external import ContentAIResult, AITaskType

    db.query(ContentAIResult).filter(
        ContentAIResult.content_id == content_id,
        ContentAIResult.task_type == task_name,
        ContentAIResult.is_final == True,
    ).update({"is_final": False}, synchronize_session=False)

    db.add(ContentAIResult(
        content_id=content_id,
        engine=engine,
        task_type=task_name,
        result_json=result,
        input_hash=input_hash,
        is_final=True,
    ))


async def run_ai_tasks(content_id: int, db: "Session") -> dict[str, str]:
    """
    등록된 모든 활성 AiTask를 순회 실행.
    반환: {task_name: "ok" | "cached" | "skip" | "error"}
    """
    from api.programming.metadata.ai_tasks import AI_TASK_REGISTRY
    from api.programming.metadata.models import Content, ContentMetadata
    from api.programming.metadata.models.external import AiTaskSetting
    from api.programming.metadata.llm import get_task_provider_chain
    from shared.quota_manager import QuotaManager

    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise ValueError(f"Content {content_id} not found")

    meta = content.metadata_record
    if meta is None:
        meta = ContentMetadata(content_id=content_id)
        db.add(meta)
        db.flush()

    # DB 설정 로드 (없으면 기본값 True)
    db_settings = {
        row.task_name: row.enabled
        for row in db.query(AiTaskSetting).all()
    }

    provider_chain = get_task_provider_chain()
    quota = QuotaManager()
    results: dict[str, str] = {}

    for task_name, task in AI_TASK_REGISTRY.items():
        task_enabled = db_settings.get(task_name, task.enabled)
        if not task_enabled:
            results[task_name] = "skip"
            continue

        task_input = task.build_input(meta)
        if task_input is None:
            results[task_name] = "skip"
            logger.debug("[ai_runner] content_id=%d task=%s skip (build_input→None)", content_id, task_name)
            continue

        input_hash = _compute_input_hash(content_id, task_name, task_input.payload)

        if _is_cached(db, content_id, task_name, input_hash):
            results[task_name] = "cached"
            logger.debug("[ai_runner] content_id=%d task=%s cached", content_id, task_name)
            continue

        if not quota.is_allowed("llm_task", limit=500):
            results[task_name] = "quota_exceeded"
            logger.warning("[ai_runner] content_id=%d task=%s quota exceeded", content_id, task_name)
            continue

        try:
            output = await task.run(task_input, provider_chain)
            task.apply(meta, output)
            _save_result(db, content_id, task_name, output.engine, output.result, input_hash)
            db.flush()
            results[task_name] = "ok"
            logger.info("[ai_runner] content_id=%d task=%s engine=%s ok", content_id, task_name, output.engine)
        except Exception as exc:
            results[task_name] = "error"
            logger.error("[ai_runner] content_id=%d task=%s error: %s", content_id, task_name, exc)

    db.commit()
    return results


async def run_single_ai_task(content_id: int, task_name: str, db: "Session") -> dict:
    """단일 AiTask 실행 — status 불변. 수동 sub-step 테스트용 (ADR-009)."""
    from api.programming.metadata.ai_tasks import AI_TASK_REGISTRY
    from api.programming.metadata.models import Content, ContentMetadata
    from api.programming.metadata.llm import get_task_provider_chain
    from shared.quota_manager import QuotaManager

    if task_name not in AI_TASK_REGISTRY:
        return {"task_name": task_name, "status": "unknown_task", "engine": None, "result_preview": None}

    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise ValueError(f"Content {content_id} not found")

    meta = content.metadata_record
    if meta is None:
        meta = ContentMetadata(content_id=content_id)
        db.add(meta)
        db.flush()

    task = AI_TASK_REGISTRY[task_name]
    provider_chain = get_task_provider_chain()
    quota = QuotaManager()

    task_input = task.build_input(meta)
    if task_input is None:
        return {"task_name": task_name, "status": "skip", "engine": None, "result_preview": None}

    input_hash = _compute_input_hash(content_id, task_name, task_input.payload)

    if _is_cached(db, content_id, task_name, input_hash):
        return {"task_name": task_name, "status": "cached", "engine": None, "result_preview": None}

    if not quota.is_allowed("llm_task", daily_limit=500):
        return {"task_name": task_name, "status": "quota_exceeded", "engine": None, "result_preview": None}

    try:
        output = await task.run(task_input, provider_chain)
        task.apply(meta, output)
        _save_result(db, content_id, task_name, output.engine, output.result, input_hash)
        db.commit()
        preview = str(output.result)[:120] if output.result else None
        logger.info("[ai_runner:single] content_id=%d task=%s engine=%s ok", content_id, task_name, output.engine)
        return {"task_name": task_name, "status": "ok", "engine": output.engine, "result_preview": preview}
    except Exception as exc:
        logger.error("[ai_runner:single] content_id=%d task=%s error: %s", content_id, task_name, exc)
        return {"task_name": task_name, "status": "error", "engine": None, "result_preview": str(exc)[:120]}
