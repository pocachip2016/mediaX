# Step C.1: migration-0012-seeds

> GitHub: 미생성 | Milestone: dev-meta-intelligence-phase-c

## 읽어야 할 파일
- `docs/dev/meta-intelligence-phase-c.md` (이전 step 산출물 — §1 라이프사이클 + §4 dedup)
- `backend/alembic/versions/0011_*.py` (Phase A 마이그레이션 — 신규 5테이블 패턴 참고)
- `backend/api/meta_core/models/intelligence.py` (MetadataCandidate/MatchEdge/FieldSuggestion 현 스키마)
- `backend/api/programming/metadata/models/external.py` (ExternalSourceType)

## 작업

### 1. alembic 0012 마이그레이션 신설

**신규 테이블 `content_seeds`**:
```
id              SERIAL PK
source_type     ExternalSourceType (tmdb/kobis/kmdb/omdb)
external_id     VARCHAR(64) — 원본 식별자
title           VARCHAR(500)
original_title  VARCHAR(500) NULL
content_type    movie/series/episode/season
production_year INT NULL
poster_url      TEXT NULL
synopsis        TEXT NULL
raw_payload     JSONB — 원본 응답 보관 (감사·재처리)
status          discovered | candidate | under_review | accepted | rejected
locked_by       VARCHAR(64) NULL — 검토 잠금 사용자
locked_at       TIMESTAMP NULL — 잠금 시작 (TTL 15분)
discovered_at   TIMESTAMP DEFAULT now()
updated_at      TIMESTAMP DEFAULT now() ON UPDATE now()
promoted_to_content_id INT NULL FK → contents.id (accepted 시점에 set)
alt_external_ids JSONB DEFAULT '{}' — 다른 소스에서 같은 SEED 매칭 시 누적

UNIQUE (source_type, external_id)
INDEX (status, discovered_at)
INDEX (content_type, production_year)
```

**신규 테이블 `seed_discovery_log`**:
```
id              SERIAL PK
source_type     ExternalSourceType
discovery_mode  trending_day | trending_week | upcoming | discover | new_release | box_office | other
fetched_at      TIMESTAMP DEFAULT now()
total_fetched   INT
new_seeds       INT — content_seeds 신규 행
matched_existing INT — 기존 Content 매칭 (SEED 미적재)
duplicates      INT — SEED 중복 (UPSERT)
errors          INT
duration_ms     INT
metadata        JSONB — region, page, query 등 호출 파라미터
```

**ExternalSourceType ENUM 확장**:
- `omdb = "omdb"` 추가
- alembic op.execute로 PostgreSQL ENUM ALTER TYPE (downgrade 시 sqlite 경고 OK)

**MetadataCandidate 컬럼 추가**:
- `target_type VARCHAR(20) DEFAULT 'content'` — content | content_seed
- `target_id INT NULL` — content_id 또는 content_seed_id (target_type 따라)
- 기존 content_id 유지하되 nullable 로 변환 (target_id 가 진실 source)

### 2. ORM 모델
`backend/api/meta_core/models/seed.py` 신설:
```python
class ContentSeed(Base):
    __tablename__ = "content_seeds"
    # 위 컬럼 모두 매핑
    # property: is_locked → locked_at + 15분 TTL 검사

class SeedDiscoveryLog(Base):
    __tablename__ = "seed_discovery_log"
```

`models/__init__.py` 에 re-export 추가.

### 3. 검증
- alembic upgrade head 통과 (sqlite + postgresql)
- ORM import 통과 — `from api.meta_core.models import ContentSeed, SeedDiscoveryLog`

## Acceptance Criteria
```bash
bash .claude/verify.sh phase-c-step1
```

- alembic 0012 파일 존재
- alembic upgrade head 성공
- `ContentSeed`, `SeedDiscoveryLog` import 가능
- `ExternalSourceType.omdb` enum 추가됨
- `MetadataCandidate.target_type`, `target_id` 컬럼 추가됨

## 금지사항
- 비즈니스 로직 금지 — 스키마/모델만
- content_seeds 에 confidence/score 컬럼 금지 — 점수는 MatchEdge 가 들고 있음
- Content 테이블 컬럼 추가/수정 금지 — Phase C 는 별도 SEED 테이블만 다룸
