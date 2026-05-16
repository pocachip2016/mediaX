# Step 5: Dam Link Display 연결

## 목적
Dam을 mediaX 이미지 저장소가 아닌 내부 에셋 SSOT로 노출. 자동 등록은 하지 않음.

## 사용 API (신규 없음)
`GET /api/meta-core/contents/{content_id}/dam-assets` — `backend/api/meta_core/public_api/router.py:110` 에 이미 구현됨.
응답: `DamAssetsOut { content_id, assets: DamAssetItem[], dam_available }`. DAM 미가용 시 `dam_available=false` + 빈 배열.

## 프론트 API 추가
`mediaX-CMS/apps/web/lib/api.ts`:
```ts
export type DamAssetItem = {
  asset_id: number
  filename: string
  asset_type: string
  thumbnail_url: string
  confidence?: number
  match_method?: string
}
export type DamAssetsOut = {
  content_id: number
  assets: DamAssetItem[]
  dam_available: boolean
}

// 기존 metadataApi와 별도 — base는 동일 BASE 변수 재사용
export const damApi = {
  getAssetsByContent: (id: number) => fetcher<DamAssetsOut>(`/api/meta-core/contents/${id}/dam-assets`)
}
```

## 상세 페이지 통합
`[id]/page.tsx`:
- assets 탭(또는 우측 사이드 영역)에 "Dam Assets" 카드 추가
- `dam_available=false` → 회색 "DAM 미가용" 메시지 + 재시도 버튼
- assets 0건 → "연결된 Dam 에셋 없음"
- assets 있음 → 썸네일 그리드 (thumbnail_url 사용) + asset_id + filename + asset_type

## Review Queue row 보강
Step 1에서 `dam_match_count`를 이미 응답에 포함했으므로 Step 2 테이블의 "Dam" 컬럼은 그대로 사용. 본 단계에서 별 작업 없음 (확인만).

## "Link to Dam" 자리 표시
Step 4의 `VisualAssetCandidatePanel` 카드에 disabled `[Link to Dam]` 버튼 자리만 추가 (`title="Phase later"` 툴팁). 실제 API 호출 없음.

## 변경 파일
- `mediaX-CMS/apps/web/lib/api.ts` — damApi 추가
- `mediaX-CMS/apps/web/app/(main)/programming/contents/[id]/page.tsx` — Dam 카드 통합
- `mediaX-CMS/apps/web/components/contents/VisualAssetCandidatePanel.tsx` — Link to Dam 버튼 자리

## 검증
- 3 시나리오 수동 확인:
  - **DAM 켜져있고 매칭 있음**: 썸네일 그리드 + `dam_match_count` badge가 Review Queue에 보임
  - **DAM 켜져있고 매칭 0**: "연결된 Dam 에셋 없음"
  - **DAM 꺼져있음**: "DAM 미가용" + 재시도 버튼
- `cd mediaX-CMS && npm run typecheck && npm run lint`

## 주의
- 신규 백엔드 만들지 않음 — Step 6/Phase Later에서 link API(`POST /visual-assets/link-dam`) 검토
- visual_asset_link 모델 신규 생성도 본 단계 범위 외
- thumbnail_url은 백엔드가 `/api/meta-core/dam-thumb/{asset_id}`로 프록시
