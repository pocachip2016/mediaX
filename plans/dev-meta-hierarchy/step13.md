# Step 13: mh-fe-bulk-ui (Phase D)

> Milestone: dev-meta-hierarchy

## 읽어야 할 파일

- `docs/dev/meta-hierarchy/fe-design.md` § 3 (Bulk Upload 설계, Wireframe A/B/C)
- `apps/web/app/(main)/programming/contents/upload/page.tsx` (기존 284줄)
- `.claude/verify.sh` (mh-fe-bulk-ui 케이스 추가 위치)

## 작업

`fe-design.md § 3` 설계를 구현한다. 백엔드 변경 없음 (`POST /upload/batch` 유지).

### 13.A — 정적 자산

- `plans/dev-meta-hierarchy/step13.md` (본 파일)
- `apps/web/public/templates/movie.csv` — Movie 샘플 헤더 + 1행 예시
- `apps/web/public/templates/series.csv` — Series 샘플 헤더 + 6행 예시

### 13.B — Mode 토글 + 필드 안내 컴포넌트

- `apps/web/components/contents/upload/TemplateModeToggle.tsx` — radio 2 cards (movie | series)
- `apps/web/components/contents/upload/MovieFieldsTable.tsx` — FIELD_DESCRIPTIONS_MOVIE 상수 + 접이식 표
- `apps/web/components/contents/upload/SeriesFieldsTable.tsx` — FIELD_DESCRIPTIONS_SERIES + 그룹핑 안내 박스

### 13.C — 검증 유틸 + 미스매치 워닝 + page.tsx 통합

- `apps/web/components/contents/upload/validateAgainstMode.ts` — 헤더·row 수준 검증
- `apps/web/components/contents/upload/ModeMismatchWarning.tsx` — Wireframe C 패널
- `apps/web/app/(main)/programming/contents/upload/page.tsx` — mode state + 분기 + validation 호출

### 13.D — verify.sh + UI 회귀 확인

- `.claude/verify.sh` — `mh-fe-bulk-ui` case 추가

## Acceptance Criteria

```bash
bash .claude/verify.sh mh-fe-bulk-ui
```

- Mode 토글 동작: movie / series 선택에 따라 컬럼 안내·템플릿 다운로드 분기
- `movie.csv` / `series.csv` 정적 파일 다운로드 동작 (`/templates/movie.csv`)
- 파일 업로드 후 mode 별 validation: 헤더 누락 / 조건부 필수 누락 시 경고
- 모드 미스매치: 경고 + [그래도 업로드] 정상 동작
- 기존 드랍존 / 업로드 / 결과 패널 회귀 없음

## 금지사항

- 백엔드 라우터 분리 금지 (`/upload/batch/movie`, `/upload/batch/series` 없음)
- 모드 미스매치 강제 차단(block) 금지 — 소프트 경고 + [그래도 업로드]
- CSV preview 에서 백엔드 dedup 검증 흉내내기 금지
- 메타 자동 prefill 금지 (빈 채로 두는 것이 D3 상속의 정석)
