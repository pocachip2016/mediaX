# Step 1: 콘텐츠 상세 5탭 (`/programming/contents/[id]`)

> GitHub: 미생성 | Milestone: dev-ui-implementation

## 읽어야 할 파일
- `mediaX-CMS/apps/web/app/(main)/programming/contents/[id]/page.tsx` (현재 구조)
- `mediaX-CMS/apps/web/app/(prototypes)/detail/page.tsx` (384줄, 이식 원본)
- `docs/dev/ui-consolidation/04_content_detail.md` (5탭 + 필드×3소스 카드 명세)
- Step 0 summary

## 작업

### 1. 헤더 영역
- 콘텐츠 제목 + 원제 + 연도
- 상태 배지 (UI 그룹 4종 + 처리중 실패 칩)
- 품질점수 (예: 78점)
- 우측 액션 버튼: `[승인]` / `[반려]` / `[AI 재처리]` (상태에 따라 활성화)

### 2. 5개 탭
프로토타입 detail 의 탭 구조 그대로 이식:

| 탭 | 내용 |
|----|------|
| 글자 | 시놉시스/장르/태그 — "필드 × 3소스 카드" (CP/AI/외부 라디오 선택) |
| 이미지 | 5개 그리드 (포스터/스틸컷 등) |
| 영상 | 영상 메타 폼 (해상도/길이/QC 결과) |
| 외부 소스 | TMDB/KOBIS/KMDB 3 카드 + 필드별 가져오기 모달 트리거 (모달 자체는 Step 2 의 add 모달과 별개 — 이번 step 에선 트리거 버튼만, 실제 모달은 mock alert) |
| AI 이력 | 엔진 비교 막대 + 시점별 출력 표 |

### 3. mock 우선
- `metadataApi.getContent(id)` 결과는 헤더 기본 정보(제목·연도)만 사용
- 탭 콘텐츠는 프로토타입 mock 그대로

## Acceptance Criteria

```bash
bash .claude/verify.sh ui-impl-2
```

- `/programming/contents/<id>` 접근 시 헤더 + 5탭 노출
- 각 탭 전환 시 콘텐츠 변경
- "외부 소스" 탭에서 라디오 선택 시 UI 반영 (저장은 mock)

## 금지사항

- 외부 소스 가져오기 모달 본격 구현 X — Step 2 의 shadcn Dialog 설치 후로 미룸 (이번 step 은 mock alert 또는 inline 표시)
- API 호출 변경 X
- 기존 (main)/programming/metadata/* 수정 X
