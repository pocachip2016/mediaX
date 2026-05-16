"""
WebSearch Discovery Tasks — Phase D Beat scheduling

Tasks:
  - discover_websearch_trending: 일 1회 04:30 KST, 5개 쿼리 trending mode
"""

import logging
from celery import shared_task
from sqlalchemy.orm import Session

from shared.database import SessionLocal
from api.meta_core.discovery.websearch_source import WebSearchDiscoverySource
from api.meta_core.discovery.runner import run_discovery

logger = logging.getLogger(__name__)


@shared_task(name="discover.websearch_trending")
def discover_websearch_trending():
    """
    WebSearch trending mode 일일 실행.

    시간: 매일 04:30 KST
    쿼리: 5개 사전 정의 (넷플릭스, 디즈니, 쿠팡, 웨이브, 티빙)
    스킵: WEBSEARCH_TRENDING_ENABLED=false
    """
    import os

    if not os.getenv("WEBSEARCH_TRENDING_ENABLED", "false").lower() == "true":
        logger.debug("[websearch_trending] disabled by env")
        return {"status": "skipped"}

    db = SessionLocal()
    try:
        source = WebSearchDiscoverySource(db)

        logger.info("[websearch_trending] starting 5 queries")

        # run_discovery를 trending mode로 호출
        # (실제로는 discovery_tasks.py의 run_discovery 함수 사용)
        result = run_discovery(
            db,
            source,
            mode="trending",
        )

        logger.info(
            f"[websearch_trending] completed: "
            f"new_seeds={result.new_seeds}, "
            f"matched={result.matched_existing}, "
            f"errors={result.errors}"
        )

        return {
            "status": "completed",
            "new_seeds": result.new_seeds,
            "matched": result.matched_existing,
            "errors": result.errors,
        }

    except Exception as e:
        logger.exception(f"[websearch_trending] failed: {e}")
        return {"status": "error", "detail": str(e)}
    finally:
        db.close()
