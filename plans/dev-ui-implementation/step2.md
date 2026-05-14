# Step 2: shadcn Dialog 설치 + Add/Bulk 모달 통합

> GitHub: 미생성 | Milestone: dev-ui-implementation

## 읽어야 할 파일
- `mediaX-CMS/packages/ui/src/components/` (기존 shadcn 컴포넌트 패턴)
- `mediaX-CMS/apps/web/app/(prototypes)/add/page.tsx` (240줄, AddContentModal 원본)
- `mediaX-CMS/apps/web/app/(prototypes)/bulk/page.tsx` (187줄, BulkActionModal 원본)
- Step 0 결과: `(main)/programming/contents/page.tsx`
- `docs/dev/ui-consolidation/03_content_add.md` (3탭 모달 명세)
- `docs/dev/ui-consolidation/05_bulk_action.md` (3단계 흐름 명세)

## 작업

### 1. shadcn Dialog 설치 (`packages/ui`)

`packages/ui` 디렉토리에서:
```bash
pnpm dlx shadcn@latest add dialog
```

- 결과 파일: `packages/ui/src/components/dialog.tsx`
- 의존성 자동 추가: `@radix-ui/react-dialog`
- `cn()` 유틸 import 경로 확인 (기존 컴포넌트와 동일하게 `@workspace/ui/lib/utils`)

### 2. AddContentModal 컴포넌트 (`apps/web/components/contents/AddContentModal.tsx`)

shadcn Dialog 기반 모달. 프로토타입 add/page.tsx 의 3탭 구조 이식:

- **탭 1 — 단일 입력**: form 필드(제목/원제/년도/유형/CP/시놉시스) → `[저장]`
- **탭 2 — CSV 배치**: 드래그-드롭 업로드 + dry-run 미리보기(정상/누락/에러/중복 + 예상 비용) → `[실행]`
- **탭 3 — 외부 검색**: 검색 입력 + 매칭 카드 (TMDB/KOBIS/Watcha match%) → `[가져오기]`

Props: `open: boolean`, `onOpenChange: (open: boolean) => void`. 데이터 저장은 mock (console.log + alert).

### 3. BulkActionModal 컴포넌트 (`apps/web/components/contents/BulkActionModal.tsx`)

shadcn Dialog 기반. 프로토타입 bulk/page.tsx 의 3단계:

- **confirm**: 선택된 항목 리스트 + 사유 입력(textarea) + "다시 묻지 않음" 체크박스 → `[실행]`
- **progress**: 전체 진행바 + 항목별 상태(처리중/완료/실패) — 시각화는 mock setInterval
- **result**: 성공/실패 분류 카드 + `[되돌리기]` + `[다음 액션]`

Props: `open`, `onOpenChange`, `action: 'approve' | 'reject' | 'reprocess' | 'rematch'`, `targets: ContentSummary[]`.

### 4. contents/page.tsx 통합 (Step 0 결과물 수정)

- 우상단 `[+ 콘텐츠 추가 ▾]` 버튼 → AddContentModal 상태 토글
- sticky 액션 바의 4개 버튼 → BulkActionModal 호출 (action prop 전달)

## Acceptance Criteria

```bash
bash .claude/verify.sh ui-impl-3
```

- `packages/ui/src/components/dialog.tsx` 존재 + `@radix-ui/react-dialog` 가 package.json dependencies 에 등록됨
- `[+ 콘텐츠 추가]` 클릭 시 모달 열림, 3탭 전환 동작, ESC/백드롭 클릭으로 닫힘
- bulk 액션 바에서 `[승인]` 클릭 시 confirm → progress → result 흐름 (mock 진행 애니메이션)

## 금지사항

- API 실제 호출 X — 저장/실행은 mock console.log
- 다른 shadcn 컴포넌트(Tabs/Select 등) 무단 설치 X — Tabs 가 필요하면 native button 토글로 구현
- Step 4 의 정리 작업 미리 진행 X
