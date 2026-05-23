# Step 1: fess-link-source-enum (Phase B)

> Milestone: fix-external-sync-stability

## 읽어야 할 파일
- `backend/workers/tasks/metadata.py` (link_kmdb_cache_to_contents, link_kobis_cache_to_contents, link_tmdb_cache_to_contents)
- `backend/api/programming/metadata/models.py` (TmdbSyncSource enum)

## 작업
link task의 source enum을 backfill에서 link로 교체.

산출:
- `backend/workers/tasks/metadata.py`
  - `link_kmdb_cache_to_contents`: `TmdbSyncSource.kmdb_backfill` → `TmdbSyncSource.kmdb_link`
  - `link_kobis_cache_to_contents`: `TmdbSyncSource.kobis_backfill` → `TmdbSyncSource.kobis_link`
  - `link_tmdb_cache_to_contents`: 동일 패턴 점검·수정 (tmdb_link enum 존재 확인 후)
- `backend/tests/test_link_source_enum.py` — link task가 *_link enum으로 sync_log를 만드는지 1~2개 단위테스트

## 검증
```bash
cd backend && pytest tests/test_link_source_enum.py -v
```

## Acceptance Criteria
```bash
/verify fess-link-source-enum
```

## 금지사항
- 기존 sync_log 행을 retroactive 하게 update 하지 마라. 이유: 과거 통계 보존.
- backfill task 의 enum 은 건드리지 마라. backfill은 그대로 *_backfill 유지.
