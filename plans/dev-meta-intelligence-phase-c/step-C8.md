# Step C.8: seed-review-backend

> GitHub: 미생성 | Milestone: dev-meta-intelligence-phase-c

## 읽어야 할 파일
- C.7 산출물 — promote_seed
- `backend/api/meta_core/intelligence/router.py` Phase B 검수 패턴
- `backend/api/meta_core/intelligence/schemas.py`

## 작업

### 1. `api/meta_core/intelligence/seed_schemas.py`
- `SeedListItem`, `SeedListResponse` (페이징 + 필터 결과)
- `SeedDetail` — alt_external_ids, raw_payload, MatchEdge 후보
- `SeedAcceptRequest`, `SeedRejectRequest`, `SeedEditRequest`
- `SeedBulkPromoteRequest` — `seed_ids: list[int]`, `actor`, `max=50`

### 2. GET 엔드포인트
- `GET /seeds` — 필터 (status, source_type, content_type, year_from/to, locked) + 페이징 + 정렬(discovered_at/score)
- `GET /seeds/{id}` — SEED detail + MatchEdge 후보 (Content 매칭 candidates)
- `GET /seeds/stats` — status별 카운트, source_type별 카운트, 최근 7일 추이

### 3. POST 엔드포인트 (검수 액션)
- `POST /seeds/{id}/lock` — under_review 로 전환 + locked_by/locked_at 설정
- `POST /seeds/{id}/unlock` — 잠금 해제 (본인만)
- `POST /seeds/{id}/accept` — `accept` = 즉시 promote (C.7) 호출
- `POST /seeds/{id}/reject` — status=rejected + reason 기록 (raw_payload 에 push)
- `POST /seeds/{id}/edit` — title/year/synopsis 수정 (사람이 보정 — 승격 전 단계)
- `POST /seeds/bulk-promote` — list[seed_id] 순차 승격, 실패시 부분 성공 반환 (transactional 아님 — 항목별 commit)

### 4. 권한
- `actor` 헤더 또는 body — 누가 승격했는지 audit trail 용
- 권한 체크는 본 step 범위 외 (1.4 결재 워크플로우 영역) — actor 만 기록

### 5. 단위 테스트
- `tests/meta_core/test_seed_review.py` ≥ 12개:
  - GET /seeds 필터/페이징/정렬
  - lock → unlock 플로우
  - accept → Content 생성 (promote 통합)
  - reject → status 변경 + reason 기록
  - edit → 필드 수정 + updated_at 갱신
  - bulk-promote 전체 성공
  - bulk-promote 일부 실패 → 부분 결과 반환
  - bulk-promote max 50 초과 → 400

## Acceptance Criteria
```bash
bash .claude/verify.sh phase-c-step8
```

- 7개 신규 엔드포인트 모두 200/4xx 정상 응답
- pytest 12+ pass
- bulk-promote 가 transactional 아님을 확인 (10건 중 3건 실패해도 7건 성공 반환)

## 금지사항
- 승격 actor 공란 허용 금지 — 항상 actor 필수
- bulk-promote transactional 금지 — 항목별 try/except 로 부분 성공
- edit 후 자동 promote 금지 — 항상 별도 accept 호출
- raw_payload 직접 수정 허용 금지 — edit 는 화이트리스트 필드만
