# Step 4 — FE 표현 컴포넌트 공유 추출

**목표**: `MediSearchPanel.tsx`의 표현 컴포넌트를 `MediSearchColumns.tsx`로 분리.
편집 패널 동작 유지, free-text read-only 지원.

## 변경 파일
- `mediaX-CMS/apps/web/components/contents/medisearch/MediSearchColumns.tsx` (신규)
- `mediaX-CMS/apps/web/components/contents/medisearch/MediSearchPanel.tsx` (import 교체)

## 이동 대상 (MediSearchPanel.tsx → MediSearchColumns.tsx)
- `META_FIELDS`, `FACET_SCORE_LABELS`, `FACET_LIST_LABELS` (라벨맵)
- `fmt`, `getMetaValue`, `getProvenance` (유틸)
- `ColHeader`, `FieldRow`, `FacetScoreBar` (원자 컴포넌트)
- `MetaColumn`, `FacetColumn` (컬럼 컴포넌트)

## `MetaColumn.onApply` optional화
```ts
// 변경 전
onApply(field: string): void

// 변경 후
onApply?: (field: string) => void

// 렌더: onApply 없으면 Apply/적용됨 버튼 섹션 미렌더
{onApply && !isApplied && (
  <button onClick={() => onApply(key)}>Apply</button>
)}
```

## 검증
```bash
cd mediaX-CMS && npm run typecheck 2>&1 | grep -E "error|Error" | head -20
# MediSearchPanel이 기존대로 렌더되는지 확인 (컴파일 통과 = 동작 불변)
```
