# Step 0: 기준점 정리 + plan 파일 생성

## 목적
변경 전 기준점 고정. 계획 SSOT 확보.

## MVP 범위 (확정)
| 구분 | 항목 |
|---|---|
| 포함 | Review Queue list / Metadata diff summary / Poster status / Dam link display |
| 제외 | 영상 프레임 추출 / Web image rights workflow / 자동 Dam 등록 / Mail · Manual draft |

## 사용자 결정 사항
1. **Dam 조회**: `GET /ai-review-queue?include_dam=true` 옵트인. 기본 false (DAM 미가용 latency 보호). Review Queue 페이지만 true.
2. **메뉴 위치**: `config/docs.ts`의 Programming › Contents 섹션 내 — `/new`, `/upload`, `/external`와 같은 레벨에 "AI Review Queue" 추가.
3. **미커밋 page.tsx 변경**: Step 3 (RecommendationPanel 분리)에 흡수해서 한 커밋으로 처리.

## 작업
- [x] `plans/dev-ai-review-queue/index.json` 생성
- [x] `plans/dev-ai-review-queue/step0.md ~ step6.md` 생성
- [ ] `plans/dev-flexible-meta-pipeline/step5.md.bak` 삭제
- [ ] `plans/dev-flexible-meta-pipeline/step5a.md` git add (이미 완료된 step 문서)
- [ ] 미커밋 `[id]/page.tsx`는 그대로 둔다 (Step 3에서 함께 커밋)

## 산출물
- 본 step 파일들
- 정리된 작업 트리

## 검증
문서·정리 단계이므로 `/verify --skip "planning only"`.
