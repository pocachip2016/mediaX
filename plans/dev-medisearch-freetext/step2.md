# Step 2 — 백엔드 헬퍼 분리 + free-text 엔드포인트

**목표**: `router_medisearch.py` 리팩터 + 신규 `/medisearch/search`, `/medisearch/evaluate` EP.

## 변경 파일
- `backend/api/programming/metadata/router_medisearch.py`

## 작업 내용

### (a) 순수 헬퍼 추출
- `_call_medisearch_enrich(payload: dict) -> dict` — httpx POST /api/movies/enrich
- `_load_stored_facet_by_tmdb(tmdb_id: int, db) -> MediSearchFacetInfo` — TmdbMovieFacet 조회
- 기존 `_load_stored_facet`: 1순위(ContentAIResult) 후 `_load_stored_facet_by_tmdb` 호출
- 기존 `medisearch_search`: httpx 블록 → `_call_medisearch_enrich` 위임

### (b) 신규 스키마
- `MediSearchFreeRequest(title, production_year?, content_type?, original_title?)`
- `MediSearchFreeResult(query, metadata, provenance, sources_detail, resolved_tmdb_id?, resolved_imdb_id?, facet)`
- `MediSearchEvaluateRequest(MediSearchFreeRequest + tmdb_id?, imdb_id?)`

### (c) 신규 엔드포인트
- `POST /medisearch/search` — enrich 호출 → tmdb_id 해석 → 저장 facet 첨부(없으면 none)
- `POST /medisearch/evaluate` — evaluate 호출 → success + tmdb_movie_cache FK 존재 시 upsert

## 주의사항
- `TmdbMovieFacet.tmdb_id` FK → `tmdb_movie_cache.id` → 저장 전 존재 여부 가드 필수
- `_upsert_tmdb_facet` (workers/tasks/facet_tasks.py:144) 재사용
- `_decide_facet_outcome` (facet_tasks.py:37) 재사용
- 기존 content-bound EP(`/contents/{id}/medisearch/search`, `/contents/{id}/medisearch/facet`) 회귀 없음

## 검증
```bash
# 도커 실행 중 상태에서
curl -s -X POST http://localhost:8000/api/programming/metadata/medisearch/search \
  -H "Content-Type: application/json" \
  -d '{"title":"올드보이","production_year":2003}' | python3 -m json.tool | grep -E "query|resolved_tmdb|origin"
```
