# 개선 백로그 — 수동 단계 검증 중 수집

> Pipeline Test Console을 단계별 수동 진행하며 발견한 개선/버그 항목.
> 우선순위·분류 후 `index.json` steps 또는 별도 plan으로 승격.

## 분류 범례
- 🐛 버그  ·  ✨ 개선  ·  🎨 UX  ·  ⚙️ BE  ·  ❓ 확인필요

## 수집 항목

| # | 분류 | 단계 | 내용 | 비고 |
|---|------|------|------|------|
| 1 | ⚙️🐛 | ②AI처리 | CSV 업로드가 `process_content_metadata.delay()` 자동 dispatch → waiting에 머물지 않고 review 직행. 수동 진행 불가 | step0 근본원인. A안(auto_process 가드)으로 해결 예정 |
| 2 | ⚙️ | 전체 | `process_content_ai`가 staging(enrich) 건너뛰고 review/approved 직행 — 단일 전이로 분리 필요 | step1 BE 상태머신 |
| 3 | 🐛⚙️ | 환경 | ~~모든 LLM 엔진 실패 — Ollama가 요청 모델 `llama3.2:3b` 미설치(404), Gemini/Groq 키 없음~~ **해결**: `.env OLLAMA_MODEL=qwen3:4b`로 전환(설치된 모델) + backend·worker recreate. env 반영·backend 200 확인. 단 실제 LLM 처리 검증은 ②AI처리 단계에서 수동 관찰 예정 | 2026-05-29 해결. AI 처리 자동 트리거 금지 — AI 처리 단계 패널에서만 관찰 |
| 4 | 🐛✨ | 전체 | **stage_event 0건** — bulk-upload→process_content_ai 경로가 StageEvent(ADR-006 SSOT)를 기록 안 함 → PipelineBoard/LiveEventLog/타임라인 빈 화면 | step4 ProgressLog 전제. 처리 경로에 record_stage_event 삽입 필요 |
| 5 | 🐛❓ | ②AI처리 | **어벤져스(1229) 이상** — worker 로그에 없음(11건만 처리), created→updated 0.07s로 worker 미경유한 채 review 도달. 나머지 11건은 20:11:58 일괄 처리(각 0.4s) | 중복/idempotency 매칭 의심. 재현·조사 필요 |
| 6 | 🎨❓ | ②AI처리 | 업로드→worker pickup 약 62s 지연(큐 대기). 처리 자체는 0.4s | 관찰용 — 진행 로그에 큐 대기/처리 구분 표기 고려 |
| 7 | 🎨 | 테스트데이터 | 시드 품질점수가 90 미만(불완전 데이터 설계) → auto 모드 approved 연쇄 경로를 현 데이터로 관찰 불가 | "완전" 시드 1~2건은 90+ 나오도록 보정 검토 |

| 8 | 🐛⚙️ | ②AI처리 | **`/bulk/process` 500 → FE "Failed to fetch"** — router `response_model=BulkActionResponse`(job_id/ids_accepted/ids_rejected) 선언인데 `service.bulk_process`는 `JobStatusOut`(id/status/target_count…) 반환 → ResponseValidationError. router.py:877 / service_bulk.py:146 | 빠른 수정: response_model을 JobStatusOut으로 바꾸거나 반환을 BulkActionResponse로 매핑. FE 패널 result 표시도 정합 필요 |
| 9 | 🐛⚙️ | ②AI처리 | **`bulk_process`가 AI를 안 돌림** — `c.status=approved`로 직행(waiting→approved), `process_content_metadata` 미호출. 시놉시스/점수/ai_processed_at 불변. docstring "status=processed"와 실제(approved) 불일치 | ②"AI 처리 트리거"의 의미가 깨짐 — 실제 AI는 단건 `/contents/{id}/process`(process_content_metadata.delay)만 수행. step1 BE 상태머신에서 통합 — bulk도 진짜 AI 처리(waiting→processing) 하도록 |

<!-- 새 항목은 아래에 추가:
| 10 | 분류 | 단계 | 내용 | 비고 |
-->
