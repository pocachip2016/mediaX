# D.2 — web_search package + BraveSearchProvider

## 목표
`meta_core/web_search/` 패키지 구성 및 Brave Search API 구현.

## 산출물

### 백엔드 파일
1. **`backend/api/meta_core/web_search/__init__.py`** — 패키지 진입점 + re-export
2. **`backend/api/meta_core/web_search/base.py`** — `WebSearchProvider(ABC)`, `WebSearchResult` dataclass
3. **`backend/api/meta_core/web_search/brave.py`** — `BraveSearchProvider` 구현
   - Brave Search API v1 호출
   - QuotaManager 통합 (is_allowed 체크)
   - 429 응답 시 QuotaExhaustedError 발생
   - 한국어 우선 (`country=kr`)
4. **`backend/api/meta_core/web_search/cache.py`** — 캐시 헬퍼
   - `cache_get(query, provider, db) -> list[WebSearchResult] | None`
   - `cache_put(query, provider, results, db, ttl_days=7) -> None`
   - WebSearchCache ORM 활용 (query_hash + source composite unique)
5. **`backend/api/meta_core/web_search/errors.py`** — 예외 클래스
   - `QuotaExhaustedError(provider, remaining)`
   - `ProviderUnavailableError(provider, detail)`
   - `BulkQuotaError(expected, remaining, detail)` — D.4에서 사용

### 테스트 파일
- **`backend/tests/meta_core/web_search/test_brave.py`** — 6개 케이스
  1. Normal search (2 results, source_domain 추출 확인)
  2. Quota exhausted (is_allowed = False)
  3. 429 rate limit (quota exhausted로 변환)
  4. 500 API error (ProviderUnavailableError)
  5. API key not configured
  6. Provider properties (provider_name, daily_limit)

## 구현 세부

### WebSearchResult dataclass
```python
@dataclass
class WebSearchResult:
    url: str
    title: str
    snippet: str
    source_domain: str  # 도메인 자동 추출
    score: float = 1.0  # 0.0~1.0
```

### BraveSearchProvider 주요 메서드
```python
async def search(query, num=8) -> list[WebSearchResult]:
    # 1. is_allowed("websearch:brave", WEBSEARCH_BRAVE_DAILY) 체크
    # 2. 초과 시 QuotaExhaustedError
    # 3. Brave API 호출 (httpx.AsyncClient)
    # 4. response.get("web").get("results") 파싱
    # 5. 429 응답 시 QuotaExhaustedError 발생
    # 6. 기타 오류 → ProviderUnavailableError
```

### 캐시 통합
- `cache_get()`: query_hash + provider로 composite 조회
- `cache_put()`: 기존 엔트리 업데이트 또는 신규 생성
- TTL 7일 (expires_at = now + 7d)
- Hit 시 DB.commit() 필수 없음 (읽기 전용)
- Put 시 DB.commit() 필수 (쓰기)

## Verify 체크

```bash
bash .claude/verify.sh phase-d-step2
```

- ✓ `backend/api/meta_core/web_search/{__init__,base,brave,cache,errors}.py` 존재
- ✓ `WebSearchProvider` ABC, `WebSearchResult` dataclass 정의
- ✓ `BraveSearchProvider` 클래스 존재 (provider_name, daily_limit, search 메서드)
- ✓ `cache_get()`, `cache_put()` 함수 존재
- ✓ 3개 exception 클래스 정의
- ✓ `backend/tests/meta_core/web_search/test_brave.py` 존재 (6 케이스)
- ✓ Import 정상 (no syntax error)

## 다음 스텝
D.3 — SerpAPI + Gemini Grounding + Ollama-DDG providers + factory

## 참고
- TabGet serper.ts 참고: https://github.com/search?... (import 안 함, 포팅만)
- Brave API 문서: https://api.search.brave.com/
