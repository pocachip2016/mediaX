# Step 5 — WebSearch 페이지 교체

**목표**: `external/page.tsx` stub → free-text 검색 화면 (진행형 로딩).

## 변경 파일
- `mediaX-CMS/apps/web/app/(main)/programming/contents/external/page.tsx`

## 상태머신
```
검색폼 상태: idle | searching | loaded | error
facet 상태:  none | stored | evaluating | fresh | eval_error
```

## 화면 구조
```
헤더: "MediSearch 외부 검색 — 제목으로 기본메타·Facet 확인"

[검색 폼]
  제목 (text, 필수)  |  제작연도 (number, 선택)  |  유형 (movie/series, 선택)  |  [검색]

[결과: 2컬럼]
  ┌─────────────────────────────┬───────────────────────────┐
  │  기본메타 + 출처              │  Facet 분석               │
  │  (MetaColumn, onApply 없음)  │  stored: 즉시 표시(배지)   │
  │  searching 중 → 스피너       │  none: "Facet 평가" 버튼   │
  │                              │  evaluating: Query 중...   │
  │                              │  fresh: 신규평가 렌더       │
  └─────────────────────────────┴───────────────────────────┘
```

## 핵심 동작
1. 제출 → `searching`: `medisearchApi.searchByTitle(query)` 호출
2. 응답 → 기본메타 컬럼 즉시 렌더. facet.origin=="stored" → facet 즉시 표시.
3. facet.origin=="none" → "이 후보로 Facet 평가" 버튼 표시.
4. 버튼 클릭 → `evaluating`: `medisearchApi.evaluateByTitle({title, production_year, tmdb_id, imdb_id})` 호출.
   "Query 중... (Facet 평가는 수 분 소요될 수 있습니다)" 메시지 + 스피너.
5. 응답 → `fresh` 렌더. 실패 → `eval_error` + 재시도 버튼.

## 주의
- 두 컬럼은 독립 — meta 응답이 오면 facet을 기다리지 않고 바로 렌더
- `FacetColumn`의 `onRequestEvaluate` prop 활용 (기존 컴포넌트와 동일 인터페이스)
- read-only (Apply 없음) → MetaColumn onApply 미전달

## 검증
```bash
cd mediaX-CMS && npm run typecheck 2>&1 | grep -E "error|Error" | head -20
# dev 서버에서 /programming/contents/external 진입 → 제목 검색 → 동작 확인
```
