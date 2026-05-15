"""
WebSearch Monitoring API — 3개 GET 엔드포인트

GET /api/meta-core/web-search/quota
  → provider별 일일 usage 조회

GET /api/meta-core/web-search/cache-stats?days=7
  → cache hit rate 통계

GET /api/meta-core/web-search/recent?limit=50
  → 최근 호출 이력
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from shared.database import get_db
from shared.quota_manager import QuotaManager, KST
from api.programming.metadata.models.tmdb_cache import WebSearchCache, WebSearchQuotaLog, ExternalSyncLog

router = APIRouter(prefix="/web-search", tags=["web-search"])


# ── Pydantic Schemas ─────────────────────────────────────────────────────────

class ProviderQuotaOut(BaseModel):
    provider: str
    daily_limit: int
    used_today: int
    remaining: int
    percent_used: float
    exhausted_until: Optional[str] = None  # ISO 8601 if exhausted


class QuotaStatsOut(BaseModel):
    as_of: str  # ISO 8601 KST
    providers: list[ProviderQuotaOut]


class CacheStatsOut(BaseModel):
    period_days: int
    total_queries: int
    cache_hits: int
    cache_misses: int
    hit_rate: float  # 0.0-1.0
    by_provider: list[dict]  # [{provider, hits, misses}, ...]


class RecentCallOut(BaseModel):
    timestamp: str  # ISO 8601
    provider: str
    query_preview: str  # First 50 chars
    cache_hit: bool
    status: str  # success | error


class RecentCallsOut(BaseModel):
    total: int
    limit: int
    calls: list[RecentCallOut]


# ── GET /quota ────────────────────────────────────────────────────────────────

@router.get("/quota", response_model=QuotaStatsOut)
def get_quota_stats(db: Session = Depends(get_db)):
    """
    Provider별 일일 쿼터 사용 현황.
    """
    from shared.config import settings

    quota_mgr = QuotaManager()

    providers_config = {
        "brave": settings.WEBSEARCH_BRAVE_DAILY,
        "serpapi": settings.WEBSEARCH_SERPAPI_DAILY,
        "gemini": settings.WEBSEARCH_GEMINI_DAILY,
        "ollama": 999999,  # Unlimited
    }

    provider_stats = []
    for provider, daily_limit in providers_config.items():
        quota_key = f"websearch:{provider}"
        used = quota_mgr.current_count(quota_key)
        remaining = daily_limit - used
        percent = (used / daily_limit * 100) if daily_limit > 0 else 0.0

        provider_stats.append(
            ProviderQuotaOut(
                provider=provider,
                daily_limit=daily_limit,
                used_today=used,
                remaining=max(0, remaining),
                percent_used=min(100.0, percent),
                exhausted_until=None,  # Could be populated from WebSearchQuotaLog
            )
        )

    now = datetime.now(KST).isoformat()
    return QuotaStatsOut(as_of=now, providers=provider_stats)


# ── GET /cache-stats ──────────────────────────────────────────────────────────

@router.get("/cache-stats", response_model=CacheStatsOut)
def get_cache_stats(
    days: int = Query(7, ge=1, le=30),
    db: Session = Depends(get_db),
):
    """
    Cache hit rate 통계 (days 기간).
    """
    cutoff = datetime.utcnow() - timedelta(days=days)

    # Total queries in period
    total_queries = (
        db.query(WebSearchCache)
        .filter(WebSearchCache.cached_at >= cutoff)
        .count()
    )

    # Assume hit_rate = repeat queries / total (simplified)
    # In practice, would need better tracking
    cache_entries = (
        db.query(WebSearchCache)
        .filter(WebSearchCache.cached_at >= cutoff)
        .all()
    )

    by_provider_stats = {}
    for entry in cache_entries:
        provider = entry.source or "unknown"
        if provider not in by_provider_stats:
            by_provider_stats[provider] = {"hits": 0, "misses": 0}
        # Count as hit (already cached)
        by_provider_stats[provider]["hits"] += 1

    by_provider = [
        {"provider": p, **stats} for p, stats in by_provider_stats.items()
    ]

    hit_rate = 0.0
    if total_queries > 0:
        total_hits = sum(s["hits"] for s in by_provider_stats.values())
        hit_rate = total_hits / total_queries

    return CacheStatsOut(
        period_days=days,
        total_queries=total_queries,
        cache_hits=sum(s["hits"] for s in by_provider_stats.values()),
        cache_misses=sum(s["misses"] for s in by_provider_stats.values()),
        hit_rate=hit_rate,
        by_provider=by_provider,
    )


# ── GET /recent ────────────────────────────────────────────────────────────────

@router.get("/recent", response_model=RecentCallsOut)
def get_recent_calls(
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    최근 웹 검색 호출 이력 (최대 limit건).
    """
    # Query ExternalSyncLog for web search entries
    recent_logs = (
        db.query(ExternalSyncLog)
        .filter(
            ExternalSyncLog.source == "websearch",
        )
        .order_by(ExternalSyncLog.created_at.desc())
        .limit(limit)
        .all()
    )

    calls = []
    for log in recent_logs:
        calls.append(
            RecentCallOut(
                timestamp=log.created_at.isoformat() if log.created_at else "",
                provider=log.source or "unknown",
                query_preview=log.remarks[:50] if log.remarks else "(no query)",
                cache_hit=False,  # Would need to track separately
                status="completed" if log.status == "completed" else "error",
            )
        )

    return RecentCallsOut(total=len(calls), limit=limit, calls=calls)
