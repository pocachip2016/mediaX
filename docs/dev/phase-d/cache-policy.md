# §5. Cache Policy

## WebSearchCache 모델 (재활용)

테이블 `web_search_cache` 는 alembic 0008 (`dev-meta-core-extraction`) 에서 이미 생성됨.
Phase D 에서는 alembic 0013 으로 `provider` 컬럼만 추가:

```python
# 기존 (0008)
class WebSearchCache(Base):
    __tablename__ = "web_search_cache"
    id = Column(Integer, primary_key=True)
    query_hash = Column(String(64), unique=True, index=True)  # SHA256 hex
    query = Column(Text)
    results_json = Column(JSON)
    expires_at = Column(DateTime, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

# Phase D 추가 (0013)
provider = Column(String(20), index=True, default="brave")  # brave/serpapi/gemini/ollama
```

unique key 는 `(query_hash, provider)` 컴포지트로 변경 (기존 query_hash 단독 unique 제거).

## TTL 7일

- 신규 영화/드라마 정보가 7일 이내 크게 바뀔 가능성 낮음 (포스터/시놉시스/캐스트 안정)
- 7일 후 자동 갱신 (`expires_at < now` 인 row 무효 처리)
- 강제 무효화 API 없음 (운영 단순화)

## SHA256 Key 생성

```python
def make_query_hash(query: str, lang: str = "ko") -> str:
    """
    동일 쿼리 + 동일 언어 = 동일 hash.
    공백 정규화, 소문자 변환 후 SHA256.
    """
    normalized = " ".join(query.lower().split())
    return hashlib.sha256(f"{normalized}|{lang}".encode()).hexdigest()
```

## Cache Get / Put

```python
def cache_get(db: Session, query: str, provider: str) -> list[WebSearchResult] | None:
    qh = make_query_hash(query)
    row = db.query(WebSearchCache).filter(
        WebSearchCache.query_hash == qh,
        WebSearchCache.provider == provider,
        WebSearchCache.expires_at > datetime.utcnow(),
    ).first()
    if row:
        return [WebSearchResult(**r) for r in row.results_json]
    return None

def cache_put(db: Session, query: str, provider: str, results: list[WebSearchResult]) -> None:
    qh = make_query_hash(query)
    db.merge(WebSearchCache(
        query_hash=qh,
        provider=provider,
        query=query,
        results_json=[asdict(r) for r in results],
        expires_at=datetime.utcnow() + timedelta(days=7),
    ))
    db.commit()
```

## Provider 분리 이유

같은 쿼리라도 provider 별 결과가 다름 (Brave vs SerpAPI 결과 ≠ 동일).
→ provider 컬럼으로 분리 캐시. 폴백 체인이 Brave 소진 → SerpAPI 호출 시 SerpAPI 캐시 별도 생성.

## 캐시 히트 측정

`/api/meta-core/web-search/cache-stats?days=7` 응답:

```json
{
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

측정 방법:
- `cache_get` 호출 시 hit/miss 를 Redis 카운터 (`websearch:cache:{provider}:{hit|miss}:daily:YYYYMMDD`) 에 기록
- API 가 7일/30일 합산 후 비율 계산
- 0 호출 provider 는 응답에서 제외

## 캐시 미스 시 비용 절감

7일 hit_rate 70% 가정 시:
- Brave 일 60 정책 × 30일 = 1800 호출 capacity
- 실제 신규 호출은 1800 × 30% = 540 호출 = 무료 한도 27% 사용
- 나머지 70% 는 cache 응답 → 0 quota

→ cache 가 사실상 quota 한도를 3배 확장.
