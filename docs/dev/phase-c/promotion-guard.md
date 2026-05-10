# §3. 승격 가드 (자동 금지)

> 소속: Phase C ADR — `_index.md` | 인접: §1 [lifecycle.md](lifecycle.md), §4 [dedup.md](dedup.md)

SEED → Content 승격은 **모든 경로에서 인간 액션이 1회 이상 개입** 하도록 강제한다.

## 3.1 자동 승격 절대 금지

- `confidence ≥ 0.95` 여도 SEED → Content 자동 전환 금지
- 이유: 발굴 소스의 false positive (예: TMDB 의 동명이작, KOBIS 의 재상영 등록)
  가 자동 등록되면 운영자 검수 화면에서 *왜 이게 등록됐는지* 추적 불가
- Phase B 에서 `>=0.95` 는 *동일 Content 매칭 자동확정* 임 — Phase C 의
  *신규 Content 생성* 과 책임 범위가 다르다. 같은 임계지만 다른 의미.

## 3.2 검토 잠금 (lock)

- 컬럼: `content_seeds.locked_by`, `locked_at`
- 잠금 진입: GET `/seeds/{id}` 시 자동 lock (단, 본인이 이미 잠근 경우 갱신만)
- 잠금 만료: `locked_at + 15분` 경과 시 unlock 가능
- 충돌 응답: 다른 사용자가 잠근 행을 GET 하면 200 + `{"locked_by": "...", "lock_remaining_sec": N}` 반환,
  편집 액션(accept/reject/edit) 호출 시 409

## 3.3 bulk-promote 정책

- 1회 요청당 max 50건 (`POST /seeds/bulk-promote`, body: `{"seed_ids": [...]}`)
- **하나라도** dedup 충돌 발견 시 전체 트랜잭션 abort — partial commit 금지
- abort 응답: 충돌 행 ID 목록 + 충돌 사유 (예: "Content #1234 와 match_score=0.91")
- 운영자 의도: bulk 는 *"이 50건 모두 신규" 라는 인간 판단의 일괄 표현* —
  중간에 매칭이 발견되면 그 판단 전제가 깨지므로 전체 중단이 안전

## 3.4 ExternalMetaSource 자동 작성

승격 트랜잭션 내에서 `ExternalMetaSource` 1행을 항상 함께 생성한다.

- `source_type` = 발굴 DiscoverySource 의 source 타입 (tmdb / kobis / kmdb / omdb)
- `external_id` = 원본 외부 ID
- `content_id` = 새로 생성된 Content.id
- `matched_at` = now() (자동 매칭 아님 — 인간 승인 시점)
- `match_score` = 1.0 (인간이 1:1 확정한 것이므로)

이 자동 작성을 빼면 신규 Content 가 Phase B aggregator 의 enrich 대상이 되지 못한다.

## 3.5 가드 위반 시 동작

- API 레이어: 422 + 가드 명시 메시지 (예: `"AUTO_PROMOTION_FORBIDDEN: human review required"`)
- 코드 레이어: SEED 승격 함수는 호출자에 `actor_user_id` 인자 강제 (default 없음)
