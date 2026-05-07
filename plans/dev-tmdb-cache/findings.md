# TMDB Cache Build — Findings & Design

> Plan: `dev-tmdb-cache` | 작성: 2026-05-06

---

## 1. 현 구현 인벤토리

### 1-1. 호출 그래프 (기존)

```
Celery Beat 02:00 ──► sync_tmdb()
                         └─► _async_sync_tmdb(db, api_key)
                                  └─► Content (tmdb_id IS NULL, not waiting) LIMIT 50
                                       └─► _tmdb_search_and_save(content, db, api_key)
                                                ├─► GET /search/movie OR /search/tv
                                                ├─► GET /movie/{id}?append_to_response=credits
                                                ├─► ExternalMetaSource(source_type=tmdb) 저장
                                                ├─► ContentImage(poster) 저장
                                                ├─► ContentCredit + PersonMaster 저장
                                                └─► (시리즈) _tmdb_collect_seasons() 재귀
                                                         └─► GET /tv/{id}/season/{n}
                                                              └─► Content(season/episode) 계층 생성

Celery Beat 04:00 ──► check_missing_episodes()
                         └─► ContentMetadata.tmdb_id IS NOT NULL & type=series LIMIT 50
                              └─► GET /tv/{tmdb_id}  →  number_of_episodes vs DB count
                                   └─► 불일치 시 enrich_content_metadata.delay(id)
```

### 1-2. 핵심 파일 위치

| 파일 | 역할 | 주요 라인 |
|------|------|----------|
| `backend/workers/celery_app.py` | Beat 스케줄 | 31–34 (sync_tmdb), 38–41 (check_missing_episodes) |
| `backend/workers/tasks/metadata.py` | sync_tmdb / enrich / check_ep | 260–321, 436–528, 720–780 |
| `backend/api/programming/metadata/router.py` | TMDB 매핑 목록 API | 466–475 |
| `backend/api/programming/metadata/service.py` | list_tmdb_synced | 1112–1165 |
| `backend/api/programming/metadata/schemas.py` | TmdbSyncedItem, PaginatedTmdbItems | 405–424 |
| `mediaX-CMS/.../programming/tmdb/page.tsx` | TMDB 탐색 UI (mock 포함) | 전체 |

### 1-3. 환경 설정

| 변수 | 상태 |
|------|------|
| `TMDB_API_KEY` | ✅ backend/.env 설정 완료 (`8150...`) |
| `DATABASE_URL` | PostgreSQL (docker), SQLite (로컬 개발) |
| `REDIS_URL` | `redis://redis:6379/0` |

---

## 2. Beat 스케줄 (기존)

| 태스크 | 스케줄 | 설명 |
|--------|--------|------|
| `sync_tmdb` | 매일 02:00 KST | 미매핑 Content row 최대 50건 tmdb_id 보강 |
| `check_missing_episodes` | 매일 04:00 KST | TMDB vs DB 에피소드 수 불일치 → enrich 재실행 |

---

## 3. DB 컬럼 (기존 — 운영용)

### content_metadata (기존, 변경 금지)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `tmdb_id` | Integer, index | 매핑된 TMDB movie/tv ID |
| `tmdb_data` | JSON | TMDB detail API raw 응답 (운영 콘텐츠 한정) |

### external_meta_sources (기존)

| 컬럼 | 설명 |
|------|------|
| `source_type` | `tmdb` ENUM 값 |
| `external_id` | str(tmdb_id) |
| `raw_json` | detail 응답 전체 |
| `matched_at` | fetch 시각 |

### content_images (기존)

- `source='tmdb'` 레코드로 포스터 URL 저장 (`https://image.tmdb.org/t/p/w500{poster_path}`)

---

## 4. API / UI 진입점 (기존)

| 경로 | 설명 |
|------|------|
| `GET /api/programming/metadata/tmdb` | 매핑된 Content 목록 (운영 콘텐츠 기준) |
| `/programming/tmdb` (Next.js) | TMDB 매핑 현황 탐색 UI |

---

## 5. 갭 분석 (신규 구현 필요 항목)

| 갭 | 설명 | 심각도 |
|----|------|--------|
| **Discovery 부재** | 기존 `sync_tmdb`는 *이미 등록된* Content row의 tmdb_id 매핑만 수행. 신규 영화를 TMDB에서 끌어오는 기능 없음 | 🔴 핵심 |
| **캐시 DB 없음** | TMDB 메타가 `content_metadata.tmdb_data` (JSON)에 묻혀있어 재활용·검색 불가 | 🔴 핵심 |
| **레이트 리밋 미보호** | `httpx` 직접 호출, Semaphore/backoff 없음 — 동시 worker 다수 시 429 위험 | 🟡 중요 |
| **Sync log 없음** | 얼마나 가져왔는지 추적 불가 | 🟡 중요 |
| **이미지 base URL 동적 조회 없음** | `https://image.tmdb.org/t/p/w500` 하드코딩 — TMDB `/configuration` API로 동적 조회 권장 | 🟢 개선 |
| **모니터링 페이지 없음** | Daily 적재량 확인 불가 | 🔴 사용자 요청 |

---

## 6. 신규 캐시 DB 스키마 설계

### 설계 원칙

1. **운영 DB와 독립** — `content_metadata` 등 기존 테이블 일절 수정 금지
2. **PK = TMDB ID** — 중복 방지 + 조인 단순화
3. **이미지 바이너리 다운로드 Phase 1 제외** — `poster_path` / `backdrop_path` 컬럼만 저장. CDN 캐싱은 `dev-tmdb-image-cdn` plan으로 분리
4. **SQLite/PostgreSQL 호환** — `raw_json` 컬럼: PostgreSQL JSONB, SQLite JSON 폴백

### 6-1. tmdb_movie_cache

```sql
CREATE TABLE tmdb_movie_cache (
  id              BIGINT PRIMARY KEY,          -- TMDB movie_id
  title           VARCHAR(500) NOT NULL,
  original_title  VARCHAR(500),
  original_language VARCHAR(10),
  release_date    DATE,
  runtime         INTEGER,                     -- 분
  popularity      FLOAT,
  vote_average    FLOAT,
  vote_count      INTEGER,
  adult           BOOLEAN DEFAULT FALSE,
  poster_path     VARCHAR(500),               -- /xxxx.jpg (base URL은 runtime 조합)
  backdrop_path   VARCHAR(500),
  overview        TEXT,
  genre_ids       JSON,                        -- [28, 12, ...]
  raw_json        JSON,                        -- TMDB /movie/{id} 전체 응답
  first_fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_fetched_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- 인덱스
CREATE INDEX ON tmdb_movie_cache(release_date);
CREATE INDEX ON tmdb_movie_cache(popularity DESC);
CREATE INDEX ON tmdb_movie_cache(last_fetched_at);
```

### 6-2. tmdb_tv_cache

```sql
CREATE TABLE tmdb_tv_cache (
  id              BIGINT PRIMARY KEY,          -- TMDB tv_id
  name            VARCHAR(500) NOT NULL,
  original_name   VARCHAR(500),
  original_language VARCHAR(10),
  first_air_date  DATE,
  last_air_date   DATE,
  number_of_seasons  INTEGER,
  number_of_episodes INTEGER,
  status          VARCHAR(100),               -- "Ended", "Returning Series" 등
  popularity      FLOAT,
  vote_average    FLOAT,
  vote_count      INTEGER,
  poster_path     VARCHAR(500),
  backdrop_path   VARCHAR(500),
  overview        TEXT,
  genre_ids       JSON,
  raw_json        JSON,
  first_fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_fetched_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ON tmdb_tv_cache(first_air_date);
CREATE INDEX ON tmdb_tv_cache(popularity DESC);
```

### 6-3. tmdb_person_cache

```sql
CREATE TABLE tmdb_person_cache (
  id              BIGINT PRIMARY KEY,          -- TMDB person_id
  name            VARCHAR(300) NOT NULL,
  also_known_as   JSON,                        -- ["홍길동", "Hong Gildong", ...]
  birthday        DATE,
  deathday        DATE,
  profile_path    VARCHAR(500),
  popularity      FLOAT,
  raw_json        JSON,
  first_fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_fetched_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 6-4. tmdb_sync_log

```sql
CREATE TABLE tmdb_sync_log (
  id              BIGSERIAL PRIMARY KEY,
  run_id          UUID NOT NULL DEFAULT gen_random_uuid(),
  source          VARCHAR(50) NOT NULL,        -- 아래 ENUM 값
  -- 'discover_movie' | 'discover_tv' | 'changes_movie' | 'changes_tv'
  -- | 'backfill_movie_year' | 'backfill_tv_year'
  target_year     INTEGER,                     -- 백필 연도 슬라이싱 시 사용
  target_date     DATE,                        -- daily changes 날짜
  status          VARCHAR(20) NOT NULL,        -- 'running' | 'completed' | 'failed'
  started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  finished_at     TIMESTAMPTZ,
  pages_fetched   INTEGER DEFAULT 0,
  items_fetched   INTEGER DEFAULT 0,
  items_inserted  INTEGER DEFAULT 0,
  items_updated   INTEGER DEFAULT 0,
  items_unchanged INTEGER DEFAULT 0,
  errors          INTEGER DEFAULT 0,
  error_sample    JSON                         -- 최초 5개 에러 메시지
);
CREATE INDEX ON tmdb_sync_log(started_at DESC);
CREATE INDEX ON tmdb_sync_log(source, target_year);
CREATE INDEX ON tmdb_sync_log(target_date);
```

---

## 7. 호출 전략 매트릭스

### 7-1. 백필 (1회성 — 전수 수집)

```
backfill_movies(year_from=1900, year_to=2026):
  for year in range(year_from, year_to+1):
    page = 1
    while page <= total_pages (max 500):
      GET /discover/movie
        ?primary_release_date.gte={year}-01-01
        &primary_release_date.lte={year}-12-31
        &sort_by=popularity.desc
        &page={page}
        &language=ko-KR,en-US
      → 20건 / page, max 500 page = 10,000건 / 연도
      → upsert tmdb_movie_cache
      page++
    TmdbSyncLog(source='backfill_movie_year', target_year=year, ...) 기록
```

**주의**: 인기 연도(1990s~2010s)는 20건×500page = 10,000건 한계 초과 가능
→ 해당 연도는 6개월 단위 재슬라이싱 (`primary_release_date.lte={year}-06-30` + `{year}-07-01~12-31`)

### 7-2. Daily 증분

```
daily_changes(date=어제):
  GET /movie/changes?start_date={date}&end_date={date}  # 변경된 movie id 목록
    → all pages → changed_ids[]
  for id in changed_ids:
    GET /movie/{id}  → upsert tmdb_movie_cache

daily_new_releases(date=어제):
  GET /discover/movie?primary_release_date.gte={date}&primary_release_date.lte={date}
    → upsert tmdb_movie_cache (신규 개봉 포함)

동일 패턴으로 TV 버전 병행
```

---

## 8. 쿼터 분석

### TMDB 공식 정책

- **Rate limit**: 50 req/sec (API v3)
- **Daily limit**: 명시 없음 — abuse 감지 시 IP 차단
- **안전 마진**: 25 req/sec (`asyncio.Semaphore(25)`)

### 백필 호출량 추정

| 항목 | 계산 | 총량 |
|------|------|------|
| 연도 수 | 1900~2026 = 127 | - |
| 평균 page 수 / 연도 | ~100 page (연도별 상이) | - |
| discover req | 127 × 100 = 12,700 | 12,700 req |
| 소요시간 @25 req/sec | 12,700 / 25 = 508초 | **~9분** |
| TV 백필 (1950~2026) | 76 × 80 × 1 ≈ 6,080 req | **~4분** |
| **합계** | | **~13분 (1회)** |

→ 쿼터 문제 없음. Detail fetch (선택적 보강)는 별도 plan.

### Daily 증분 호출량 추정

| 항목 | 추정치 |
|------|--------|
| `/movie/changes` 페이지 | ~5 page/일 (평균 100건 변경) |
| detail fetch | ~100 req |
| `/discover/movie` 신규 | ~1~3 page |
| **TV 합산** | ~200 req/일 |
| 소요시간 @25 req/sec | < **10초** |

---

## 9. 프론트엔드 차트 전략

현재 `mediaX-CMS/apps/web` 에는 **별도 차트 라이브러리 없음**.

→ 모니터링 페이지에서는 **CSS 상대폭 바 그래프** (Tailwind `w-[N%]` 동적) 사용.
 `max(items) = 100%` 기준으로 일자별 relative bar 표시. 외부 라이브러리 추가 없이 구현.

---

## 10. ContentMetadata 연계 방식 (신규 콘텐츠 입력 보완)

1. 사용자가 새 콘텐츠 제목 입력
2. Backend: `tmdb_movie_cache` 에서 `title ILIKE '%검색어%'` 빠른 조회
3. 후보 목록 반환 → 담당자 선택
4. 선택 시: `tmdb_movie_cache.raw_json` → `ContentMetadata.tmdb_data` 복사 + `ContentImage`, `ContentCredit` 자동 생성
5. 이 flow 는 기존 `enrich_content_metadata` 태스크와 병행 (캐시 히트 시 API 호출 없이 즉시 응답)

---

## 11. 다음 단계 (이 plan의 step 들)

| Step | 이름 | 산출물 |
|------|------|--------|
| T.2 | alembic-migration-tmdb-cache | 0004_tmdb_cache.py + 4개 테이블 |
| T.3 | tmdb-client-with-rate-limiter | tmdb_client.py + pytest |
| T.4 | backfill-worker-discover | workers/tasks/tmdb_cache.py |
| T.5 | daily-incremental-worker-and-beat | daily_changes + Beat 등록 |
| T.6 | monitoring-api | /api/.../tmdb-cache/stats, /sync-log, /recent |
| T.7 | monitoring-ui-page | /programming/tmdb-sync 페이지 |
| T.8 | backfill-rehearsal | 2020~2025 시연 + 결과 검증 |
