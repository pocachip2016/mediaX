# Step 1: poster-audit-doc

**유형**: doc-only (진단)
**상태**: completed (2026-05-26)
**모델**: Opus 4.7

## 산출물

- `docs/1_programming/external-poster-audit.md` — 7개 섹션 완성
- `plans/dev-external-poster-audit/index.json` — 후속 step 후보 6개 우선순위 분류

## 핵심 발견

1. **KMDB worker 파싱 버그 (P1)** — `backend/workers/tasks/kmdb_cache.py:57-62` 의 `posters` 파싱이 nested dict 를 가정하지만 실제 raw_json 의 `posters` 는 flat `|` 구분 문자열. 결과적으로 **3,098 / 3,098 row (100%) 의 poster_url 이 NULL**. 최근 1주 신규 row 2,434건 모두 NULL.
2. **자산은 raw_json 에 이미 존재** — 평균 영화당 poster 2.32개 / stillcut 7.80개. 총 약 **6,050 poster URL + 12,410 stillcut URL** 이 미활용 상태로 보존됨. 외부 API 재호출 없이 backfill 가능.
3. **KOBIS-only fallback 의 실제 영향 6건** — KOBIS 매칭 콘텐츠 872건 중 866건 (99.3%) 은 이미 TMDB 로 poster 보유. KOBIS→TMDB fallback worker 의 비용/효익 매우 낮음 → **P3 드롭 권장**.
4. **ContentImage 변환 부재** — kmdb·watcha source 의 ContentImage 0건. 현재 `tmdb_recommend` 60건 + `cp` 1건만 존재.

## 후속 step 우선순위 (요약)

- **P1**: `kmdb-poster-extract-fix` → `kmdb-content-image-sync`
- **P2**: `kmdb-poster-fe`, `content-detail-source-compare`
- **P3**: `kmdb-stillcut-extract`, `kobis-poster-fallback` (드롭 검토)

## Verify

`/verify --skip "Step 1: 진단 문서 작성"`
