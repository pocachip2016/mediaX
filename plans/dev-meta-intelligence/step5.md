# Step 5: enrich-to-suggestions-with-kmdb

> GitHub: 미생성 | Milestone: dev-meta-intelligence (Phase B — 골격, B 진입 시점에 상세화)

## 읽어야 할 파일
- `docs/dev/meta-intelligence.md` (§6 KMDb)
- `backend/api/meta_core/scoring.py` (step2)
- `backend/api/meta_core/gap.py` (step4)
- `backend/workers/tasks/metadata.py` (현재 enrich_content_metadata)
- `backend/api/programming/metadata/tmdb_client.py` (TMDB 클라이언트 패턴)

## 목적
GapReport 가 지정한 외부 소스를 호출 → MetadataCandidate 적재 → MatchEdge 생성 → FieldSuggestion 분해.
**현 enrich_content_metadata 가 ContentMetadata 에 직접 쓰던 동작을 끊고 candidate/suggestion 흐름으로 우회.**

## 작업 (윤곽)
- `backend/api/meta_core/clients/kmdb_client.py` 신설
  - `KmdbClient(api_key=env KMDB_API_KEY, base_url="http://api.kmdb.or.kr/openapi-data2/")`
  - `.search_movie(title, year=None) -> list[dict]`
  - `.get_movie_detail(docid) -> dict`
  - 응답 캐시: `external_sync_log` 활용, raw 는 `metadata_candidates.raw_payload`
- `backend/api/meta_core/enrich.py` 신설
  - `enrich_content(content_id) -> EnrichResult`
  - 흐름: Gap 분석 → 각 소스 호출 → candidate upsert → MatchEdge 계산(scoring.py) → 분류(auto/review/hold/drop) → FieldSuggestion 분해(필드별 정규화)
  - 결과: candidate 수, match_edge 수, suggestion 수, drop 수
- `workers/tasks/metadata.py:enrich_content_metadata` 리팩토링
  - 기존 ContentMetadata 직접 쓰기 제거
  - `meta_core.enrich.enrich_content(id)` 호출로 대체
- `TmdbSyncSource` ENUM 에 `kmdb_daily`, `kmdb_backfill` 추가 (alembic 보강 0012)
  - 0011 와 분리 이유: ENUM 추가는 PostgreSQL 트랜잭션 밖 실행 필요
- KMDb sync Beat 태스크는 **추가하지 않음** (Phase C 전엔 on-demand 만)

## Acceptance Criteria
```bash
# KMDb 키 미설정 시 silent skip
KMDB_API_KEY= python3 -c "from api.meta_core.enrich import enrich_content; print('OK')"
# enrich 호출 → candidate/suggestion 행 생성 확인
pytest backend/tests/meta_core/test_enrich.py
bash .claude/verify.sh meta-intelligence-step5
```

## 금지사항
- **ContentMetadata 직접 쓰기 금지.** suggestion → resolution → 적용 은 Aggregator(step7) 책임.
  이유: audit trail 보장.
- **KMDb Daily Beat 등록 금지.** 본 step 은 on-demand enrich 만.
  이유: Phase C 의 SEED 흐름에서 일괄 통제.
- **KMDb 키 없이 raise 금지.** `KMDB_API_KEY` 미설정 시 source 만 skip.
  이유: 다른 소스(tmdb/kobis) 만으로도 enrich 동작해야 함.
