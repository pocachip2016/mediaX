# Step 2: external-source-merge

> GitHub: 미생성 | Milestone: dev-meta-core-extraction

## 읽어야 할 파일
- `plans/dev-meta-core-extraction/step0.md` (이관 대상: kobis_movie_cd, tmdb_id)
- `backend/api/programming/metadata/ai_engine.py:236-319` (legacy 컬럼 쓰는 위치)
- `backend/workers/tasks/metadata.py:475-514` (ExternalMetaSource 정상 패턴)

## 현황 분석

| 경로 | 현재 동작 |
|---|---|
| `ai_engine.process_content_ai` | kobis_movie_cd/tmdb_id → ContentMetadata만 씀. ExternalMetaSource 미기록 |
| `workers.tasks.metadata.enrich_content_metadata` | ExternalMetaSource 정상 기록 (already correct) |
| `service.suggest_text_meta` | ExternalMetaSource read-path 사용 (already correct) |

**갭**: AI 처리(ai_engine) 경로에서 ExternalMetaSource 가 생성되지 않아, 해당 경로로 처리된 콘텐츠는 text_meta 제안에서 KOBIS/TMDB 데이터가 누락됨.

## 작업

### 1. ai_engine.py — 듀얼라이트 추가
`process_content_ai` (line 286-289) 직후, kobis_movie_cd / tmdb_id 기록 시 ExternalMetaSource 도 upsert.

```python
# 추가할 import (함수 내 lazy import 블록에 추가)
from api.programming.metadata.models import ExternalMetaSource, ExternalSourceType

# kobis upsert
if result.kobis_match and result.kobis_match.get("movieCd"):
    _upsert_external_source(db, content_id, ExternalSourceType.kobis,
                            result.kobis_match["movieCd"], result.kobis_match)

# tmdb upsert
if result.tmdb_match and result.tmdb_match.get("id"):
    _upsert_external_source(db, content_id, ExternalSourceType.tmdb,
                            str(result.tmdb_match["id"]), result.tmdb_match)
```

헬퍼 함수 `_upsert_external_source` 는 ai_engine.py 상단에 추가 (module-level).

### 2. 백필 스크립트 — 기존 레거시 데이터 마이그레이션
`backend/scripts/backfill_external_meta_sources.py`:
- ContentMetadata 에 kobis_movie_cd/tmdb_id 가 있으나 ExternalMetaSource 행이 없는 레코드 탐지
- ExternalMetaSource 행 생성 (match_confidence=None, matched_at=created_at)
- dry_run 모드 지원

## Acceptance Criteria

```bash
cd /home/ktalpha/Work/mediaX/backend
source .venv/bin/activate
# 1. 임포트 검증
python3 -c "from api.programming.metadata.ai_engine import _upsert_external_source; print('helper OK')"
# 2. 백필 dry-run
python3 scripts/backfill_external_meta_sources.py --dry-run
```

## 금지사항
- ContentMetadata.kobis_movie_cd/tmdb_id 컬럼 삭제 금지 (step7 에서 처리)
- enrich_content_metadata (workers) 코드 수정 금지 — 이미 올바름
- alembic 마이그레이션 파일 추가 금지 (스키마 변경 없음)
