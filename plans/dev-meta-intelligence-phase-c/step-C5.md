# Step C.5: omdb-client

> GitHub: 미생성 | Milestone: dev-meta-intelligence-phase-c

## 읽어야 할 파일
- C.1 산출물 — ExternalSourceType.omdb 추가 확인
- `backend/api/meta_core/clients/kmdb_client.py` (클라이언트 패턴 참고)
- `backend/shared/config.py` (Settings 패턴)

## 작업

### 1. `api/meta_core/clients/omdb_client.py`

**`OmdbClient`**:
- `OMDB_API_KEY` 환경변수 (`shared/config.py` 추가)
- BASE: `https://www.omdbapi.com/`
- 메서드:
  - `get_by_imdb_id(imdb_id)` → 단건 조회
  - `search_by_title(title, year=None)` → 검색
  - `get_by_tmdb_imdb(tmdb_external_ids)` → TMDB 의 imdb_id 로 cross-lookup

### 2. Rate limiter (Free tier 1000/day)
`shared/redis_rate_limit.py` 패턴 재사용 (KOBIS 에서 이미 구축):
- key: `omdb:daily:{YYYYMMDD}`
- INCR + EXPIRE 86400
- limit 도달 시 RuntimeError → 호출자가 fallback

### 3. ExternalMetaSource 통합
`enrich_content()` (Phase B step5) 에 OMDb 분기 추가:
- TMDB 결과의 `external_ids.imdb_id` 가 있으면 OMDb 조회
- 결과 → MetadataCandidate (source_type='omdb') + FieldSuggestion 변환
- 분야: `synopsis` (Plot), `runtime`, `imdb_rating`, `country`, `language`

### 4. Discovery 미사용
OMDb 는 발굴(discovery) 소스 아님 — **enrich 보강 전용**.
이 step 은 클라이언트 + Phase B enrich 통합만. discovery_source 는 만들지 않음.

### 5. 단위 테스트
- `tests/meta_core/test_omdb_client.py` ≥ 6개:
  - 정상 응답 파싱
  - Response=False 처리
  - rate limit 도달 시 RuntimeError
  - imdb_id cross-lookup 시 TMDB external_ids 의 imdb 키 누락 → None
  - mock httpx

## Acceptance Criteria
```bash
bash .claude/verify.sh phase-c-step5
```

- `from api.meta_core.clients.omdb_client import OmdbClient` 통과
- pytest 6+ pass
- `OMDB_API_KEY` env 미설정 시 RuntimeError (구체 메시지: "OMDB_API_KEY missing")
- enrich_content 가 OMDb 결과를 ExternalMetaSource(omdb) 로 저장하는 흐름 검증 (mock)

## 금지사항
- OmdbDiscoverySource 만들지 마라 — OMDb 는 보강 전용
- 자유 텍스트 검색을 메인 경로로 쓰지 마라 — imdb_id cross-lookup 우선
- 1000/day 한도 무시 금지 — 항상 rate limit 통과 후 호출
