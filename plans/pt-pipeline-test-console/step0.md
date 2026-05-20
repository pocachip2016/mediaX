# Step 0: pt-adr (Phase A)

> GitHub: 미생성 | Milestone: pt-pipeline-test-console

## 읽어야 할 파일
- backend/api/programming/metadata/router.py (파이프라인 엔드포인트)
- backend/api/programming/metadata/models/content.py (상태 enum, ContentBatchJob, audit/action log)
- backend/workers/tasks/metadata.py (process_content_metadata, enrich_content_metadata)
- backend/scripts/seed_sample_data.py (기존 시드 패턴 참고)
- mediaX-CMS/apps/web/app/(main)/programming/contents/pipeline/page.tsx (확장 대상)

## 작업
콘텐츠 등록 파이프라인 6단계 정의 + 콘텐츠별 추적 모델 + UI 청사진을 ADR-002로 정리.
산출:
- `docs/dev/pt-pipeline-test-console/adr-002-pipeline-test-console.md`
- `plans/pt-pipeline-test-console/index.json`
- `plans/pt-pipeline-test-console/step0.md`

ADR 본문 포함 항목:
- D1 6단계 SSOT (waiting/processing/staging/review/approved/published) + 전이 표
- D2 TEST_PIPELINE 시드 데이터 카탈로그 (15건)
- D3 /test/pipeline/* + /contents/{id}/timeline API 시그니처
- D4 UI 컴포넌트 트리 + ASCII 와이어프레임
- D5 재사용 매트릭스 + 신규 자산
- D6 가드레일 (admin role + ENABLE_PIPELINE_TEST env + cleanup 안전조건)
- D7 모델 전환 정책 (Opus Step 0~1 / Sonnet 2~8 / Haiku 9+verify)

## Acceptance Criteria
```bash
/verify --skip "doc-only ADR step"
```

## 금지사항
- 코드 수정 금지. 이유: Step 0은 분석/설계 전용. 구현은 Step 1+.
- 200줄 초과 시 분할 의무 (feedback_doc_splitting). 본 ADR 목표 < 190 라인.
