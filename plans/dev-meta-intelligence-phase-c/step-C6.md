# Step C.6: seed-dedup-match

> GitHub: 미생성 | Milestone: dev-meta-intelligence-phase-c

## 읽어야 할 파일
- C.2~C.4 산출물 — `discovery/runner.py`, 3개 source
- `backend/api/meta_core/scoring.py` — compute_match_score 재사용
- `backend/api/meta_core/aggregator.py` — Phase B 집계 흐름
- `docs/dev/meta-intelligence-phase-c.md` §4 dedup 정책

## 작업

### 1. `api/meta_core/discovery/dedup.py`

**핵심 함수 `match_or_create_seed(db, result: DiscoveryResult)`**:
1. 동일 source_type + external_id 의 SEED 가 있으면 UPDATE → return (existing, "duplicate")
2. mediaX `Content` 와 비교:
   - 후보 검색: `title fuzzy + production_year ±1` SQL
   - 각 후보에 `compute_match_score()` 적용
   - max score ≥ 0.85 → SEED 미적재 + MatchEdge(target_type='content') 만 추가 → return (None, "matched_existing")
3. 다른 SEED 와 fuzzy match (title+year) ≥ 0.92:
   - 기존 SEED.alt_external_ids[source_type] = external_id 누적
   - return (existing, "alt_id_added")
4. 위 모두 미해당 → 신규 SEED INSERT → return (new, "created")

### 2. runner.py 통합
C.2 의 `run_discovery()` 가 raw insert 만 하던 부분을 `match_or_create_seed()` 로 교체.
log 의 카운터(`new_seeds`, `matched_existing`, `duplicates`) 분기 처리.

### 3. SQL 인덱스
production_year, title 의 fuzzy 검색 성능 — `pg_trgm` 의 `title gin_trgm_ops` 인덱스
(0012 마이그레이션에 포함되지 않았으면 0013 으로 추가).

### 4. 통합 테스트
- `tests/meta_core/test_seed_dedup.py` ≥ 8개:
  - 신규 발굴 → SEED 생성
  - 기존 SEED 재발굴 → UPDATE
  - 기존 Content 매칭 ≥ 0.85 → SEED 미생성, MatchEdge 추가
  - SEED 간 fuzzy match → alt_external_ids 누적
  - production_year ±1 허용 검증
  - 동시성: 같은 external_id 두 워커가 동시 적재 → ON CONFLICT 처리

## Acceptance Criteria
```bash
bash .claude/verify.sh phase-c-step6
```

- `from api.meta_core.discovery.dedup import match_or_create_seed` 통과
- pytest 8+ pass
- run_discovery 호출 후 seed_discovery_log.matched_existing > 0 인 시나리오 검증 (fixture)

## 금지사항
- match_score < 0.85 면서 SEED 도 만들지 않음 금지 — discard 대신 항상 새 SEED 로 적재
- alt_external_ids 에 confidence 기록 금지 — 그건 MatchEdge 의 영역
- 자동 SEED→Content 승격 금지 — 매칭 ≥ 0.85 여도 MatchEdge 만, 승격은 C.7
