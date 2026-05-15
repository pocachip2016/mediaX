# D.7 — Monitoring Backend API

## 목표
WebSearch 모니터링 3개 GET 엔드포인트 + Pydantic 스키마.

## 산출물

### 백엔드 파일
1. **`backend/api/meta_core/web_search/router.py`** (신규)
   - `GET /api/meta-core/web-search/quota` — provider별 일일 사용량
   - `GET /api/meta-core/web-search/cache-stats?days=7` — cache hit rate
   - `GET /api/meta-core/web-search/recent?limit=50` — 최근 호출 이력

2. **Pydantic 스키마** (router.py 내)
   - `ProviderQuotaOut` — provider, daily_limit, used_today, remaining, percent_used
   - `QuotaStatsOut` — as_of(ISO8601), providers[]
   - `CacheStatsOut` — period_days, total_queries, cache_hits, hit_rate, by_provider[]
   - `RecentCallOut` — timestamp, provider, query_preview, cache_hit, status
   - `RecentCallsOut` — total, limit, calls[]

3. **Router 마운트**
   - `backend/api/meta_core/router.py` — web_search_router include

### 테스트 파일
- **`backend/tests/meta_core/web_search/test_router.py`** — 6개 케이스
  1. ProviderQuotaOut 스키마
  2. CacheStatsOut 스키마
  3. RecentCallsOut 스키마
  4. GET /quota 응답 구조
  5. GET /cache-stats 응답 구조
  6. GET /recent 응답 구조

## 엔드포인트 상세

### 1. GET /api/meta-core/web-search/quota

```json
{
  "as_of": "2026-05-16T15:45:00+09:00",
  "providers": [
    {
      "provider": "brave",
      "daily_limit": 60,
      "used_today": 30,
      "remaining": 30,
      "percent_used": 50.0,
      "exhausted_until": null
    },
    ...
  ]
}
```

응답: QuotaStatsOut (200)

### 2. GET /api/meta-core/web-search/cache-stats?days=7

Query params:
- days: 1~30 (default 7)

```json
{
  "period_days": 7,
  "total_queries": 100,
  "cache_hits": 70,
  "cache_misses": 30,
  "hit_rate": 0.70,
  "by_provider": [
    {"provider": "brave", "hits": 70, "misses": 0},
    {"provider": "serpapi", "hits": 0, "misses": 30}
  ]
}
```

응답: CacheStatsOut (200)

### 3. GET /api/meta-core/web-search/recent?limit=50

Query params:
- limit: 1~100 (default 50)

```json
{
  "total": 45,
  "limit": 50,
  "calls": [
    {
      "timestamp": "2026-05-16T15:40:00Z",
      "provider": "brave",
      "query_preview": "한국 드라마 신작 2026",
      "cache_hit": false,
      "status": "success"
    },
    ...
  ]
}
```

응답: RecentCallsOut (200)

## 데이터 소스

- **Quota**: QuotaManager.current_count() (Redis)
- **Cache**: WebSearchCache ORM (DB)
- **Recent**: ExternalSyncLog ORM (DB)

## Verify 체크

```bash
bash .claude/verify.sh phase-d-step7
```

- ✓ web_search/router.py 존재
- ✓ 3개 GET 엔드포인트 정의
- ✓ 5개 Pydantic 스키마
- ✓ web_search_router 마운트 (meta_core/router.py)
- ✓ test_router.py 존재 (6 케이스)
- ✓ TestClient 응답 구조 확인

## 다음 스텝
D.8 — Monitoring UI + Beat + wrap

## 참고
- 엔드포인트 prefix: `/api/meta-core/web-search/{quota,cache-stats,recent}`
- Query params: days (cache), limit (recent) 검증됨
- Response format: ISO 8601 timestamp (KST/UTC 일관성)
