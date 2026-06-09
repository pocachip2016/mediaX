# ADR-012-01: 자동편성 파이프라인 모델 (P-stage / 버킷 / 정책)

> 부모: [adr-012-auto-schedule_index.md](adr-012-auto-schedule_index.md)

## 대상 단위 = ProgrammingNode

콘텐츠 파이프라인이 *Content* 를 `current_stage` 로 전이시키듯, 자동편성은 `auto_enabled=True` 인
**노드**를 `auto_stage` 로 전이시킨다. 노드의 정체성(rule_query/headline/window)은 이미 ADR-011에 있고,
여기서는 **단계 전이 + 단계별 실행**만 추가한다.

## P-stage (6단계)

| Stage | 의미 | 실행 로직 (재사용) |
|-------|------|------------------|
| `P1_DEFINE` (조건정의) | rule_query·headline_copy(의도)·window 가 채워진 intake 상태 | 입력 검증만 |
| `P2_CANDIDATE` (후보생성) | Tier0 규칙으로 후보 콘텐츠 산출(read-time, 저장 안 함) | `rule_engine.apply_rule_query` |
| `P3_MATCH` (AI매칭) | Tier1 의도해석 + Tier2 의미매칭 → `suggested` 링크 저장 | `intent_service.interpret_intent` + `suggest_service.suggest_links` |
| `P4_AUTOCONFIRM` (자동확정) | confidence ≥ threshold suggested → active. 미달 1건↑ 존재 시 검수 잔류 | `suggest_service.confirm_link` |
| `P5_CONFLICT` (충돌검사) | set 내 노출 window 겹침·중복 content_id dedup 점검 | 신규 `conflict_service.detect_conflicts` |
| `P6_PUBLISH` (발행) | 노드의 set `status=published` → 서비스 편성표 발행 | NodeSet publish |

## 버킷 매핑 (콘텐츠 `_STAGE_BUCKET` 패턴)

| 버킷 | 포함 stage | 처리 유형 | next stage |
|------|-----------|----------|-----------|
| 1 | P1_DEFINE | intake | P2 |
| 2 | P2_CANDIDATE, P3_MATCH | 후보·매칭 | P4 |
| 3 | P4_AUTOCONFIRM | 자동확정 | P5 |
| 4 | P5_CONFLICT | 검수(충돌 확인) | P6 |
| 5 | P6_PUBLISH | terminal | — |

- **잔류(auto_skipped_at)**: P4에서 임계값 미달 suggested 가 남으면 마킹 → claim 에서 제외(무한 재평가 방지).
  정책 threshold 변경 시 일괄 clear → 재평가 재개(콘텐츠 `auto_review_skipped_at` 동일).
- **claim**: `auto_enabled=True` + `auto_hold=False` + `FOR UPDATE SKIP LOCKED` + visibility_timeout 재claim.
- **멱등 advance**: txn 내 선조건 재확인 → 이미 이동 시 no-op. 실제 전이만 `SchedulingStageEvent` 기록.

## ScheduleAutoPolicy (싱글톤)

| 필드 | 기본값 | 의미 |
|------|--------|------|
| `p2_auto`…`p6_auto` | true | per-stage AUTO 토글(해당 버킷 자동 전이 허용) |
| `confidence_threshold` | 0.5 | P4 자동확정 임계값 |
| `auto_tick_enabled` | false | Beat tick 활성(기본 꺼짐 — 운영자 명시 활성) |
| `batch_size` | 20 | tick 당 claim 수 |
| `visibility_timeout` | 300 | claim stuck 재claim 초 |

## recompute_schedule_score (0~100)

편성 완성도 = active 링크 수(가중) + window 충족 + headline 유무. P5 진입 시 재계산(콘텐츠 quality_score 패턴).
점수는 콘솔 표시·발행 판단 보조용(자동확정 게이트는 confidence_threshold 가 담당).

## 불변 규칙

1. AI 매칭은 P3에서 `status=suggested` 로만 저장 — 자동 노출 금지(ADR-011 계승).
2. P4 자동확정은 `confidence ≥ threshold` 만 — 미달은 검수 잔류, 절대 자동 active 안 됨.
3. Tier0(P2) 산출 멤버는 저장 안 하고 read-time — ai 확정분만 active 영속(ADR-011 계승).
4. P6 발행은 P5 충돌 0건일 때만 자동 진행 — 충돌 있으면 잔류(운영자 해소 후 진행).
