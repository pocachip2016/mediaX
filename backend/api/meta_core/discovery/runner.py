"""
run_discovery — DiscoverySource 실행 단일 진입점

흐름:
  1. source.discover(mode) 이터레이터 소비
  2. 각 결과를 match_or_create_seed 로 dedup/match 처리
  3. seed_discovery_log 1건 기록

Celery task 등록은 C.9.
"""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from api.meta_core.discovery.base import DiscoverySource
from api.meta_core.discovery.dedup import match_or_create_seed

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def run_discovery(db: "Session", source: DiscoverySource, mode: str, **kwargs) -> dict:
    """
    단일 발굴 회차 실행. 결과 요약 dict 반환.

    kwargs 는 source.discover(mode, **kwargs) 로 그대로 전달 — OMDb 같이
    mode 별 추가 파라미터(title, imdb_ids 등)가 필요한 소스를 지원.

    Returns:
        {"total": N, "new_seeds": N, "matched_existing": N,
         "duplicates": N, "alt_id_added": N, "errors": N, "duration_ms": N}
    """
    t0 = time.monotonic()
    total = new_seeds = matched_existing = duplicates = alt_id_added = errors = 0

    try:
        results = list(source.discover(mode, **kwargs))
        total = len(results)
        for result in results:
            try:
                _, action = match_or_create_seed(db, result)
                if action == "created":
                    new_seeds += 1
                elif action == "matched_existing":
                    matched_existing += 1
                elif action == "duplicate":
                    duplicates += 1
                elif action == "alt_id_added":
                    alt_id_added += 1
            except Exception as exc:
                logger.warning("[discovery] dedup 실패 %s/%s: %s",
                               result.source_type, result.external_id, exc)
                errors += 1
        db.commit()
    except Exception as exc:
        logger.error("[discovery] %s.%s 실패: %s", source.source_type, mode, exc)
        db.rollback()
        errors += 1

    duration_ms = int((time.monotonic() - t0) * 1000)
    summary = {
        "total": total,
        "new_seeds": new_seeds,
        "matched_existing": matched_existing,
        "duplicates": duplicates,
        "alt_id_added": alt_id_added,
        "errors": errors,
        "duration_ms": duration_ms,
    }

    source.log_run(
        db=db,
        mode=mode,
        total=total,
        new_seeds=new_seeds,
        matched_existing=matched_existing,
        duplicates=duplicates,
        errors=errors,
        duration_ms=duration_ms,
    )

    logger.info("[discovery] %s.%s 완료 — total=%d new=%d match=%d dup=%d err=%d (%dms)",
                source.source_type, mode, total, new_seeds, matched_existing,
                duplicates, errors, duration_ms)
    return summary
