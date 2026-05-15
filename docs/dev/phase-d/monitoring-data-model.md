# §6. Monitoring Data Model

## 3 GET API

### `GET /api/meta-core/web-search/quota`

각 provider 의 실시간 잔여 쿼터 + 강제 소진 여부.

```json
{
  "as_of": "2026-05-16T14:00:00+09:00",
  "kst_date": "2026-05-16",
  "providers": [
    {
      "provider": "brave",
      "daily_limit": 60,
      "used_today": 23,
      "remaining": 37,
      "percent": 38.3,
      "exhausted_at": null,
      "next_reset_at": "2026-05-17T00:00:00+09:00"
    },
    {
      "provider": "serpapi",
      "daily_limit": 3,
      "used_today": 3,
      "remaining": 0,
      "percent": 100.0,
      "exhausted_at": "2026-05-16T11:32:18+09:00",
      "next_reset_at": "2026-05-17T00:00:00+09:00"
    },
    {
      "provider": "gemini",
      "daily_limit": 200,
      "used_today": 89,
      "remaining": 111,
      "percent": 44.5,
      "exhausted_at": null,
      "next_reset_at": "2026-05-17T00:00:00+09:00"
    },
    {
      "provider": "ollama",
      "daily_limit": null,
      "used_today": 14,
      "remaining": null,
      "percent": null,
      "exhausted_at": null,
      "next_reset_at": null
    }
  ]
}
```

데이터 소스: `QuotaManager.current_count(f"websearch:{provider}")` (Redis) + `web_search_quota_log.exhausted_at` (DB).

### `GET /api/meta-core/web-search/cache-stats?days=7`

WebSearchCache 히트율.

```json
{
  "window_days": 7,
  "from_kst": "2026-05-09",
  "to_kst": "2026-05-16",
  "total_queries": 1247,
  "hits": 892,
  "misses": 355,
  "hit_rate": 0.715,
  "by_provider": [
    {"provider": "brave", "hits": 623, "misses": 217, "hit_rate": 0.741},
    {"provider": "serpapi", "hits": 12, "misses": 5, "hit_rate": 0.706},
    {"provider": "gemini", "hits": 198, "misses": 89, "hit_rate": 0.690},
    {"provider": "ollama", "hits": 59, "misses": 44, "hit_rate": 0.573}
  ]
}
```

데이터 소스: Redis 카운터 (`websearch:cache:{provider}:{hit|miss}:daily:YYYYMMDD`) 7일 합산.

### `GET /api/meta-core/web-search/recent?limit=50`

최근 호출 이력 (cache hit 포함).

```json
{
  "limit": 50,
  "items": [
    {
      "ts": "2026-05-16T13:58:42+09:00",
      "provider": "brave",
      "query": "기생충 봉준호 시놉시스",
      "cache_hit": true,
      "result_count": 8,
      "status": "ok",
      "context": "aggregator:content_id=1234"
    },
    {
      "ts": "2026-05-16T13:55:11+09:00",
      "provider": "serpapi",
      "query": "Watcha 오리지널 신작 2026",
      "cache_hit": false,
      "result_count": 8,
      "status": "ok",
      "context": "discovery:websearch:trending"
    },
    {
      "ts": "2026-05-16T13:50:03+09:00",
      "provider": "brave",
      "query": "...",
      "cache_hit": false,
      "result_count": 0,
      "status": "quota_exhausted",
      "context": "discovery:websearch:query"
    }
  ]
}
```

데이터 소스: `ExternalSyncLog WHERE source LIKE 'websearch%' ORDER BY ts DESC LIMIT 50`.
- `source` 형식: `websearch:{provider}` 또는 `websearch:cache:hit`

## Pydantic 스키마

```python
# api/meta_core/web_search/schemas.py
class ProviderQuotaOut(BaseModel):
    provider: str
    daily_limit: int | None
    used_today: int
    remaining: int | None
    percent: float | None
    exhausted_at: datetime | None
    next_reset_at: datetime | None

class QuotaResponse(BaseModel):
    as_of: datetime
    kst_date: date
    providers: list[ProviderQuotaOut]

class ProviderCacheStats(BaseModel):
    provider: str
    hits: int
    misses: int
    hit_rate: float

class CacheStatsResponse(BaseModel):
    window_days: int
    from_kst: date
    to_kst: date
    total_queries: int
    hits: int
    misses: int
    hit_rate: float
    by_provider: list[ProviderCacheStats]

class RecentCallOut(BaseModel):
    ts: datetime
    provider: str
    query: str
    cache_hit: bool
    result_count: int
    status: str  # ok / quota_exhausted / provider_error
    context: str | None  # 호출 위치 (aggregator/discovery/...)

class RecentResponse(BaseModel):
    limit: int
    items: list[RecentCallOut]
```

## UI 매핑

`/monitoring/web-search` 페이지가 위 3 API 를 호출:
- 상단 4 provider 카드: `quota` 응답을 그대로 카드 그리드로 렌더 (limit/used/remaining/percent 진행바)
- 중단 cache hit rate 표: `cache-stats?days=7` + `cache-stats?days=30` 두 호출 결합
- 하단 최근 50건 표: `recent?limit=50`

30초 auto-refresh: `setInterval(fetchAll, 30000)`.

## 알림 (운영 안전망, Phase D 범위 외)

차후 확장:
- `exhausted_at` 발생 시 Slack/이메일 알림 (Phase E 후속)
- `hit_rate < 0.30` 7일 연속 시 cache TTL 늘리거나 query 정규화 검토 알림
