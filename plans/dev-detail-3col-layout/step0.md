# Step 0: adr-and-cancel-dai (Phase A)

> Milestone: dev-detail-3col-layout

## 작업
- 상세 화면 3컬럼 레이아웃 ADR-005 작성 (view 2컬럼 / edit·review 3컬럼 + 하단 AI 종합)
- 진행 중이던 `dev-detail-api-integration` plan을 본 plan으로 통합하여 cancelled 처리
- 본 plan skeleton 생성 (index.json + step0.md)

## 결정 사항
1. **view 모드**: Diff·AI 추천 제거 → 2컬럼 (Poster + ContentShell)
2. **edit/review 모드**: 3컬럼 (Poster+썸네일 / 현재 상태 / AI 추천) + 하단 AISummaryBottom
3. **edit 모드는 인라인 편집**으로 review와 동일한 3컬럼 구조에 통합 (EditPane 삭제)
4. dai Step 2(mock fallback)는 이미 `page.tsx` 119–159에 구현됨 → 중복이므로 dai 취소
5. dai Step 3(E2E)·4(wrap)는 본 plan의 Step 6에 흡수

## 산출
- `docs/dev/dev-detail-3col-layout/ADR-005-three-column-layout.md`
- `plans/dev-detail-3col-layout/index.json`
- `plans/dev-detail-3col-layout/step0.md`
- `plans/dev-detail-api-integration/index.json` — Steps 2-4 `status: cancelled` + 사유 기록

## Acceptance Criteria
```bash
/verify --skip "doc-only: ADR + plan skeleton + dai cancellation"
```

## 금지사항
- 코드 수정 금지. Step 0은 분석/설계 + plan 정리 전용.
- 기존 dai step 파일(step0.md, adr-004)은 보존 (히스토리).
