import hashlib
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from api.meta_core.web_search.base import WebSearchResult
from api.programming.metadata.models.tmdb_cache import WebSearchCache


def cache_get(query: str, provider: str, db: Session) -> list[WebSearchResult] | None:
    """
    Get cached results for query+provider.

    Returns list of WebSearchResult if found and not expired, else None.
    """
    query_hash = hashlib.sha256(query.encode()).hexdigest()
    now = datetime.now(timezone.utc)

    cached = (
        db.query(WebSearchCache)
        .filter(
            WebSearchCache.query_hash == query_hash,
            WebSearchCache.source == provider,
        )
        .first()
    )

    # expires_at가 naive로 저장된 레거시 행 대비 — UTC aware로 정규화 후 비교
    cached_expiry = cached.expires_at if cached else None
    if cached_expiry is not None and cached_expiry.tzinfo is None:
        cached_expiry = cached_expiry.replace(tzinfo=timezone.utc)

    if cached and cached_expiry > now:
        if cached.results_json:
            return [
                WebSearchResult(
                    url=r["url"],
                    title=r["title"],
                    snippet=r["snippet"],
                    source_domain=r.get("source_domain", ""),
                    score=r.get("score", 1.0),
                )
                for r in cached.results_json
            ]
    return None


def cache_put(
    query: str,
    provider: str,
    results: list[WebSearchResult],
    db: Session,
    ttl_days: int = 7,
) -> None:
    """
    Cache results for query+provider.

    Updates existing entry if found, else creates new.
    """
    query_hash = hashlib.sha256(query.encode()).hexdigest()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=ttl_days)

    existing = (
        db.query(WebSearchCache)
        .filter(
            WebSearchCache.query_hash == query_hash,
            WebSearchCache.source == provider,
        )
        .first()
    )

    results_json = [
        {
            "url": r.url,
            "title": r.title,
            "snippet": r.snippet,
            "source_domain": r.source_domain,
            "score": r.score,
        }
        for r in results
    ]

    if existing:
        existing.results_json = results_json
        existing.expires_at = expires_at
        existing.fetched_at = now
    else:
        db.add(
            WebSearchCache(
                query_hash=query_hash,
                query=query,
                source=provider,
                results_json=results_json,
                expires_at=expires_at,
                fetched_at=now,
            )
        )

    db.commit()
