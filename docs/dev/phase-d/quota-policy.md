# §2. Quota Policy

## Redis Key 컨벤션

```
websearch:{provider}:daily:{YYYYMMDD_KST}
```

예시:
- `websearch:brave:daily:20260516`
- `websearch:serpapi:daily:20260516`
- `websearch:gemini:daily:20260516`

Ollama 는 카운터 미사용 (무한).

## Provider별 Daily Limit

| Provider | 무료 한도 (월) | mediaX daily 정책 | 안전 마진 |
|----------|----------------|-------------------|-----------|
| Brave | 2000 | 60 | ~10% (60×30=1800 < 2000) |
| SerpAPI | 100 | 3 | ~10% (3×30=90 < 100) |
| Gemini | RPD 200 (Flash) | 200 | 0% — 모델 자체 한도 |
| Ollama | 무제한 | ∞ | n/a |

env 변수로 조정 가능:
- `WEBSEARCH_BRAVE_DAILY` (default 60)
- `WEBSEARCH_SERPAPI_DAILY` (default 3)
- `WEBSEARCH_GEMINI_DAILY` (default 200)

## KST 자정 리셋

`shared.quota_manager.QuotaManager` 의 기존 패턴 그대로:

```python
# is_allowed 내부
key = f"websearch:{provider}:daily:{today_kst:%Y%m%d}"
count = redis.get(key) or 0
if count >= daily_limit:
    return False
redis.incr(key)
redis.expireat(key, next_midnight_kst)
return True
```

KOBIS/KMDB 와 동일한 패턴이므로 별도 helper 불필요. `QuotaManager.is_allowed("websearch:brave", 60)` 한 줄로 처리.

## 호출 흐름

```
WebSearchProvider.search(query)
  ├─ cache.cache_get(query, provider) → hit 시 즉시 return (quota 0)
  ├─ QuotaManager.is_allowed("websearch:brave", daily) → False 시 QuotaExhaustedError
  ├─ httpx.get(brave_api_url, ...) → 200 OK
  ├─ cache.cache_put(query, provider, results, ttl=7d)
  └─ return results
```

`QuotaExhaustedError` 발생 시 `factory.search_with_fallback` 가 다음 provider 로 자동 전환.

## 강제 소진 (exhaustNow)

provider 가 429 (Too Many Requests) 응답을 반환하면 (예: Brave 가 사용자 모르는 사이 한도 초과 통지),
즉시 `QuotaManager.set("websearch:brave:daily:YYYYMMDD", daily_limit)` 으로 한도 채움 → 당일 잔여 호출 차단.

```python
# brave.py 내부
if resp.status_code == 429:
    quota.exhaust_now(f"websearch:{self.provider_name}", daily_limit)
    raise QuotaExhaustedError(self.provider_name)
```

## 모니터링 데이터

`web_search_quota_log` 테이블 (alembic 0013):
- `id`, `provider`, `day_kst`, `count`, `limit_at_time`, `exhausted_at` (nullable)
- 매 호출 시 INSERT 안 함 — 일 1회 04:00 KST Beat 가 Redis 카운터 → DB 스냅샷
- `exhausted_at` 은 강제 소진 시점에 즉시 UPDATE

`/api/meta-core/web-search/quota` 엔드포인트는 Redis 실시간 + DB 히스토리 조합.
