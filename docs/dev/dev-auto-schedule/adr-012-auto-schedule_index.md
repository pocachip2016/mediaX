# ADR-012: 자동편성 파이프라인 (Auto-Programming Pipeline)

> Status: **Proposed** · Date: 2026-06-09 · Builds on: ADR-011(편성 Node/Link DAG), ADR-010(콘텐츠 파이프라인 AUTO)
> Task: `plans/dev-auto-schedule/` · Module: `backend/api/programming/scheduling/`

## 1. 배경 / 문제

ADR-011로 편성 DAG(`ProgrammingNode`/`Link`)와 Tier0/1/2 AI 매칭이 완성됐다. 하지만
현재 흐름은 **운영자가 노드마다 수동으로 `suggest → confirm`** 을 눌러야 콘텐츠가 편성된다.

요구: *"특정 조건이 충족되면 자동으로 편성"* — 운영자가 노드에 **조건(rule_query)+의도(headline)+노출기간(window)**
만 정의해 두면, 시스템이 **후보생성 → AI매칭 → 자동확정 → 충돌검사 → 발행**까지 단계적으로
자동 진행해야 한다. 콘텐츠 등록 파이프라인 콘솔(ADR-010 AUTO 모드)이 *Content* 에 대해 하는 일을,
편성은 *Node* 에 대해 해야 한다.

핵심 미지원: **① 노드 단위 단계 전이(스테이지)** **② 조건 충족 시 자동 발동(Beat/이벤트/온디맨드)**
**③ 자동확정 임계값 + 잔류(검수 대기) 처리**.

## 2. 결정

**미러링(Mirror).** 콘텐츠 파이프라인 AUTO 패턴(ADR-010 `pipeline_auto_service`)을 편성 노드 컨텍스트로
재작성해 **자동편성 파이프라인**을 만든다. 대상 단위는 `auto_enabled=True` 인 **ProgrammingNode**.

핵심 원칙(ADR-011 계승): **AI는 추천, 자동확정은 임계값 기반, 미달은 사람 검수로 잔류.**
- 발행 대상 = 기존 `ProgrammingNodeSet`(draft→published) **재사용**. 신규 lineup 테이블 신설하지 않음.
- 각 단계는 기존 Tier 서비스 재사용(`rule_engine`/`intent_service`/`suggest_service`).

신규 자산:
- `ProgrammingNode` 에 AUTO 추적 필드(`auto_enabled`/`auto_stage`/`auto_hold`/`auto_claimed_at`/`auto_skipped_at`)
- `SchedulingStageEvent` — 노드 단계 전이 SSOT(콘텐츠 `StageEvent` 구조 복제)
- `ScheduleAutoPolicy` — 싱글톤 정책(per-stage AUTO 토글 + confidence 임계값 + tick 활성)
- `scheduling/auto_service.py` — claim/advance/run-to-stable + per-stage 실행
- `workers/tasks/scheduling_auto.py` — Beat tick

섹션 문서:
- [01. 파이프라인 모델 (P-stage / 버킷 / 정책 / 점수)](adr-012-01-pipeline-model.md)
- [02. 트리거 3종 (Beat · 콘텐츠 이벤트 · 온디맨드)](adr-012-02-triggers.md)

## 3. 결과 / 영향

- ✅ 운영자는 노드에 조건만 정의 → 후보생성·AI매칭·자동확정·발행 자동 진행
- ✅ 기존 Tier0/1/2 + `suggest_service` 그대로 재사용(중복 구현 없음)
- ✅ 콘텐츠 파이프라인과 **동일한 멱등/잔류/visibility_timeout 규칙** → 운영 일관성
- ✅ 임계값 미달 suggested 는 **검수 잔류**(자동 발행 안 됨) — human-in-the-loop 유지
- ✅ 발행은 `ProgrammingNodeSet.status=published` 로 귀결 — 서비스 편성표 = NodeSet
- ⚠ 대상이 Content 가 아니라 Node — 콘텐츠 코드 복붙 금지, 노드 상태축으로 재작성
- ⚠ 이벤트 트리거 과호출 위험 — `auto_enabled` + published set 으로 대상 한정 필수

## 4. 대안 (기각)

- **수동 유지(현행)**: 노드마다 클릭 필요 — 대량 편성 비효율. 자동화 목적상 기각.
- **신규 ServiceLineup 테이블 신설**: NodeSet 과 중복 개념 — 이관 빚. NodeSet 재사용으로 기각.
- **시간대/채널 그리드 편성**: VOD 중심이라 방송 타임슬롯 불필요. 범위 외(기각).
