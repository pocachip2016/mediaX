# ADR-006 — Pipeline Stage Model (9-Stage + Manual Gates)

- **Status**: Proposed (2026-05-21)
- **Phase**: dev-pipeline-detailed-flow / Step 0
- **Related**: ADR-002 (pipeline test console, 6-stage), ADR-003 (unified shell)
- **Index**: 본 문서 = 결정만. 와이어프레임 → [wireframes.md], 데이터 모델 → [data-model.md]

## Context

현재 운영 파이프라인은 `Content.status` 단일 enum(7값)으로 진행을 추적한다.

| 한계 | 근거 |
|---|---|
| 입수 채널 부재 | email-poll / manual / bulk-csv / dam-webhook 모두 `status=waiting` |
| AI 처리 블랙박스 | `processing → staging` 사이 Ollama / TMDB / KOBIS / WebSearch 4 소스가 한 칸에 압축 |
| 보강 수동 게이트 없음 | WebSearch 자동 폴백 → 결과 확인 없이 다음 단계 진행 |
| 실패/반려 미분 | `rejected_by_human` 과 `failed_system` 색·집계 동일 |
| 이벤트 로그 부재 | `created_at/updated_at` 만 존재 — stage별 latency·provider 흔적 없음 |

ADR-002 의 6-stage 콘솔(`S0~S5`)은 **검증용**이라 운영 파이프라인의 SSOT 가 아니다.

## D1 — 9-Stage 운영 모델

```
S1 INTAKE → S2 NORMALIZE → S3 LLM-EXTRACT → S4 SOURCE-MATCH
   → S5 GAP-DETECT → S6 WEBSEARCH-FILL → S7 STAGING → S8 REVIEW → S9 PUBLISH
```

- **S1 INTAKE**: `intake_channel` enum (email_poll / manual / bulk_csv / dam_webhook) 기록
- **S4 SOURCE-MATCH**: TMDB · KOBIS · Dam-asset 3 소스 **병렬** 호출. 각각 hit/miss + latency 별 row
- **S5 GAP-DETECT**: 부족 필드 목록 생성. 충분 시 S6 스킵 → S7
- **S6 WEBSEARCH-FILL**: Brave → SerpAPI → Gemini → Ollama 4-provider 폴백 체인 (Phase D 그대로 활용)
- **S8 REVIEW**: 분기 3 (approve / reject / failed). reject 와 failed 별도 보관함

## D2 — Gate (수동 진행 버튼) 정책

| Gate | 위치 | 기본값 | 자동화 트리거 |
|------|------|--------|-------------|
| GATE-1 AI 시작 | S2→S3 | 🔒 수동 | trusted_cp 화이트리스트 |
| GATE-2 갭 진단 | S4→S5 | 🤖 자동 | (결정성 — 항상 자동) |
| GATE-3 WebSearch 보강 | S5→S6 | 🔒 수동 | quota·비용 |
| GATE-4 STAGING 진입 | S6→S7 | 🤖 자동 | |
| GATE-5 검수 결정 | S7→S8 | 🔒 수동 (영구) | 검수는 사람 |
| GATE-6 게시 | S8→S9 | 🔒 수동 | quality≥90 자동 게시 옵션 |

- 게이트는 **콘텐츠 단위 + 게이트 단위** 두 축으로 토글 (콘텐츠별 override 가능)
- 자동화 후보는 추후 cutover. ADR-006 본 작업은 **전부 수동**으로 시작.

## D3 — 상태(status) vs 스테이지(stage) 관계

`Content.status` 는 보존하되 `Content.current_stage` 를 신규 SSOT 로 둔다.

| current_stage | derived status |
|---|---|
| S1, S2 | waiting |
| S3, S4 | processing |
| S5, S6 | processing (또는 enrichment_blocked) |
| S7 | staging |
| S8 | review |
| approved/published | approved/published |
| rejected | rejected |
| failed | failed_enrichment |

기존 검수 큐·리스트 화면은 status filter 그대로 동작 → 무중단 cutover.

## D4 — `stage_event` 테이블 (SSOT for timeline / log)

```python
class StageEvent:
    id: int
    content_id: int                # FK Content
    stage: PipelineStage           # S1_INTAKE ~ S9_PUBLISH
    source: str | None             # tmdb / kobis / dam / brave / serpapi / gemini / ollama / user
    event_type: StageEventType     # entered / completed / skipped / failed / retried / advanced / gate_opened
    started_at: datetime
    ended_at: datetime | None
    latency_ms: int | None
    payload_json: dict | None      # provider 응답 요약 (size 캡 4KB)
    error_text: str | None
    actor: str                     # "system" | "user:<email>"
```

상세 컬럼·인덱스·migration → [data-model.md]

## D5 — 3-View UX

| View | 경로 | 용도 |
|------|------|------|
| Pipeline Board | `/programming/contents/pipeline` (기존 확장) | 운영자 — stage별 count + 게이트 트리거 |
| Content Timeline V2 | `/programming/contents/[id]?mode=view` 좌측 확장 | 콘텐츠별 9-stage + source 분기 |
| Live Event Log | `/monitoring/pipeline/log` (신규) | 실시간 stage_event stream (가상 스크롤) |

ASCII 와이어프레임 전체 → [wireframes.md]

## D6 — 컴포넌트 재사용/신규 매트릭스

| 컴포넌트 | 기반 | 비고 |
|---|---|---|
| `PipelineBoard` | 기존 `pipeline/page.tsx` 상단 카드 확장 | 6→9 stage, 채널 카드 3 신규 |
| `ChannelCard` | `PipelineStat` 변형 | 입수 채널 24h count |
| `GateButton` | 신규 | `<GateButton stage="GATE-3" mode count onAdvance>` |
| `GatePanel` (Drawer) | 기존 `BatchAiTrigger`/`BatchEnrichTrigger`/`TestReviewPanel` 통합 | 6 게이트 공통 UX |
| `ContentTimelineV2` | 기존 `ContentPipelineTimeline` 확장 | 6dot → 9dot + sub-row(provider) |
| `StageEventStream` | 신규 | `@tanstack/react-virtual` 가상 스크롤 |
| `FailureRejectionTabs` | 기존 `BulkReviewQueue` 분할 | 반려/실패 탭 분리 |

기존 `ContentPipelineTimeline` 의 6-stage 콘솔(ADR-002)은 **테스트 콘솔 전용**으로 남기고, 운영 화면은 V2 로 점진 교체.

## D7 — Step 계획 (10 step)

| # | Phase | 슬러그 | 작업 요약 | 산출 |
|---|---|---|---|---|
| 0 | A | dpf-adr | 본 ADR + wireframes + data-model 문서 | 3 md + index.json + step skel |
| 1 | B | dpf-schema | `stage_event` 테이블 + enum + alembic | migration + 5 pytest |
| 2 | B | dpf-service | `record_stage_event()` + 진입점 5곳 훅 | service.py + 4 pytest |
| 3 | B | dpf-timeline-api | `/contents/{id}/timeline` v2 | router + 6 pytest |
| 4 | B | dpf-board-api | `/pipeline/board` + 채널 통계 | router + 5 pytest |
| 5 | C | dpf-board-fe | `PipelineBoard` + `ChannelCard` + `GateButton` | tsc pass |
| 6 | C | dpf-gate-panel | `GatePanel` Drawer (6게이트 통합) | tsc pass |
| 7 | D | dpf-timeline-fe | `ContentTimelineV2` + unified shell 좌측 통합 | tsc pass |
| 8 | D | dpf-event-log | `/monitoring/pipeline/log` + `StageEventStream` | tsc pass |
| 9 | E | dpf-cutover | status→derived view + 호환 검증 + wrap | TODO/CLAUDE.md 갱신 |

**모델 전환**: Step 0 = Opus · Step 1~4 = Sonnet · Step 5~8 = Sonnet · verify/summary = Haiku.

## D8 — Out of Scope

- 자동화 정책 (trusted_cp · quality≥90 자동게시) — 본 ADR 은 수동 게이트 인프라까지만
- TEST_PIPELINE 콘솔(ADR-002) 의 V2 마이그레이션 — 콘솔은 6-stage 검증용으로 보존
- stage_event 의 외부 시스템 (Datadog/Grafana) 연동
- 게이트 권한 모델(role-based) — 1차는 모든 운영자 가능

## D9 — Acceptance Criteria (전체 phase 종료 시)

- 신규 콘텐츠 1건이 S1→S9 까지 진행하며 stage_event 9~13행 기록
- Pipeline Board 에서 GATE-3 클릭 → WebSearch 보강 5건 → 결과 확인 → STAGING 진입
- `Content.status` 기반 기존 검수 큐 / 리스트 / 상세 화면 무중단
- pytest 20+ pass · tsc clean · /verify dpf-cutover 통과

## D10 — Risks

| 위험 | 완화 |
|---|---|
| stage_event row 폭증 | content별 13 row 한도 + 30일 후 압축(JSON aggregate) |
| 기존 status 검사 코드 break | derived view + 단위 테스트로 1:1 대응 검증 |
| FE 게이트 토글 race | 게이트 advance API 는 idempotent (`If-Match: stage_event.id`) |
| 6-stage 콘솔 혼동 | TEST_PIPELINE 화면에 "검증용 — 운영 보드는 /pipeline" 안내 |
