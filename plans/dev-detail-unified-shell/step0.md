# Step 0: dus-adr (Phase A)

> Milestone: dev-detail-unified-shell

## 읽어야 할 파일
- mediaX-CMS/apps/web/app/(main)/programming/contents/[id]/page.tsx (864줄)
- mediaX-CMS/apps/web/app/(main)/programming/contents/[id]/edit/page.tsx (96줄)
- mediaX-CMS/apps/web/app/(main)/programming/contents/[id]/recommend/page.tsx (261줄)
- mediaX-CMS/apps/web/app/(main)/programming/contents/review/page.tsx (495줄)
- mediaX-CMS/apps/web/components/contents/recommend/*
- mediaX-CMS/apps/web/components/contents/detail/*
- mediaX-CMS/apps/web/components/contents/{MetadataDiffPanel,MetadataEnrichPanel,ContentForm}.tsx

## 작업
콘텐츠 상세 통합 Shell 설계를 ADR-003 으로 정리.

산출:
- `docs/dev/dev-detail-unified-shell/adr-003-unified-shell.md`
- `plans/dev-detail-unified-shell/index.json`
- `plans/dev-detail-unified-shell/step0.md`

ADR 본문 포함 항목:
- D1 Unified Shell 결정 — 좌측(현재 상태) + 우측(모드별 액션)
- D2 우측 모드별 컨텐츠 — [A] 포스터 / [B] 시놉시스 / [C] 메타필드 / [D] Footer
- D3 URL 매핑 — ?mode=view|edit|review + 기존 /edit, /recommend redirect
- D4 컴포넌트 트리 — ContentShell + ViewPane/EditPane/ReviewPane
- D5 재사용/신규 매트릭스
- D6 Step 계획 (8 step, 모델 전환 정책 포함)
- D7 Out of Scope
- D8 Acceptance Criteria

## Acceptance Criteria
```bash
/verify --skip "doc-only ADR + plan skeleton step"
```

## 금지사항
- 코드 수정 금지. 이유: Step 0 은 분석/설계 전용. 구현은 Step 1+.
- ADR < 190 라인 (feedback_doc_splitting).
