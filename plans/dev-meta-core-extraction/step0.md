# Step 0: inventory

> GitHub: 미생성 | Milestone: dev-meta-core-extraction

## 읽어야 할 파일
- `backend/api/programming/metadata/models/content.py`
- `backend/api/programming/metadata/models/external.py`
- `backend/api/programming/metadata/models/tmdb_cache.py`
- `backend/api/programming/metadata/CLAUDE.md`

---

## 분석 결과: 테이블별 Layer 분류

### 1. contents 테이블 (`Content` 모델)

| 컬럼 | Layer | 이유 |
|---|---|---|
| id, title, original_title | **meta_core** | 작품 자체 식별자 |
| content_type | **meta_core** | movie/series/season/episode 계층 — 단, variety·documentary 확장 필요 |
| production_year, runtime_minutes, country | **meta_core** | 작품 속성 |
| parent_id, season_number, episode_number | **meta_core** | 계층 구조 |
| created_at, updated_at | **meta_core** | |
| **status** | **service_kt** | waiting/processing/staging/approved/rejected — KT 편성 워크플로우 |
| **cp_name, cp_email_id** | **service_kt** | CP사 관계 — KT 비즈니스 |

> **결정**: Content 테이블은 분리하지 않고 유지. status·cp_name·cp_email_id 는 service 필드임을 주석으로 명기.

---

### 2. content_metadata 테이블 (`ContentMetadata` 모델) ← 혼재 심각

| 컬럼 그룹 | 컬럼 | Layer | 이관 방향 |
|---|---|---|---|
| CP 원본 메타 | cp_synopsis, cp_genre, cp_tags, cp_cast, cp_poster_url | **service_kt** | 유지 (KT CP 워크플로우) |
| AI 생성 메타 | ai_synopsis, ai_genre_primary/secondary, ai_mood_tags, ai_cast, ai_rating_suggestion | **service_kt** | 유지 (KT AI 처리 결과) |
| **외부 ID (레거시)** | **kobis_movie_cd, kobis_data** | ~~Layer1 오염~~ | **ExternalMetaSource 행으로 마이그레이션 후 DROP** |
| **외부 ID (레거시)** | **tmdb_id, tmdb_data** | ~~Layer1 오염~~ | **ExternalMetaSource 행으로 마이그레이션 후 DROP** |
| 확정 메타 | final_synopsis, final_genre, final_tags, final_cast, final_source | **service_kt** | 유지 (KT 검수 결과) |
| 품질 | quality_score, score_breakdown | **service_kt** | 유지 (KT 품질 기준) |
| 완료 플래그 | text/image/video_meta_completed | **service_kt** | 유지 (KT 워크플로우 플래그) |
| 기술 메타 | video_resolution/format, codec_*, bitrate, duration, subtitle_languages | **service_kt** | 유지 (KT 납품 파일 기술 정보) |
| DRM | drm_type | **service_kt → ContentDistribution** | step0 이후 ContentDistribution 으로 이동 예정 |
| KT 노출 | preview_clip_url | **service_kt** | 유지 |
| 처리 이력 | ai_processed_at, reviewed_by, reviewed_at | **service_kt** | 유지 |

> **이 단계 핵심 작업**: `kobis_movie_cd/kobis_data` + `tmdb_id/tmdb_data` → `ExternalMetaSource` rows 로 마이그레이션

---

### 3. external_meta_sources 테이블 (`ExternalMetaSource`) ← 이미 meta_core 패턴

현재 컬럼: content_id(nullable), source_type ENUM, external_id, title_on_source, raw_json, match_confidence, matched_at

**수정 필요:**
- `content_id nullable=True` → `NOT NULL` 로 변경 (매핑 전 임시 행이면 content_id 없는 것이 문제)
- `ExternalSourceType` ENUM 확장: `imdb`, `youtube` 추가 예정
- **이 테이블이 KOBIS/TMDB/IMDb 메타 권위 레코드의 SSOT**

---

### 4. tmdb_*_cache + TmdbSyncLog ← meta_core 이동 대상

| 테이블 | 현재 위치 | 이동 후 |
|---|---|---|
| tmdb_movie_cache | programming/metadata | meta_core/cache/ |
| tmdb_tv_cache | programming/metadata | meta_core/cache/ |
| tmdb_person_cache | programming/metadata | meta_core/cache/ |
| tmdb_sync_log | programming/metadata | → external_sync_log (통합, step3) |

`TmdbSyncLog` 는 step3에서 source_type 컬럼 추가 후 `external_sync_log` 로 rename.

---

### 5. person_master, content_credits ← meta_core

- `PersonMaster`: name_ko/name_en, tmdb_person_id, kobis_person_id, birthday, deathday, profile_path, raw_json → **meta_core**
- `ContentCredit`: content_id ↔ person_id (role/character/cast_order) → **meta_core**

---

### 6. genre_codes, tag_codes, content_genres, content_tags ← meta_core

장르/태그 마스터 및 M:N 링크 — 모두 meta_core. `source` 필드(`tmdb/kobis/ai/manual`)로 출처 구분 가능.

---

### 7. content_images ← meta_core

poster/thumbnail/stillcut — TMDB·KOBIS 포스터는 meta_core 이미지. KT 자체 제작 이미지도 동일 테이블에 `source=manual` 로 보관.

---

### 8. service_kt 전용 테이블 (이동 불필요, 레이블링만)

| 테이블 | Layer | 비고 |
|---|---|---|
| content_ai_results | service_kt | KT AI 처리 이력 |
| content_batch_jobs | service_kt | KT CP 배치 업로드 |
| cp_email_logs | service_kt | KT CP 이메일 수신 |

---

## 신규 테이블 (이후 step에서 생성)

| 테이블 | Step | Layer |
|---|---|---|
| external_sync_log | step3 | meta_core (tmdb_sync_log 일반화) |
| kobis_movie_cache | step4 | meta_core |
| web_search_cache | step5 | meta_core |
| ContentDistribution | dev-service-distribution step0 | service_kt |

---

## 모듈 이동 계획

```
backend/api/
├── meta_core/              ← 신설 (step1)
│   ├── content/            Contents, PersonMaster, ContentCredit
│   ├── taxonomy/           GenreCode, TagCode, M:N
│   ├── image/              ContentImage
│   ├── external/           ExternalMetaSource
│   ├── cache/              TmdbMovieCache, TmdbTvCache, TmdbPersonCache
│   └── public_api/         Dam 등 외부 소비자용 read-only (dev-dam-bridge step0)
└── programming/
    └── metadata/           ContentMetadata (service_kt 필드 유지), 워크플로우 로직
```

---

## Acceptance Criteria

```bash
# 이 step 은 분석 문서 작성 — 코드 변경 없음
# 검증: 아래 두 조건 확인
# 1. step0.md 매핑표에서 모든 14개 테이블 분류 완료
# 2. 이관 필요 컬럼(kobis_movie_cd, kobis_data, tmdb_id, tmdb_data) 목록과 대상 명확
echo "inventory step0: doc-only, no code changes"
```

## 금지사항
- 이 step 에서 코드·마이그레이션 수정 금지. 매핑 확정만.
