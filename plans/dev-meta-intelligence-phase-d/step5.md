# D.5 — WebSearchDiscoverySource (SEED 발굴)

## 목표
WebSearch 기반 SEED 발굴 (OTT 단독/신규 인디 콘텐츠).

## 산출물

### 백엔드 파일
1. **`backend/api/meta_core/discovery/websearch_source.py`**
   - `WebSearchDiscoverySource(DiscoverySource)` 구현
   - 3 mode:
     - `query`: 단일 쿼리 (e.g., "한국 드라마 2026")
     - `topic`: 주제 검색 (e.g., "OTT 단독 영화")
     - `trending`: 사전 정의 5개 쿼리 일괄 (넷플릭스, 디즈니, 쿠팡, 웨이브, 티빙)
   - LLM 구조화 추출: title, original_title, content_type, production_year
   - external_id: URL SHA256 prefix (10자)
   - Confidence base: 0.5 (Phase C 정책)

### 테스트 파일
- **`backend/tests/meta_core/discovery/test_websearch.py`** — 6개 케이스
  1. query mode 발굴
  2. topic mode 발굴
  3. trending mode 5개 쿼리 호출
  4. LLM 응답 JSON 파싱 (유효)
  5. LLM 응답 JSON 파싱 (무효)
  6. 동기 discover() 인터페이스

## 구현 세부

### Mode별 로직

#### query mode
```
input: query="한국 드라마 신작 2026"
→ search_query = f"{query} 영화 드라마 시리즈"
→ search_with_fallback(search_query)
→ LLM 추출 × N
```

#### topic mode
```
input: topic="OTT 단독 영화"
→ search_query = f"{topic} 한국 콘텐츠 2026"
→ search_with_fallback(search_query)
→ LLM 추출 × N
```

#### trending mode
```
_TRENDING_QUERIES = [
  "넷플릭스 신작 영화 2026",
  "디즈니플러스 예정작",
  "쿠팡플레이 한국 드라마",
  "웨이브 시리즈 신작",
  "티빙 독점 콘텐츠 2026"
]
→ for query in _TRENDING_QUERIES:
   search_with_fallback(query)
   LLM 추출 × N
→ 총 ~40건 (쿼리당 8개 × 5)
```

### LLM 추출 (Gemini→Groq→Ollama 폴백)

```python
prompt = f"""
웹 검색 결과:
- 제목: {title}
- 설명: {snippet}
- URL: {url}

JSON으로 추출:
{{
  "title": "한국명 또는 영문명",
  "original_title": "원어명 또는 null",
  "content_type": "movie/series 또는 null",
  "production_year": 2026 또는 null,
  "confidence": 0.5 (default)
}}
"""
```

### external_id 생성
```python
url_hash = SHA256(url)[:10]  # "a1b2c3d4e5"
# Ensures each URL = unique seed (even if dup content)
```

## Verify 체크

```bash
bash .claude/verify.sh phase-d-step5
```

- ✓ websearch_source.py 존재
- ✓ WebSearchDiscoverySource 클래스 정의
- ✓ discover(mode, **kwargs) 메서드 구현
- ✓ 3 mode (query, topic, trending) 지원
- ✓ _extract_with_llm() 비동기 메서드
- ✓ _parse_extraction_response() JSON 파싱
- ✓ test_websearch.py 존재 (6 케이스)
- ✓ search_with_fallback 통합 확인
- ✓ source_type = "websearch"

## On-demand 호출

```python
# discovery_tasks.py에서 (D.5 이후 단계):
from api.meta_core.discovery.websearch_source import WebSearchDiscoverySource
from api.meta_core.discovery.runner import run_discovery

source = WebSearchDiscoverySource(db)
run_discovery(db, source, mode="query", query="specific title")
# 또는
run_discovery(db, source, mode="trending")
```

**Bulk 호출 금지**: D.4 bulk guard로 자동 차단 (쿼리 100+ 불가)

## 다음 스텝
D.6 — Aggregator opt-in integration

## 참고
- DiscoverySource ABC: api/meta_core/discovery/base.py
- run_discovery runner: api/meta_core/discovery/runner.py
- Phase C 정책: docs/dev/phase-c/
