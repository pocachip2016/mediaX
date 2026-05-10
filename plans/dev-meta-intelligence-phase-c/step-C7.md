# Step C.7: seed-promote-api

> GitHub: 미생성 | Milestone: dev-meta-intelligence-phase-c

## 읽어야 할 파일
- C.1/C.6 산출물 — ContentSeed 모델, dedup 모듈
- `backend/api/meta_core/aggregator.py` — Phase B 집계 (승격 직후 트리거)
- `backend/api/meta_core/intelligence/router.py` — Phase B 검수 백엔드 패턴
- `docs/dev/meta-intelligence-phase-c.md` §3 승격 가드

## 작업

### 1. `api/meta_core/discovery/promote.py`

**`promote_seed(db, seed_id, actor: str) -> Content`**:
1. SEED row lock (`SELECT FOR UPDATE`)
2. status 체크 — `discovered`/`candidate`/`under_review` 만 허용 (`accepted`/`rejected` 거부)
3. dedup 재확인 — Content 매칭 ≥ 0.85 발견 시 RuntimeError("possible duplicate; reject or use existing")
4. Content INSERT — title/original_title/year/synopsis/poster from SEED
5. ExternalMetaSource INSERT — source_type=seed.source_type, external_id=seed.external_id, content_id=new_content.id
6. SEED status='accepted', promoted_to_content_id=new_content.id, locked_by=NULL
7. 비동기 Celery task 트리거: `enqueue_aggregate_content(content_id)` — Phase B aggregator 시작
8. return Content

### 2. POST 엔드포인트
`api/meta_core/intelligence/router.py` 에 추가:
```
POST /seeds/{seed_id}/promote
  body: { actor: str, override_dup: bool=false }
  → 200 { content_id, status: 'created' }
  → 409 { error: 'possible_duplicate', candidates: [...] }
  → 423 { error: 'locked_by_other', locked_by, locked_at }
```

### 3. 잠금 처리
- 다른 사용자 lock 보유 시 423 Locked + lock 정보 반환
- TTL 15분 — `locked_at + 15min < now()` 면 무시하고 진행

### 4. 단위 테스트
- `tests/meta_core/test_seed_promote.py` ≥ 7개:
  - 정상 승격 → Content INSERT, ExternalMetaSource INSERT, SEED status=accepted
  - 이미 accepted → 4xx
  - lock 보유 다른 사용자 → 423
  - lock TTL 만료 → 진행
  - dedup 재확인 → 409 (override_dup=false)
  - override_dup=true → 강제 승격
  - aggregator 트리거 mock 검증

## Acceptance Criteria
```bash
bash .claude/verify.sh phase-c-step7
```

- POST /seeds/{id}/promote 200/409/423 모두 검증
- pytest 7+ pass
- 승격 후 ExternalMetaSource 행 자동 생성 확인
- aggregator Celery task enqueue 검증 (mock)

## 금지사항
- bulk-promote 금지 — C.8 의 영역
- review actions(accept/reject/edit) 금지 — C.8 의 영역
- dedup 재검사 생략 금지 — 발굴 시점 ↔ 승격 시점 사이에 Content 추가됐을 수 있음
- aggregator 동기 호출 금지 — 반드시 Celery enqueue (응답 지연 방지)
