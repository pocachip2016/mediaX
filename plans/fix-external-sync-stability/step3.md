# Step 3: fess-cache-metrics-schema (Phase C)

> Milestone: fix-external-sync-stability

## 읽어야 할 파일
- `backend/api/programming/metadata/models.py` (TmdbSyncLog)
- `backend/alembic/versions/` (최신 migration 번호 확인)

## 작업
external_sync_log에 캐시 측 카운터 컬럼 2개 추가.

산출:
- `backend/alembic/versions/0019_external_sync_log_cache_metrics.py`
  - `cache_inserted INTEGER NOT NULL DEFAULT 0` 추가
  - `cache_updated INTEGER NOT NULL DEFAULT 0` 추가
  - downgrade: 컬럼 drop
- `backend/api/programming/metadata/models.py` — `TmdbSyncLog` 모델에 두 필드 추가

## 검증
```bash
cd backend && alembic upgrade head
docker exec mediax-postgres-1 psql -U media_ax -d media_ax -c "\d external_sync_log" | grep -E "cache_inserted|cache_updated"
```

## Acceptance Criteria
```bash
/verify fess-cache-metrics-schema
```

## 금지사항
- 기존 `items_inserted`/`items_updated` 의 semantic 변경 금지. 이유: ExternalMetaSource 카운터로 그대로 유지하고 cache 측은 새 컬럼으로 분리.
