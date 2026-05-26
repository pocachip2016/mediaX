# 외부소스 Poster 처리 흐름 — 진단 보고서

**작성일**: 2026-05-26
**범위**: TMDB / KMDB / KOBIS (Watcha 배제)
**plan**: `plans/dev-external-poster-audit/`
**목적**: 후속 보완 step 우선순위 결정 근거 (실측 기반 P1/P2/P3 분류)

---

## 1. 요약 표

| 소스 | cache 이미지 컬럼 | sync 시 채워짐 | ContentImage 변환 | FE 표시 |
|------|------------------|---------------|-------------------|---------|
| **TMDB** | `tmdb_movie_cache.poster_path` / `tmdb_tv_cache.poster_path` | ✅ 84% / 82% | ✅ (`_tmdb_search_and_save`) | ✅ |
| **KMDB** | `kmdb_movie_cache.poster_url` + `raw_json` | ❌ **0%** (worker 버그) | ❌ (변환 worker 없음) | ❌ (FE 컬럼 미구현) |
| **KOBIS** | 없음 (모델·API 모두 부재) | — (구조적 불가) | — | — |

---

## 2. DB 실측치

### 2.1 캐시 테이블 row 수 + poster 채워짐 비율

| 테이블 | total | filled | 비율 |
|--------|------:|-------:|----:|
| `tmdb_movie_cache.poster_path` | 488,890 | 411,759 | **84.2%** |
| `tmdb_tv_cache.poster_path` | 167,725 | 137,152 | **81.8%** |
| `kmdb_movie_cache.poster_url` | **3,098** | **0** | **0.0% ⚠️** |
| `kobis_movie_cache` (poster 컬럼 없음) | 8,503 | — | — |

KMDB 최근 1주 신규 row: **2,434건 중 0건 채워짐** → 신규 sync 도 계속 NULL 생성 중.

### 2.2 KMDB `raw_json` 이미지 키 보유율 (3,098건 기준)

| 키 | 보유 row | 비고 |
|----|---------:|------|
| `posters` (string) | 3,098 (100%) | API 응답에 항상 존재 |
| `stlls` (string) | 3,098 (100%) | API 응답에 항상 존재 |
| `plots` | 3,098 (100%) | — |

- `posters` 가 **non-empty** row: **2,606 / 3,098 (84.1%)** — 빈 문자열 492 제외.
- `stlls` 가 **non-empty** row: **1,591 / 3,098 (51.4%)** — 빈 stillcut 1,507 제외.

### 2.3 ContentImage 분포 (현재 운영 상태)

```
image_type | source         | count
-----------+----------------+-------
 poster    | tmdb_recommend |    60   ← dev-poster-recommend Phase 2 결과
 poster    | cp             |     1
```

- **kmdb·tmdb·watcha source 의 ContentImage 0건**. 즉, cache 의 poster_url 이 ContentImage 로 변환되는 흐름이 사실상 없음.
- 60건의 `tmdb_recommend` 만 운영자가 수동 추천 흐름에서 생성됨.

### 2.4 ExternalMetaSource source_type 분포

| source_type | total |
|------------|------:|
| bulk_upload | 6,591 |
| kobis | 872 |
| tmdb | 122 |
| manual | 3 |

`kmdb` source_type 의 ExternalMetaSource **0건** — KMDB cache 가 별도로 관리될 뿐 콘텐츠 메타에 연결되지 않음.

### 2.5 KOBIS 매칭 콘텐츠의 poster 누락 측정

```
kobis_matched_count          | 872   ← KOBIS source 와 연결된 콘텐츠 수
kobis_matched_without_poster | 6     ← 그 중 poster 가 한 장도 없는 콘텐츠
```

→ **866 / 872 (99.3%) 는 이미 다른 경로(TMDB)로 poster 보유**. KOBIS-only fallback 의 실제 영향 콘텐츠는 **6건**.

---

## 3. KMDB raw_json 이미지 키 상세

### 3.1 실제 데이터 구조 (raw_json 샘플)

```json
"posters": "http://file.koreafilm.or.kr/.../tn_DPF030009.jpg|http://file.koreafilm.or.kr/.../tn_DPF009370.JPG"
"stlls":   "http://file.koreafilm.or.kr/.../stll1.jpg|http://file.koreafilm.or.kr/.../stll2.jpg|..."
```

**`posters`·`stlls` 모두 flat 문자열**. `|` 구분 multi-URL. nested object 아님.

### 3.2 한 영화당 평균/최대 URL 개수

| 필드 | 평균 (non-empty 행 기준) | 최대 |
|------|------------------------:|----:|
| `posters` | **2.32개** | 25개 |
| `stlls` | **7.80개** | 10개 |

**잠재 자산 규모 (현재 모두 미활용)**:
- poster URLs: 2,606 × 2.32 ≈ **약 6,050개**
- stillcut URLs: 1,591 × 7.80 ≈ **약 12,410개**

### 3.3 jsonb_typeof 확인

```
posters_is_string | 3098    ← 100% string
posters_is_object | 0       ← nested object 케이스 없음
```

→ worker 가 dict 분기 코드를 가지고 있지만, 실제 데이터로는 그 분기에 한 번도 진입하지 않는다.

---

## 4. 흐름 매핑

```
TMDB:
  API → tmdb_movie_cache.poster_path
        → _tmdb_search_and_save (workers/tasks/metadata.py:728-752)
        → ContentImage(image_type='poster', source='tmdb')
        → FE: /programming/sources/tmdb 에 poster 표시 ✅

KMDB:
  API → kmdb_movie_cache.raw_json.posters (string, "url|url|...")
        →❌ _upsert_kmdb_movie (workers/tasks/kmdb_cache.py:57-62)
           [BUG] posters 를 dict 로 가정 → 항상 NULL 저장
        →❌ ContentImage 변환 worker 없음
        →❌ FE: KMDB cache dashboard 에 poster 컬럼 미구현

KOBIS:
  API → kobis_movie_cache (poster 필드 없음, 구조적)
        → (KOBIS-only fallback 미구현, 6건만 영향)
        → ContentImage 미생성
```

---

## 5. 누락 지점 상세 (코드 위치 + 영향 규모)

| # | 누락 지점 | 위치 | 영향 규모 |
|---|-----------|------|-----------|
| 1 | KMDB worker 의 posters 파싱 버그 | `backend/workers/tasks/kmdb_cache.py:57-62` | **3,098 / 3,098 row (100%)** poster_url NULL |
| 2 | KMDB stlls(스틸컷) 추출 부재 | 위와 동일 worker | **1,591 row (51.4%)** 의 ~12,410개 URL 미활용 |
| 3 | KMDB cache → ContentImage 변환 worker 부재 | (해당 worker 없음) | 콘텐츠 검수·표시 흐름에서 KMDB poster 활용 불가 |
| 4 | KMDB FE cache 페이지 poster 컬럼 부재 | `mediaX-CMS/apps/web/app/(main)/programming/sources/kmdb/page.tsx:209-216` | 운영자가 캐시 검색 결과 시 poster 확인 불가 |
| 5 | 콘텐츠 상세 ExternalSourceOut 에 poster 필드 없음 | `mediaX-CMS/apps/web/lib/api.ts:134-139` | 콘텐츠 상세에서 외부소스별 poster 비교 UI 불가 |
| 6 | KOBIS poster fallback 미구현 | (해당 worker 없음) | **6 contents** (전체 KOBIS 매칭 872 중 99.3%는 이미 TMDB로 보강됨) |

---

## 6. 우선순위 제안 (P1 / P2 / P3)

평가 축: **영향 콘텐츠/row 건수** + **운영 임팩트** (검수/노출 빈도).

### P1 (즉시 필요)

- **kmdb-poster-extract-fix** — KMDB worker 의 `posters` 파싱을 flat 문자열 기반으로 수정. 3,098건 (100%) 영향. 데이터는 raw_json 에 이미 존재하므로 buffer 재추출만으로 backfill 가능 (외부 API 호출 불필요).
- **kmdb-content-image-sync** — fix 이후 다중 poster URL 을 `ContentImage(source='kmdb')` 다건 등록. 약 6,050개 poster URL 이 dev-poster-recommend 후보로 노출됨.

### P2 (가치 있음, 후행)

- **kmdb-poster-fe** — KMDB cache dashboard 검색 결과 테이블에 poster 썸네일·컬럼 노출. P1 완료 후 의미 있음 (현재 데이터 없으므로 단독 진행 무의미).
- **content-detail-source-compare** — 콘텐츠 상세에서 외부소스별 poster 카드 비교 UI. dev-poster-recommend Phase 2 와 자연스럽게 연동.

### P3 (선택적, 임팩트 제한적)

- **kmdb-stillcut-extract** — stillcut 12,410개 URL 추출·저장. ContentImage(image_type='stillcut') 분기 필요. 검수/홍보 자산으로 유용하나 우선순위 낮음.
- **kobis-poster-fallback** — KOBIS 매칭 → TMDB 자동 재검색. **실제 영향 콘텐츠 6건뿐**. 비용/효익이 매우 낮음. **드롭 또는 매우 후행 권장**.

---

## 7. 후속 step 제안 (slug + AC + 의존성)

| slug | 영역 | P | AC | 의존 |
|------|------|---|----|------|
| `kmdb-poster-extract-fix` | BE worker | **P1** | `_upsert_kmdb_movie` 가 `raw_json['posters']` 문자열을 `\|` 로 split → 첫 단일 URL 을 `poster_url` 컬럼 저장 + 전체 list 를 raw_json 그대로 유지 (이미 보존됨). backfill: `kmdb_movie_cache` 전체 re-upsert (raw_json 그대로 재처리). | — |
| `kmdb-content-image-sync` | BE worker | **P1** | `kmdb_movie_cache` 의 다중 poster URL → `ContentImage(image_type='poster', source='kmdb', is_primary=false)` 다건 등록 worker + Beat. 콘텐츠-KMDB 연결(`docid` 매칭) 필요. | `kmdb-poster-extract-fix` |
| `kmdb-poster-fe` | FE | P2 | KMDB cache dashboard 검색 결과에 poster 썸네일 컬럼 추가. KMDB cache 응답 schema 에 `poster_url`/`poster_urls` 가 채워진 상태 전제. | `kmdb-poster-extract-fix` |
| `content-detail-source-compare` | FE | P2 | 콘텐츠 상세에서 외부소스별 poster 카드 비교 UI. `ExternalSourceOut` schema 확장 + `ContentImage` 그룹화. | `kmdb-content-image-sync` |
| `kmdb-stillcut-extract` | BE worker | P3 | `raw_json['stlls']` 도 함께 파싱 → `ContentImage(image_type='stillcut', source='kmdb')` 등록. | `kmdb-poster-extract-fix` |
| `kobis-poster-fallback` | BE worker | P3 (드롭 권장) | 6 contents 만 영향. 비용/효익 낮음. 진행 시 `title_ko/title_en + open_year` → TMDB `/search/movie` → `ContentImage` 등록. | `_tmdb_search_and_save` 재사용 |

---

## 부록 A. 실측 쿼리 모음

본 보고서의 모든 수치는 다음 쿼리로 재현 가능 (`docker exec mediax-postgres-1 psql -U media_ax -d media_ax -c "..."`).

```sql
-- 2.1 캐시 row 수 + 채워짐 비율
SELECT 'tmdb_movie' tbl, COUNT(*) total, COUNT(poster_path) filled FROM tmdb_movie_cache
UNION ALL SELECT 'tmdb_tv', COUNT(*), COUNT(poster_path) FROM tmdb_tv_cache
UNION ALL SELECT 'kmdb_movie', COUNT(*), COUNT(poster_url) FROM kmdb_movie_cache
UNION ALL SELECT 'kobis_movie', COUNT(*), 0 FROM kobis_movie_cache;

-- 2.2 KMDB raw_json 키 보유율
SELECT
  COUNT(*) FILTER (WHERE raw_json::jsonb ? 'posters') has_posters,
  COUNT(*) FILTER (WHERE raw_json::jsonb ? 'stlls')   has_stlls
FROM kmdb_movie_cache;

-- 2.3 ContentImage 분포
SELECT image_type, source, COUNT(*) FROM content_images GROUP BY image_type, source ORDER BY 3 DESC;

-- 2.4 ExternalMetaSource 분포
SELECT source_type, COUNT(*) FROM external_meta_sources GROUP BY source_type ORDER BY 2 DESC;

-- 2.5 KOBIS 매칭 콘텐츠 poster 누락
SELECT
  (SELECT COUNT(*) FROM external_meta_sources WHERE source_type='kobis') kobis_matched,
  (SELECT COUNT(DISTINCT ems.content_id)
   FROM external_meta_sources ems
   LEFT JOIN content_images ci ON ci.content_id=ems.content_id AND ci.image_type='poster'
   WHERE ems.source_type='kobis' AND ci.id IS NULL) kobis_no_poster;

-- 3.1 raw_json posters 형태 확인
SELECT
  SUM(CASE WHEN jsonb_typeof(raw_json::jsonb -> 'posters')='string' THEN 1 ELSE 0 END) posters_is_string,
  SUM(CASE WHEN jsonb_typeof(raw_json::jsonb -> 'posters')='object' THEN 1 ELSE 0 END) posters_is_object,
  SUM(CASE WHEN (raw_json::jsonb ->> 'posters') LIKE '%|%' THEN 1 ELSE 0 END) posters_has_pipe,
  SUM(CASE WHEN (raw_json::jsonb ->> 'posters')='' THEN 1 ELSE 0 END) posters_empty
FROM kmdb_movie_cache;

-- 3.2 평균/최대 URL 개수
SELECT
  AVG(CASE WHEN (raw_json::jsonb->>'posters')<>'' THEN array_length(string_to_array(raw_json::jsonb->>'posters','|'),1) END)::numeric(5,2) avg_posters,
  AVG(CASE WHEN (raw_json::jsonb->>'stlls')<>'' THEN array_length(string_to_array(raw_json::jsonb->>'stlls','|'),1) END)::numeric(5,2) avg_stlls,
  MAX(CASE WHEN (raw_json::jsonb->>'posters')<>'' THEN array_length(string_to_array(raw_json::jsonb->>'posters','|'),1) END) max_posters,
  MAX(CASE WHEN (raw_json::jsonb->>'stlls')<>'' THEN array_length(string_to_array(raw_json::jsonb->>'stlls','|'),1) END) max_stlls
FROM kmdb_movie_cache;
```

## 부록 B. 핵심 코드 위치

- worker 버그 위치: `backend/workers/tasks/kmdb_cache.py:57-62`
  ```python
  posters = raw.get("posters") or {}
  poster_list = posters.get("poster") if isinstance(posters, dict) else []  # ← 실제 raw['posters'] 는 string
  ```
- TMDB → ContentImage 참고 흐름: `backend/workers/tasks/metadata.py:728-752` (`_tmdb_search_and_save`)
- ContentImage 모델: `backend/api/programming/metadata/models/image.py` (ImageType enum: poster/thumbnail/stillcut/banner/logo)
- KMDB FE cache 페이지: `mediaX-CMS/apps/web/app/(main)/programming/sources/kmdb/page.tsx:209-216` (poster 컬럼 자리 없음)
