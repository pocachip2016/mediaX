# Step 4: fess-cache-metrics-wiring (Phase C)

> Milestone: fix-external-sync-stability

## 읽어야 할 파일
- `backend/workers/tasks/metadata.py::backfill_kobis` (line 1059~)
- `backend/workers/tasks/metadata.py::sync_kobis`
- `backend/workers/tasks/kmdb_cache.py` (kmdb backfill 함수)

## 작업
캐시 add/update 시 cache_inserted/cache_updated 카운터를 추적해 sync_log에 기록.

산출:
- `backend/workers/tasks/metadata.py::backfill_kobis`
  - `kobis_movie_cache` add 시 `cache_inserted += 1`, 기존 행 update 시 `cache_updated += 1`
  - `log.cache_inserted = cache_inserted`, `log.cache_updated = cache_updated` 기록
- `backend/workers/tasks/metadata.py::sync_kobis` (kobis_daily) — 동일 패턴
- `backend/workers/tasks/kmdb_cache.py::kmdb_quota_backfill_tick` 호출 경로의 캐시 upsert — 동일 패턴
- `backend/tests/test_cache_metrics.py` — 2~3 pytest
  - fake API 응답으로 backfill 호출 시 cache_inserted > 0 확인
  - 같은 데이터 두 번 호출 시 두 번째는 cache_updated 만 증가, cache_inserted = 0 확인

## 검증
```bash
cd backend && pytest tests/test_cache_metrics.py -v
```

## Acceptance Criteria
```bash
/verify fess-cache-metrics-wiring
```

## 금지사항
- ExternalMetaSource 카운터(`inserted`/`updated`/`unchanged`) 의 의미를 변경하지 마라. 별개 메트릭.
- cache upsert 로직 자체 변경 금지. 카운터만 추가.
