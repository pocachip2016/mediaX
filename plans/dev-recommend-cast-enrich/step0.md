# dev-recommend-cast-enrich — 추천 cast 보강 + bulk 중복 해결

> **목적**: 추천 상세 화면(`/programming/contents/[id]/recommend`)에서 cast(주연) 행이 표시되도록 외부 소스 데이터 보강. 동시에 bulk_upload 중복 생성 문제 해결 + TMDB 캐시 시스템 활용.
> **검수 대상**: content 4192 ("스파이더맨: 뉴 유니버스") — 중복 3건 존재, 외부 소스 3개 모두 cast 없음.

---

## 사전 컨텍스트 (모든 step 공통)

### 현재 상태 (실측)
- content 4192 외부 소스 3개: `bulk_upload`(Watcha 추출), `kobis`, `tmdb` — 모두 cast 필드 없음
- 4192 credits: 감독 3명만 (송강호·이순신·조진웅 등 출연 0명)
- 같은 title+year+cp 중복: 4192=`[3718, 3955, 4192]`, 전체 344 그룹
- `tmdb_movie_cache.raw_json`은 detail+credits 포함 (changes API로 sync된 항목)
- KOBIS는 별도 캐시 테이블 없음

### 주요 파일
- 백엔드 서비스: `backend/api/programming/metadata/service.py`
  - `process_batch_rows` (line 450~) — bulk 업로드 로직
  - `get_content_recommendations` (line 2509~) — 추천 API
  - `_extract_field_from_raw` (line 2475~) — raw_json 필드 추출
  - `_STANDARD_RECOMMENDATION_FIELDS` (line 2467~) — 표준 필드 목록
- 라우터: `backend/api/programming/metadata/router.py` (line 323 GET /recommendations)
- KOBIS 클라이언트: `backend/api/meta_core/clients/kobis_client.py`
- TMDB 클라이언트: `backend/api/programming/metadata/tmdb_client.py` (`detail_movie`, `detail_tv` 이미 `append_to_response=credits`)
- TMDB 캐시 모델: `backend/api/programming/metadata/models/tmdb_cache.py`
- TMDB 캐시 worker: `backend/workers/tasks/tmdb_cache.py` (`_upsert_movie`, `_upsert_tv` 재사용)

### Score Conventions
- 캐시 데이터는 `raw_json` 키 그대로 보존 (TMDB credits.cast 구조 등 변형 X)
- ExternalMetaSource.raw_json 병합 시 **빈 값만 채움** (기존 값 덮어쓰지 않음)
- cast 추출은 상위 5명 (TMDB는 order 정렬, KOBIS는 cast 컬럼 순서)

---

## Step 1 — bulk-dedup
**Scope**: process_batch_rows에 dedup 추가 + 기존 중복 정리 스크립트.

**파일**:
- `backend/api/programming/metadata/service.py` (`process_batch_rows` 수정)
- `backend/scripts/dedup_contents.py` (신규)

**작업**:
1. `process_batch_rows`에서 각 row 처리 전 `(title, production_year, cp_name)` 매칭하는 기존 Content 조회
2. 매칭되면:
   - 기존 ExternalMetaSource(bulk_upload) 있으면 raw_json에 빈 값만 채움 (있는 값 덮어쓰기 X)
   - 없으면 새 ExternalMetaSource(bulk_upload)만 추가
   - `process_content_metadata.delay()` 호출 X (재처리 방지)
   - `skipped_duplicates` 카운터 증가
3. 매칭 없으면 기존 신규 생성 로직 그대로
4. 반환 dict에 `skipped_duplicates` 추가
5. `scripts/dedup_contents.py`:
   - `(title, year, cp_name)` 그룹별 canonical 선정 (가장 빠른 id)
   - 자식 row(ExternalMetaSource·ContentMetadata·ContentCredit·ContentImage·ContentGenre·ContentTag) content_id를 canonical로 이전 (충돌 시 skip)
   - 중복 Content 삭제
   - `--dry-run` 기본, `--apply`로 실행

**verify** (`recommend-cast-enrich-step1`):
- `process_batch_rows` 함수에 `skipped_duplicates` 포함
- `scripts/dedup_contents.py` 파일 존재 + import 가능
- `python scripts/dedup_contents.py --dry-run` 실행 → 344 그룹 영향 출력
- typecheck (pytest 회귀 통과)

**금지**:
- ❌ **기존 중복 콘텐츠 자동 삭제 금지** — 반드시 `--dry-run` 기본, `--apply` 명시 시에만 실행
- ❌ **canonical 외 콘텐츠의 외부 소스 무시 금지** — 자식 row 이전 (FK 정합성)

---

## Step 2 — kobis-movie-info
**Scope**: KobisClient에 `movie_info(movie_cd)` 메서드 추가.

**파일**:
- `backend/api/meta_core/clients/kobis_client.py`

**작업**:
```python
def movie_info(self, movie_cd: str) -> dict:
    """searchMovieInfo — 영화 상세 (actors/directors/companys/showTm/audits)."""
    data = self._get("/movie/searchMovieInfo.json", {"movieCd": movie_cd})
    return data.get("movieInfoResult", {}).get("movieInfo", {})
```

**verify** (`recommend-cast-enrich-step2`):
- `KobisClient.movie_info` import 가능
- `movie_info` 메서드 시그니처 (movie_cd: str) → dict
- (선택) 실제 호출 검증은 step 4에서

**금지**:
- ❌ `_get` 내부 rate limit(1req/sec) 우회 금지

---

## Step 3 — enrich-credits
**Scope**: enrich_external_credits 통합 함수 + 헬퍼 + endpoint + cast 5명 슬라이스.

**파일**:
- `backend/api/programming/metadata/service.py` (신규 함수 + `_extract_field_from_raw` 수정)
- `backend/api/programming/metadata/router.py` (신규 endpoint)

**작업**:

### 3.1 `enrich_external_credits(content_id, db)` 함수
- 콘텐츠 외부 소스 순회
- TMDB: `_enrich_tmdb_source(src, content, db, api_key)` 호출
- KOBIS: `_enrich_kobis_source(src, db, api_key)` 호출
- 반환: `{"tmdb": "ok"/"skip"/"no_key"/"no_id"/"error", "kobis": ...}`

### 3.2 `_enrich_tmdb_source` 헬퍼
- `tmdb_movie_cache`/`tmdb_tv_cache` 캐시 조회 (content_type에 따라)
- 캐시에 credits 있으면 그대로 사용
- 캐시 미스 또는 credits 없으면 `TmdbClient.detail_movie/detail_tv` 호출 + `_upsert_movie/tv` 재사용
- ExternalMetaSource.raw_json에 `cast`, `crew`, `genres`, `runtime` 병합

### 3.3 `_enrich_kobis_source` 헬퍼
- `KobisClient.movie_info(external_id)` 호출
- ExternalMetaSource.raw_json에 `actors`, `directors`, `companys`, `runtime`(showTm) 병합

### 3.4 `_extract_field_from_raw` cast 케이스
```python
if field == "cast":
    raw_cast = raw.get("cast") or raw.get("actors")
    if isinstance(raw_cast, list):
        raw_cast = raw_cast[:5]  # 상위 5명
    return _names_from_list(raw_cast)
```

### 3.5 Router endpoint
```python
@router.post("/contents/{content_id}/enrich-credits")
def trigger_enrich_credits(content_id: int, db: Session = Depends(get_db)):
    return service.enrich_external_credits(content_id, db)
```

**verify** (`recommend-cast-enrich-step3`):
- 신규 함수 import 가능
- `enrich_external_credits` 시그니처 정상 (content_id: int, db: Session) → dict
- `_extract_field_from_raw` cast 5명 슬라이스 동작 (unit test)
- POST endpoint 등록 확인
- pytest 회귀

**금지**:
- ❌ **ExternalMetaSource.raw_json 통째로 덮어쓰기 금지** — 기존 키 보존 + 신규 키만 추가 (dict 머지)
- ❌ **TMDB 캐시 _upsert_movie 우회 금지** — 직접 INSERT 말고 재사용
- ❌ **API 키 없을 때 raise 금지** — `"no_key"` 반환

---

## Step 4 — verify-content-4192
**Scope**: 4192에 enrich-credits 호출 → 추천 API에 cast 표시 → 브라우저 확인.

**파일**: 변경 없음 (검증만)

**작업**:
1. `curl -X POST http://localhost:8000/api/programming/metadata/contents/4192/enrich-credits` → `{"tmdb":"ok","kobis":"ok"}` 응답 확인
2. `curl /contents/4192/recommendations | jq '.auto_fill[] | select(.field=="cast")'` → cast 추천 존재 확인
3. 브라우저 http://localhost:3000/programming/contents/4192/recommend 에서 주연 행에 TMDB(5명)·KOBIS 출연진 표시 확인
4. 기존 필드(genres/director/runtime/country/production_year/synopsis) 회귀 없음 확인

**verify** (`recommend-cast-enrich-step4`):
- enrich-credits 응답 ok
- recommendations API auto_fill/conflicts에 cast 필드 포함
- 기존 6개 필드 회귀 없음
- typecheck + 브라우저 표시 (수동)

---

## Step 5 — wrap
**Scope**: 문서 갱신.

**파일**:
- `plans/dev-recommend-cast-enrich/index.json` — 모든 step `completed` + summary + completed_at
- `TODO.md` — Now에서 Done으로 이동
- `mediaX/CLAUDE.md` (구현 현황 표) — enrich-credits 라인 추가 (선택)
- `backend/api/programming/metadata/CLAUDE.md` — enrich-credits 엔드포인트 + dedup 정책 추가

**verify**: `/verify --skip "doc only"`

---

## 후속 (이번 plan 범위 외)
- `KobisMovieCache` 테이블 신설 (TMDB 캐시 패턴)
- `KmdbMovieCache` 테이블 신설 (일별 호출 제한 보호)
- TMDB Beat sync에 미매핑 콘텐츠 자동 enrich-credits 추가
- ContentCredit 자동 적재 (현재는 추천 표시만)
- `POST /bulk-enrich-credits` 일괄 처리 endpoint
- KOBIS rate-limit quota 추적 (WebSearchQuotaLog 패턴)

---

## 주의사항 (금지 + 이유)
- ❌ **TMDB/KOBIS 호출 캐시 우회 금지** — 캐시 우선, 미스 시에만 API 호출. 쿼터 보호.
- ❌ **ExternalMetaSource.raw_json 통째로 교체 금지** — 기존 키 보존하면서 신규 키 추가만. bulk_upload 데이터 손실 방지.
- ❌ **bulk dedup에서 자동 삭제 금지** — 스크립트는 `--dry-run` 기본. 사용자 확인 후 `--apply`.
- ❌ **cast 5명 슬라이스 위치를 `_names_from_list` 안에 두지 마라** — 다른 필드(director)는 전체 표시. cast 케이스에만 슬라이스.
- ❌ **`enrich_external_credits`를 자동 trigger 금지** — endpoint 호출 시에만. Beat 통합은 후속 task.
