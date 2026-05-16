# Step 6: Bulk Review Summary 보강

## 목적
237건 같은 대량 데이터에서 빠른 triage. 잘못된 일괄 승인 방지.

## 상단 Summary 6칸 확정
```
Total | Missing | Conflict | Needs Poster | Dam Match | High Risk
```
Step 1 응답의 `summary` 그대로 사용. 각 카드 클릭 = 해당 필터 토글.

## 필터 (다중 chip)
- All
- metadata_status: Missing / Conflict / Enhancement / Clean
- poster_status: Needs Selection / External Only / Dam Match
- risk_level: Low / Medium / High
- input_type: Bulk / Manual / Existing

조합은 AND. 활성 chip은 outlined → solid 토글.

## Bulk Apply 가드
- 행 다중 선택 후 `[선택 일괄 승인]` 버튼
- **활성 조건 (선택된 모든 행이 만족해야 활성)**:
  - `metadata_status === "clean"`
  - `poster_status === "poster_ok"`
  - `risk_level === "low"`
- 위배 행 1개라도 있으면 disabled + 툴팁: "위배 N건: {content_id 목록}"
- 실 호출: 기존 `/api/programming/metadata/staging/bulk-approve` 재사용 (`{content_ids, reviewer}`)

## 가드 단위테스트
`mediaX-CMS/apps/web/components/contents/__tests__/reviewQueueBulkGuard.test.ts` (또는 가드 함수만 분리해서)
- 4 케이스: 전부 만족 / 1건 risk_level=high / poster_status=needs_selection / metadata_status=missing

(현재 프로젝트에 프론트 테스트 인프라가 없다면 가드 함수를 순수 함수로 분리해 lib에 두고 만들 때 결정)

## 성능 확인
- Watcha 237건 기준 첫 페이지(50개) 응답 < 1.0s (include_dam=true 포함)
- include_dam=false 면 < 0.5s 목표
- 측정: 브라우저 네트워크 탭

## 변경 파일
- `mediaX-CMS/apps/web/app/(main)/programming/contents/review/page.tsx` — summary 6칸 + 필터 다중 + bulk apply 가드 + 행 선택
- (필요 시) `mediaX-CMS/apps/web/lib/reviewQueueGuard.ts` — 가드 순수 함수 분리

## 검증
- `cd mediaX-CMS && npm run typecheck && npm run lint`
- 시나리오:
  - 237건 로드 시간 측정
  - 필터 조합 (Missing+High Risk) 결과 검증
  - 모든 행 만족 → 일괄 승인 활성 → 실 호출 후 행 수 감소
  - 위배 1건 포함 → 버튼 disabled + 툴팁 표시

## 주의
- bulk apply는 매우 보수적으로. MVP에서는 "low risk + clean"만 허용
- 페이지네이션 적용 후 일괄 승인은 현재 페이지 선택 행에만 작동
- staging 상태가 아닌 콘텐츠가 섞이면 백엔드가 거부하므로 그 에러 메시지 그대로 표시
