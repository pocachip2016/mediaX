# Step 3: 처리현황 페이지 + 기존 정리

> GitHub: 미생성 | Milestone: dev-ui-implementation

## 읽어야 할 파일
- `mediaX-CMS/apps/web/app/(main)/monitoring/pipeline/page.tsx` (이전 원본)
- `mediaX-CMS/apps/web/config/docs.ts` (Step 0 결과)
- `mediaX-CMS/apps/web/app/(main)/programming/metadata/` 11개 page.tsx (삭제 대상 — import 의존도 확인)
- Step 0~2 summary

## 작업

### 1. 처리 현황 페이지 신규 (`(main)/programming/contents/pipeline/page.tsx`)

기존 `monitoring/pipeline/page.tsx` 의 컨텐츠를 복사·재배치:
- KPI 카드 (오늘 통계: 처리/실패/대기/평균 처리시간)
- 실패 큐 (재시도 버튼)
- 배치 작업 이력

→ 컨텐츠 영역과의 일관성을 위해 `programming/contents/` 아래로 이동 (CLAUDE.md / docs/dev/ui-consolidation/02 §1.1 참조).

### 2. 사이드바 마무리 (`config/docs.ts`)

- "메타데이터 (레거시)" 그룹 + 하위 11개 항목 **삭제**
- "콘텐츠 관리" 그룹에 "처리 현황" 항목 추가 (콘텐츠 목록 아래)
- monitoring 섹션에서 "파이프라인" 항목 제거

### 3. 일괄 삭제 (rm)

- `apps/web/app/(main)/programming/metadata/` 전체 (11개 page.tsx + 디렉토리)
- `apps/web/app/(main)/monitoring/pipeline/`
- `apps/web/app/(prototypes)/` 전체 (list/detail/add/bulk 4개)

삭제 전:
- `metadataApi` 의 함수들 중 deprecated 페이지에서만 호출되던 것이 있는지 grep — 있으면 본 step 의 추가 정리로 분리 (또는 dev-api-consolidation 으로 위임)

### 4. 빌드 검증

```bash
cd mediaX-CMS && npm run build
```

orphan import 없이 통과해야 함.

## Acceptance Criteria

```bash
bash .claude/verify.sh ui-impl-4
```

- 사이드바에 "메타데이터" 라벨이 보이지 않음
- 사이드바 "콘텐츠 관리" 그룹에 "콘텐츠 목록" + "처리 현황" 2개 항목
- `/programming/contents/pipeline` 접근 시 KPI/실패큐/이력 렌더링
- `/programming/metadata/*` 접근 시 404
- `/list`, `/detail`, `/add`, `/bulk` (prototypes route group URL) 접근 시 404
- `npm run build` exit code 0

## 금지사항

- 백엔드 API 파일 삭제 X — UI 만 정리
- `metadataApi` 자체 삭제 X (Step 0~2 의 신규 페이지가 시그니처 참조)
- `(main)/monitoring/` 의 다른 항목 (incidents/quality/security) 변경 X
