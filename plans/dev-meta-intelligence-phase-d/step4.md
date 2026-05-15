# D.4 — bulk-guard + cache integration

## 목표
Bulk 연산 quota 가드 + cache hit 시 quota 미사용 확인.

## 산출물

### 백엔드 파일
1. **`backend/api/meta_core/web_search/guard.py`**
   - `check_bulk_allowed(expected_calls, provider, daily_limit, quota_manager) -> bool`
   - Rule: `expected > remaining_quota * 0.5` → `BulkQuotaError` 발생
   - Safety margin 50% — 동일 날 다른 연산 보호

2. **Cache integration (factory.py)**
   - `search_with_fallback()` 이미 cache_get 우선 처리 (quota 사용 안 함)
   - Cache hit 로그: `"Cache HIT: <provider>"` 확인

### 테스트 파일
- **`backend/tests/meta_core/web_search/test_guard.py`** — 6개 케이스
  1. Bulk allowed (sufficient quota)
  2. Bulk rejected (insufficient quota)
  3. Edge case: exactly at threshold (allow)
  4. Edge case: over by one (reject)
  5. Multiple providers (serpapi)
  6. Bulk error detail 검증

- **`backend/tests/meta_core/web_search/test_cache.py`** — 6개 케이스
  1. Cache hit returns results
  2. Cache miss (no entry)
  3. Cache miss (expired)
  4. Cache put new entry
  5. Cache put update existing
  6. Cache respects TTL parameter

## Bulk Guard Logic

```python
remaining = daily_limit - used  # e.g., 60 - 45 = 15
threshold = remaining * 0.5      # e.g., 15 * 0.5 = 7.5

if expected_calls > threshold:
    # REJECT
    raise BulkQuotaError(expected, remaining)
else:
    # ALLOW (can proceed safely)
    return True
```

### 예시
- Brave daily limit: 60
- 오늘 사용: 45 (remaining: 15)
- Bulk 예상 호출: 20건 × 4 provider = 80건
- Check: 20 > 15 * 0.5 (7.5) → **REJECT** ✓
- Reason: 20건 호출 후 5건만 남음 (다른 연산 불가)

## Cache Hit = 0 Quota

`search_with_fallback()`:
```
1. for provider in chain:
   cached = cache_get(query, provider)  # DB 조회만, quota 미사용
   if cached:
       return cached, provider_name     # 성공, quota 0

2. # Cache miss → provider 호출 (quota 사용)
   results = await provider.search()
   cache_put(query, provider, results)  # 캐시 저장
   return results, provider_name
```

7일 cache TTL → 70% hit rate = 3배 quota 효율 (100 쿼리 = ~30 실제 호출)

## Verify 체크

```bash
bash .claude/verify.sh phase-d-step4
```

- ✓ guard.py 파일 존재
- ✓ `check_bulk_allowed()` 함수 정의
- ✓ `BulkQuotaError` 발생 시 `expected`, `remaining` 필드 포함
- ✓ Cache hit 시 quota 미증가 (factory search_with_fallback 로직)
- ✓ test_guard.py 존재 (6 케이스)
- ✓ test_cache.py 존재 (6 케이스)
- ✓ 패키지 re-export OK

## 다음 스텝
D.5 — WebSearchDiscoverySource (SEED 발굴)

## 참고
- TabGet's QuotaExhaustedError graceful break 패턴 적용
