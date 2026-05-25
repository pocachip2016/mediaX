# Step 0: dpf-adr (Phase A)

> Milestone: dev-pipeline-detailed-flow

## 읽어야 할 파일
- mediaX-CMS/apps/web/app/(main)/programming/contents/pipeline/page.tsx (1438줄)
- backend/api/programming/metadata/models.py (ContentStatus enum)
- backend/api/programming/metadata/router.py (status 사용처)
- backend/api/test/pipeline_router.py (ADR-002 6-stage 콘솔, 보존 대상)
- backend/workers/ (email poll / enrich / websearch task)
- docs/dev/pt-pipeline-test-console/adr-002-* (대비 — 검증용 6-stage 흐름)

## 작업
운영 파이프라인 9-stage + 6-gate 설계를 ADR-006 으로 정리.

산출:
- `docs/dev/dev-pipeline-detailed-flow/adr-006-pipeline-stage-model.md` (결정 D1~D10)
- `docs/dev/dev-pipeline-detailed-flow/wireframes.md` (Board / Timeline V2 / Live Log + GatePanel)
- `docs/dev/dev-pipeline-detailed-flow/data-model.md` (enum / 컬럼 / migration / API)
- `plans/dev-pipeline-detailed-flow/index.json` (10 step)
- `plans/dev-pipeline-detailed-flow/step0~9.md` (skeleton)

ADR 본문 포함 항목:
- D1 9-Stage 모델 결정 (S1~S9)
- D2 Gate(수동 진행 버튼) 정책 6개 + 토글
- D3 status vs current_stage derived 관계
- D4 stage_event 테이블 (SSOT)
- D5 3-View UX
- D6 컴포넌트 재사용/신규 매트릭스
- D7 Step 계획 (10 step, 모델 전환 정책)
- D8 Out of Scope
- D9 Acceptance Criteria (전체 phase)
- D10 Risks + 완화

## Acceptance Criteria
```bash
/verify --skip "doc-only ADR + plan skeleton step"
```

## 금지사항
- 코드 수정 금지. 이유: Step 0 은 분석/설계 전용. 구현은 Step 1+.
- ADR 메인 < 190 라인 (feedback_doc_splitting) — 와이어프레임/데이터모델 분할.

## 상태
✅ Completed (2026-05-21)
