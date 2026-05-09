# Step 1: meta-core-module

> GitHub: 미생성 | Milestone: dev-meta-core-extraction

## 읽어야 할 파일
- `plans/dev-meta-core-extraction/step0.md` (분류 매핑표)
- `backend/main.py` (라우터 등록 패턴)
- `backend/alembic/env.py` (모델 import 방식)
- `backend/api/programming/metadata/models/__init__.py`

## 작업

`backend/api/meta_core/` 모듈 경계를 신설한다. 이 step 에서 모델 파일의 물리적 이동은 하지 않는다 — 기존 import 경로를 모두 유지하면서 meta_core 가 re-export 래퍼 역할을 하도록 한다.

1. 디렉토리 + `__init__.py` 생성:
   ```
   backend/api/meta_core/
   ├── __init__.py
   ├── router.py          ← 빈 APIRouter, /api/meta-core prefix
   └── models/
       └── __init__.py    ← 기존 모델 re-export
   ```

2. `meta_core/models/__init__.py` 에서 step0 분류 결과에 따른 meta_core 모델들을 re-export:
   - Content, ContentType, ContentStatus, MetaSource (content.py)
   - PersonMaster, ContentCredit (person.py)
   - GenreCode, TagCode, ContentGenre, ContentTag (taxonomy.py)
   - ContentImage (image.py)
   - ExternalMetaSource, ExternalSourceType, ContentAIResult (external.py)
   - TmdbMovieCache, TmdbTvCache, TmdbPersonCache, TmdbSyncLog, TmdbSyncSource, TmdbSyncStatus (tmdb_cache.py)

3. `main.py` 에 meta_core 라우터 등록 (`/api/meta-core` prefix)

4. `alembic/env.py` 에 `import api.meta_core.models  # noqa: F401` 추가 (모델 등록 보장)

## Acceptance Criteria

```bash
cd /home/ktalpha/Work/mediaX/backend
python3 -c "from api.meta_core.models import Content, PersonMaster, ExternalMetaSource, TmdbMovieCache; print('meta_core models OK')"
python3 -c "from api.meta_core.router import router; print('router OK')"
# 기존 import 경로도 계속 동작해야 함
python3 -c "from api.programming.metadata.models.content import Content; print('legacy import OK')"
```

## 금지사항
- 기존 모델 파일(content.py, person.py 등) 수정 금지 — 이 step 은 새 디렉토리 + re-export 만
- 테이블명·컬럼·마이그레이션 변경 금지
- service.py, router.py, schemas.py 수정 금지
