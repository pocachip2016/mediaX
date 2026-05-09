# Step 7: field-aggregator

> GitHub: 미생성 | Milestone: dev-meta-intelligence (Phase B — 골격, B 진입 시점에 상세화)

## 읽어야 할 파일
- `backend/api/meta_core/field_strategy.py` (step6)
- `backend/api/meta_core/models/intelligence.py`
- `backend/api/programming/metadata/models/content.py` (ContentMetadata)

## 목적
FieldSuggestion 풀에 Strategy 적용 → FieldResolution 생성 → 자동 확정 시 ContentMetadata 에 반영.
**ContentMetadata 에 쓰는 유일한 합법 경로.**

## 작업 (윤곽)
- `backend/api/meta_core/aggregator.py`
  - `aggregate_content(content_id) -> AggregateReport`
    - 1단계: pending FieldSuggestion 조회 (content_id 기준)
    - 2단계: field_name 그룹핑 → FIELD_STRATEGIES[field] 적용
    - 3단계: 분류별 결정
      - A: agree_count + sum(source_weight) ≥ 가드 → decision=auto_agreement, applied_to_content=true
      - B: 멤버별 등장 ≥ threshold → union, applied_to_content=true (cap 적용)
      - C: 항상 decision=pending (검수자 대기)
      - D: source_priority + quality_fn 1위 → decision=auto_quality, applied_to_content=true
      - E: 모든 source 의 id 를 ExternalMetaSource 에 upsert (suggestion 도 superseded 로 마감)
    - 4단계: FieldResolution upsert (UNIQUE(content_id, field) 보존)
    - 5단계: applied_to_content=true 면 ContentMetadata 또는 ContentImage / ContentCredit 갱신
  - `aggregate_batch(content_ids)` (Beat 태스크용)
- 자동 확정된 row 의 source FieldSuggestion 은 status=applied 로 마감
- 충돌 case: 기존 FieldResolution 이 manual_pick 상태면 자동 덮어쓰기 X (manual 우선)

## Acceptance Criteria
```bash
# scenario: TMDB+KMDb 가 같은 director 제안 → auto_agreement
pytest backend/tests/meta_core/test_aggregator.py::test_director_auto_agreement
# scenario: TMDB/KMDb/네이버 줄거리 3개 → 모두 pending
pytest backend/tests/meta_core/test_aggregator.py::test_synopsis_pending
# scenario: poster 3개 → quality 1위만 적용
pytest backend/tests/meta_core/test_aggregator.py::test_poster_quality_pick
bash .claude/verify.sh meta-intelligence-step7
```

## 금지사항
- **FieldStrategy 우회 금지.** 분류·임계 모두 카탈로그 참조.
  이유: 카탈로그가 단일 진실원. 우회하면 운영 조정 막힘.
- **manual_pick 자동 덮어쓰기 금지.** 검수자 결정 보존.
  이유: 검수자가 "B 채택" 했는데 다음 enrich 가 auto 로 덮으면 신뢰 무너짐.
- **Aggregator 안에서 외부 API 호출 금지.** Suggestion 풀만 보고 결정.
  이유: enrich(step5) 와 책임 분리.
