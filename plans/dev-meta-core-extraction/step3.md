# Step 3: sync-log-generalize

> GitHub: 미생성 | Milestone: dev-meta-core-extraction

## 읽어야 할 파일
- `backend/api/programming/metadata/models/tmdb_cache.py:113-136` (TmdbSyncLog 현재 구조)
- `backend/workers/tasks/tmdb_cache.py:247,425,522` (TmdbSyncLog 생성 3곳)

## 작업

`tmdb_sync_log` 테이블에 `external_source` 컬럼을 추가하고 `external_sync_log` 로 rename.
KOBIS(step4), 웹서치(step5) 등 신규 소스가 동일 테이블을 사용할 수 있게 됨.

변경 범위:
1. `models/tmdb_cache.py` — `__tablename__` rename + `external_source` 컬럼 추가
2. `alembic/versions/0006_external_sync_log.py` — rename_table + add_column + backfill
3. `workers/tasks/tmdb_cache.py` — TmdbSyncLog 생성 3곳에 `external_source=ExternalSourceType.tmdb` 추가

## Acceptance Criteria

```bash
cd /home/ktalpha/Work/mediaX/backend
source .venv/bin/activate
DATABASE_URL=sqlite:///./media_ax_dev.db alembic upgrade head
python3 -c "
from api.programming.metadata.models import TmdbSyncLog
print('tablename:', TmdbSyncLog.__tablename__)
assert TmdbSyncLog.__tablename__ == 'external_sync_log'
from sqlalchemy import inspect as sa_inspect
from shared.database import engine
cols = [c['name'] for c in sa_inspect(engine).get_columns('external_sync_log')]
assert 'external_source' in cols, f'external_source not in {cols}'
print('external_source column OK')
print('ALL PASS')
"
```

## 금지사항
- TmdbMovieCache / TmdbTvCache / TmdbPersonCache 모델 수정 금지
- service.py 함수 로직 수정 금지 (컬럼 추가만, 기존 쿼리 그대로)
