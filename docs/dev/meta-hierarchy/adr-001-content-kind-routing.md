# ADR-001: 시리즈/시즌/에피소드 vs 영화 meta 구조 정리

**Status**: Accepted
**Date**: 2026-05-19
**Phase**: dev-meta-hierarchy
**Scope**: backend(meta_core·programming/metadata·workers) + frontend(mediaX-CMS)

---

## Context

`Content` 단일 테이블이 `content_type ∈ {movie, series, season, episode}` 와
`parent_id` 자기참조 + `season_number`/`episode_number` 로 계층을 표현한다.
`ContentMetadata` 는 Content 와 1:1 — 즉 series/season/episode 각각 독립 메타 행을 가진다.

content_type → 외부소스/엔드포인트 라우팅 규칙이 여러 파일에 **중복·불일치**하고,
계층 간 메타 **상속 로직이 없으며**, insert/update/delete/bulk 경로가
계층을 일관되게 다루지 않는다.

---

## 감사 결과 — 라우팅 불일치 (A~F)

| # | 위치 | 문제 |
|---|------|------|
| A | `meta_core/enrich.py:151` `_fetch_tmdb` | `is_series = content_type == series` — season/episode 가 `/search/movie` 로 잘못 라우팅 |
| B | `programming/metadata/poster_recommend.py:77` | `is_tv = content_type in (series,)` — 동일 패턴, season/episode 누락 |
| C | `workers/tasks/metadata.py:456, 623` | 동일 `is_series` 리터럴 중복, 정의 불일치(둘 다 series-only) |
| D | `meta_core/discovery/kobis_source.py:54,73` · `kmdb_source.py` | `content_type="movie"` 하드코딩 — KOBIS/KMDB 는 영화 전용 DB(구조적 제약) |
| E | `meta_core/gap.py:_SOURCE_MAP` | content_type 무관 추천 — 시리즈에 movie 전용 KMDB/KOBIS 추천 → 낭비/오매칭 |
| F | 전반 | series→season→episode 메타 상속 부재 — 에피소드 enrich 가 단독 타이틀 외부 조회 → 실패 |

## 감사 결과 — Write 경로 무결성 (R1~R6)

| # | 경로 | 위험 |
|---|------|------|
| R1 | `service.create_content` / `process_batch_rows:538` / `discovery/promote.py:95,107` | content_type 기본 `movie`, parent_id 미검증·미링크 → 비-worker insert 는 계층 생성 불가 |
| R2 | `process_batch_rows:498` dedup 키 `(title, year, cp_name)` | content_type 미포함 → 동명 영화/시리즈 충돌 병합 |
| R3 | `service.bulk_delete:1888` soft delete | 자손 미전파 → 시리즈 삭제 시 시즌/에피소드 `is_deleted=False` 잔존, 목록/계층 불일치 |
| R4 | `scripts/dedup_contents.py` `reassign_children` | `Content.parent_id` 자기참조 재할당 누락 → 중복 시리즈 제거 시 에피소드 고아 |
| R5 | `service.update_content` content_type 변경 | 자식 존재 시 series→movie 변경 → 고아화, 전파 없음 |
| R6 | 상속 시점 미정의 | insert 시 부모값 복사 시 stale, 미복사 시 누락으로 오인 |

`workers/tasks/metadata.py:803~864` (TMDB TV → season/episode 생성)이
**계층을 만드는 유일 경로**이며, `:958` 가 `series` 만 필터하므로
series 가 선존재해야만 동작한다.

---

## Decision

### D1. content_kind SSOT 헬퍼

`backend/api/programming/metadata/content_kind.py` 단일 모듈로 통일.

```python
TV_TYPES = {ContentType.series, ContentType.season, ContentType.episode}

def is_tv_type(content_or_type) -> bool: ...
def tmdb_search_kind(content) -> Literal["tv", "movie"]:  # tv-type → "tv"
def external_lookup_target(content, db) -> Content:  # season/episode → 최상위 series 조상, 없으면 self
```

A~C 의 모든 `content_type == series` 리터럴은 이 헬퍼로 대체한다.

### D2. 외부 소스 매트릭스

| content_type | TMDB | KMDB | KOBIS |
|---|---|---|---|
| movie | `/search/movie` | ✅ | ✅ |
| series | `/search/tv` | ✗ (skip) | ✗ (skip) |
| season/episode | `/search/tv` (조상 series 기준) | ✗ | ✗ |

`gap._SOURCE_MAP` 는 tv-type 일 때 KMDB/KOBIS 를 추천 목록에서 제외한다(E).

### D3. 상속 = read-time 해석 (R6)

insert/update 시 부모값을 **복사하지 않는다**. `inheritance.resolve_inherited_metadata(content, db)`
가 조회 시점에 episode→season→series 순으로 빈 필드를 채워 반환한다(순수 함수, DB 쓰기 없음).
`gap.analyze_gap` 도 이 resolver 를 사용해 상속 가능 필드를 누락으로 보고하지 않는다(F).
근거: 부모 메타 변경 시 자식 자동 반영, stale 복사본 부재.

### D4. parent_id = 계층 SSOT (R1)

`season_number`/`episode_number` 는 표시·정렬용 보조. 계층 진실은 `parent_id`.
create/bulk/promote 는 parent_id 정합(움직임: episode→season→series)을 검증한다.

### D5. content_type-aware dedup (R2, R4)

- `process_batch_rows` dedup 키에 `content_type` 추가.
- `dedup_contents.py` 는 중복 제거 시 자식의 `Content.parent_id` 를 canonical 로 재지정.

### D6. soft-delete 자손 cascade (R3)

`bulk_delete` 가 series 삭제 시 하위 season/episode 까지 `is_deleted=True` 전파.
역으로, 목록/계층 쿼리는 삭제된 조상의 자식을 노출하지 않는다.

### D7. content_type 변경 가드 (R5)

`update_content` 에서 자식이 존재하는 Content 의 content_type 변경은 거부(에러 반환).

### D8. movie vs series 파이프라인 차이

- **movie**: `waiting → processing → staging → review/approved` 평면 단건.
- **series**: series 가 staging 으로 가려면 하위 season/episode 처리 상태를 집계.
  series 자체 메타(시리즈 단위 시놉시스/포스터)와 에피소드 메타는 분리 검수.
  (구체 규칙은 step 진행 시 staging 집계 함수에서 확정.)

### D9. bulk insert movie/series 경로 분리

- **movie 경로**: 평면 insert, dedup 키에 content_type 포함, movie 전용 컬럼(runtime 등) 검증.
- **series 경로**: CSV 에 `series_title`/`season_number`/`episode_number` 컬럼 →
  series→season→episode upsert 로 parent_id 계층 자동 구성. 메타는 상속(D3)으로 해석.
- 두 경로 각각 sample CSV E2E 테스트.

### D10. Frontend 반영 (설계는 Phase D 에서 상세)

- **검색 조건문**: `content_type=series` → 계층 그룹/트리, `movie` → 평면,
  `season|episode` → 독립 필터(부모 컬럼 노출).
- **3단 추천화면**(`[id]/recommend` cells): series 계열은 브레드크럼(시리즈>시즌>에피소드)
  + 상속값 read-only(회색), override 시 강조.
- **3탭(글자/이미지/영상)**: movie/series/season/episode 조건부 — episode 는 상속 배지.
- **bulk 업로드**: movie/series 템플릿 분리 + series 계층 컬럼 가이드.

---

## Consequences

- 라우팅 SSOT 1개 → A~C 중복 제거, season/episode TMDB TV 정상 조회.
- 상속 read-time → 부모 변경 즉시 반영, 마이그레이션 불필요, 쿼리 시 resolver 비용 추가.
- dedup/delete 무결성 확보, 단 기존 데이터에 대한 1회 정합 점검 필요(별도 follow-up 가능).
- Frontend 검색/추천/업로드 화면이 content_type 분기 → 컴포넌트 조건부 복잡도 증가.

## 비범위 (Out of scope)

- 기존 운영 데이터의 소급 계층 재구성(backfill) — 필요 시 별도 task.
- season/episode 별 영상 기술 메타(코덱·DRM) 정책 — 기존 유지.
