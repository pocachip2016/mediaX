# Step 4: kobis-sync-completion

> GitHub: 미생성 | Milestone: dev-meta-core-extraction (← Dam M.1 이관)

## 읽어야 할 파일
- `backend/workers/tasks/metadata.py:210-257` (sync_kobis 현재 구현)
- `backend/workers/tasks/metadata.py:670-715` (_kobis_search_and_save — ExternalMetaSource 패턴 참고)
- `plans/dev-meta-core-extraction/step2.md` (_upsert_external_source 패턴)

## 현황 문제점
1. `ExternalMetaSource` 미기록 — text_meta 제안에서 KOBIS 데이터 누락
2. `external_sync_log` 미사용 — 동기화 이력 추적 불가
3. O(N×M) 매칭 — 전체 미매핑 ContentMetadata 루프 × KOBIS 영화 수

## 작업

### 1. TmdbSyncSource ENUM에 kobis 값 추가
`models/tmdb_cache.py`:
```python
kobis_daily = "kobis_daily"
kobis_backfill = "kobis_backfill"
```

### 2. alembic 0007 — PostgreSQL ENUM 확장 (SQLite는 no-op)
```python
bind.dialect.name == 'postgresql' →
  ALTER TYPE tmdbsyncsource ADD VALUE IF NOT EXISTS 'kobis_daily'
  ALTER TYPE tmdbsyncsource ADD VALUE IF NOT EXISTS 'kobis_backfill'
```

### 3. sync_kobis 재작성
- `TmdbSyncLog(source=kobis_daily, external_source=kobis, target_date=yesterday)` 생성
- Content.title DB-레벨 매칭 (O(N) 개선)
- `_upsert_external_source(db, content_id, kobis, movie_cd, movie_raw)` 호출
- `ContentMetadata.kobis_movie_cd` 듀얼라이트 유지 (step2 패턴)
- log.items_inserted/updated, log.status 갱신

## Acceptance Criteria

```bash
cd /home/ktalpha/Work/mediaX/backend
source .venv/bin/activate
DATABASE_URL=sqlite:///./media_ax_dev.db alembic upgrade head
python3 -c "
from api.programming.metadata.models import TmdbSyncSource
assert hasattr(TmdbSyncSource, 'kobis_daily'), 'kobis_daily missing'
assert hasattr(TmdbSyncSource, 'kobis_backfill'), 'kobis_backfill missing'
from workers.tasks.metadata import sync_kobis
print('sync_kobis import OK')
print('ALL PASS')
"
```

## 금지사항
- KOBIS API 실제 호출 금지 (API 키 없는 환경에서 테스트)
- `_kobis_search_and_save` 함수 수정 금지 (enrich 흐름용, 그대로 유지)
