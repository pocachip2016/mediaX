# Step 1: migration-0011-candidates-resolutions-seeds

> GitHub: 미생성 | Milestone: dev-meta-intelligence (Phase A)

## 읽어야 할 파일
- `docs/dev/meta-intelligence.md` (step0 산출 — §1 용어, §2 분류, §6 KMDb)
- `backend/api/programming/metadata/models/external.py` (ExternalSourceType ENUM 위치)
- `backend/api/programming/metadata/models/tmdb_cache.py` (TmdbSyncSource ENUM 위치)
- `backend/alembic/versions/0010_add_dam_events.py` (직전 마이그레이션 스타일 참고)
- `backend/api/programming/metadata/models/content.py` (Content / ContentMetadata FK 대상)

## 목적
Phase B 의 모든 흐름이 의존하는 5개 테이블을 한 번에 신설하고 ENUM 도 함께 확장.
Phase B 시작 시 마이그레이션이 이미 끝나 있어야 코드 step 들이 자유롭게 진행됨.

## 작업

### 1. ENUM 확장 (in-place 변경, 새 마이그레이션 안에서)

#### `ExternalSourceType` 에 `kmdb` 추가
- `backend/api/programming/metadata/models/external.py:18` 의 enum 클래스에 `kmdb = "kmdb"` 한 줄 추가
- 마이그레이션 0011 의 `upgrade()` 에서 PostgreSQL 의 `externalsourcetype` enum 에 `ALTER TYPE ... ADD VALUE 'kmdb'` 실행
- SQLite 는 enum 이 VARCHAR 라 별도 처리 불필요 (alembic env.py 의 `is_sqlite` 분기 활용)

### 2. 새 테이블 5종 — 마이그레이션 0011

파일명: `backend/alembic/versions/0011_meta_intelligence_tables.py`
revision: `0011_meta_intelligence_tables`, down_revision: `0010_add_dam_events`

#### 2-1. `metadata_candidates` — 정규화된 외부 후보 메타
```
id                  BIGINT PK
source_type         ExternalSourceType (FK 없음, ENUM)
source_external_id  VARCHAR(255)             -- TMDB id, KOBIS movieCd, KMDb DOCID 등
source_url          VARCHAR(2000) NULL
raw_payload         JSON NOT NULL            -- 원본 응답 원형 보존
title_norm          VARCHAR(500) NOT NULL    -- 정규화 제목 (소문자 + 특수문자 제거)
original_title      VARCHAR(500) NULL
year                INT NULL
content_type        VARCHAR(20) NULL         -- movie/series/season/episode
synopsis            TEXT NULL
poster_url          VARCHAR(2000) NULL
cast_json           JSON NULL                -- [{name, role, order}, ...]
director_json       JSON NULL                -- [{name}, ...]
genre_json          JSON NULL                -- ["드라마", "스릴러"]
external_ids_json   JSON NULL                -- {tmdb: 12345, kobis: "20231234"}
fetched_at          TIMESTAMP NOT NULL
status              VARCHAR(20) NOT NULL DEFAULT 'active'  -- active/expired/rejected

UNIQUE(source_type, source_external_id)
INDEX(title_norm, year)
INDEX(fetched_at)
```

#### 2-2. `match_edges` — candidate ↔ 내부 Content 매칭
```
id                  BIGINT PK
candidate_id        BIGINT FK metadata_candidates ON DELETE CASCADE
content_id          BIGINT FK contents ON DELETE CASCADE NULL
score               FLOAT NOT NULL                -- 0.0 ~ 1.0
reasons_json        JSON NOT NULL                 -- ["title_exact", "year_match", "cast_overlap"]
sub_scores_json     JSON NULL                     -- {title:0.3, year:0.2, cast:0.15, ...}
decided             BOOLEAN NOT NULL DEFAULT false
decided_at          TIMESTAMP NULL
decided_by          VARCHAR(100) NULL             -- "system" | username
created_at          TIMESTAMP NOT NULL

INDEX(candidate_id)
INDEX(content_id)
INDEX(score)
UNIQUE(candidate_id, content_id)
```

#### 2-3. `field_suggestions` — 필드 단위 raw 후보
```
id                  BIGINT PK
content_id          BIGINT FK contents ON DELETE CASCADE
field_name          VARCHAR(50) NOT NULL          -- synopsis | poster | director | cast | ...
value_json          JSON NOT NULL                 -- 단일값/리스트/URL 모두 JSON
source_candidate_id BIGINT FK metadata_candidates NULL
source_type         ExternalSourceType NOT NULL
confidence          FLOAT NOT NULL DEFAULT 0.0
status              VARCHAR(20) NOT NULL DEFAULT 'pending'  -- pending/applied/rejected/superseded
created_at          TIMESTAMP NOT NULL

INDEX(content_id, field_name)
INDEX(status)
```

#### 2-4. `field_resolutions` — (content_id, field) 결정 1행
```
id                       BIGINT PK
content_id               BIGINT FK contents ON DELETE CASCADE
field_name               VARCHAR(50) NOT NULL
decision                 VARCHAR(30) NOT NULL
                         -- auto_agreement | auto_quality | manual_pick | manual_merge
                         -- pending | rejected
chosen_value_json        JSON NULL                  -- 적용된 값
chosen_suggestion_ids    JSON NULL                  -- [12, 17, 19] (merge 면 N개)
agreement_count          INT NOT NULL DEFAULT 0
agreeing_sources_json    JSON NULL                  -- ["tmdb", "kmdb"]
merge_method             VARCHAR(20) NULL           -- pick | union | llm_merge | quality_pick
applied_to_content       BOOLEAN NOT NULL DEFAULT false
decided_by               VARCHAR(100) NULL          -- "system" | username
decided_at               TIMESTAMP NULL
created_at               TIMESTAMP NOT NULL

UNIQUE(content_id, field_name)
INDEX(decision)
INDEX(applied_to_content)
```

#### 2-5. `seed_candidates` — 신규 콘텐츠 후보 (Phase C 에서 본격 사용)
```
id                  BIGINT PK
candidate_id        BIGINT FK metadata_candidates ON DELETE CASCADE
title               VARCHAR(500) NOT NULL
content_type        VARCHAR(20) NULL
evidence_urls_json  JSON NULL                  -- 근거 URL 목록
confidence          FLOAT NOT NULL DEFAULT 0.0
reason_json         JSON NULL                  -- ["not_found_in_internal_db", "seen_in_2_sources"]
status              VARCHAR(20) NOT NULL DEFAULT 'pending_review'
                    -- pending_review | approved | rejected | duplicate
created_content_id  BIGINT FK contents ON DELETE SET NULL NULL
decided_by          VARCHAR(100) NULL
decided_at          TIMESTAMP NULL
created_at          TIMESTAMP NOT NULL

INDEX(status)
INDEX(created_at)
```

### 3. SQLAlchemy 모델 추가

위치: `backend/api/meta_core/models/intelligence.py` (신규 파일)
- `MetadataCandidate`, `MatchEdge`, `FieldSuggestion`, `FieldResolution`, `SeedCandidate` 5 클래스
- `meta_core/models/__init__.py` 의 re-export 목록에 추가
- `alembic/env.py` 의 import 라인에 본 모듈 추가 (autogenerate 인식)

### 4. external_sync_log 보강 (선택)
ADR §7 의 모니터링용 — 자동 확정 카운트:
- `external_sync_log` 에 `auto_resolved_count INT NULL DEFAULT 0`, `manual_review_count INT NULL DEFAULT 0` 2 컬럼 추가
- 본 step 의 마이그레이션 같은 파일에 포함

## Acceptance Criteria
```bash
# 1. 마이그레이션 적용 가능 (SQLite + PostgreSQL)
cd backend && alembic upgrade head

# 2. 모델 import smoke test
python3 -c "
from api.meta_core.models.intelligence import (
    MetadataCandidate, MatchEdge, FieldSuggestion, FieldResolution, SeedCandidate
)
from api.programming.metadata.models.external import ExternalSourceType
assert ExternalSourceType.kmdb == 'kmdb'
print('OK')
"

# 3. ENUM 확인 (PostgreSQL)
# DATABASE_URL=postgresql://... 환경에서:
psql -c "SELECT unnest(enum_range(NULL::externalsourcetype));"
# kobis, tmdb, watcha, netflix, naver, daum, other, kmdb 출력

# 4. /verify
bash .claude/verify.sh meta-intelligence-step1
```

## 금지사항
- **CRUD 코드 작성 금지.** 모델 + 마이그레이션만. service/router 는 다음 step 들에서.
  이유: 마이그레이션 단독 PR 로 격리하면 롤백·리뷰 단순.
- **데이터 백필 금지.** 빈 테이블로 시작.
  이유: candidate 는 Phase B 의 enrich 흐름에서만 채워져야 의미가 있음.
- **`tmdb_id`, `kobis_movie_cd` 컬럼 부활 금지.** ExternalMetaSource SSOT 원칙 유지.
  이유: 0009 마이그레이션이 막 정리한 것을 되돌리는 회귀.
- **ContentMetadata 직접 수정 금지.** field_resolutions → 적용 흐름은 step7(Aggregator) 에서.
  이유: Aggregator 미존재 상태에서 직접 쓰면 audit trail 비어버림.
