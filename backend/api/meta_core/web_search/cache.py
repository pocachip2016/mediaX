import hashlib
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from api.meta_core.web_search.base import WebSearchResult
from api.programming.metadata.models.tmdb_cache import WebSearchCache


def cache_get(query: str, provider: str, db: Session) -> list[WebSearchResult] | None:
    """
    Get cached results for query+provider.

    Returns list of WebSearchResult if found and not expired, else None.
    """
    query_hash = hashlib.sha256(query.encode()).hexdigest()
    now = datetime.utcnow()

    cached = (
        db.query(WebSearchCache)
        .filter(
            WebSearchCache.query_hash == query_hash,
            WebSearchCache.source == provider,
        )
        .first()
    )

    if cached and cached.expires_at > now:
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
    expires_at = datetime.utcnow() + timedelta(days=ttl_days)

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
        existing.cached_at = datetime.utcnow()
    else:
        db.add(
            WebSearchCache(
                query_hash=query_hash,
                source=provider,
                results_json=results_json,
                expires_at=expires_at,
                cached_at=datetime.utcnow(),
            )
        )

    db.commit()
