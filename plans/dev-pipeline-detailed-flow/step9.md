# Step 9: dpf-cutover (Phase E)

> Milestone: dev-pipeline-detailed-flow

## 작업
9-stage 모델로 운영 cutover + 기존 화면 호환 검증 + wrap.

산출:
- `backend/api/programming/metadata/service/status_view.py` (신규 또는 service.py 확장)
  - `status` 컬럼을 derived view 화하는 helper (실제 컬럼은 보존)
  - `current_stage` 갱신 시 자동으로 `status` 동기 갱신 보장
- 호환 검증 스위트 (수동 또는 신규 pytest)
  - `/programming/contents` 리스트 status 필터 동작
  - `/programming/metadata/staging` 검수 큐 정상
  - `/programming/contents/[id]` 상세 페이지 정상
  - `/programming/contents/review` BulkReviewQueue 동작
  - 기존 v1 timeline 호출자 무중단
- `TODO.md` 갱신 — Done 에 dev-pipeline-detailed-flow 추가, Later 정리
- `CLAUDE.md` 구현 현황 표 갱신 — dev-pipeline-detailed-flow 행 추가
- `docs/dev/dev-pipeline-detailed-flow/adr-006-pipeline-stage-model.md` Status: Proposed → Accepted

## 검증
```bash
cd backend && pytest tests/ -k "stage_event or timeline or pipeline_board" -v
cd mediaX-CMS && npm run typecheck
# manual QA:
#   1. TEST_PIPELINE 콘솔(6-stage)이 여전히 동작
#   2. 신규 PipelineBoard 9-stage 가 동작
#   3. GATE-3 클릭 → 5건 WebSearch 보강 → STAGING 진입
#   4. /monitoring/pipeline/log 라이브 스트림
#   5. 검수 큐·리스트 화면 status 필터 무중단
```

## Acceptance Criteria
```bash
/verify dpf-cutover
```

## Out of Scope (후속 phase 후보)
- 자동화 정책 (trusted_cp 화이트리스트 / quality≥90 자동 게시)
- stage_event 30일 archive job
- Datadog/Grafana 외부 메트릭 연동
- 게이트 권한 모델 (role-based)
