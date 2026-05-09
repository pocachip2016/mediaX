# Step 7: legacy-column-drop

> GitHub: 미생성 | Milestone: dev-meta-core-extraction

## 읽어야 할 파일
- `backend/api/programming/metadata/models/content.py:104-165` (ContentMetadata)
- `backend/workers/tasks/metadata.py:353-393` (_async_sync_tmdb)
- `backend/api/programming/metadata/ai_engine.py:360-380` (dual-write 제거 위치)

## 현황
ExternalMetaSource가 SSOT로 완성. 아래 3개 컬럼은 듀얼라이트 기간이 종료됐으므로 제거:

| 컬럼 | 대체 |
|------|------|
| `content_metadata.kobis_movie_cd` | `external_meta_sources.external_id` (source_type=kobis) |
| `content_metadata.kobis_data` | `external_meta_sources.raw_json` (source_type=kobis) |
| `content_metadata.tmdb_id` | `external_meta_sources.external_id` (source_type=tmdb) |

`tmdb_data` 컬럼은 TMDB 풍부 메타(display용) 유지.

## 작업

### 1. `models/content.py` — 3개 컬럼 제거
```python
# 삭제:
kobis_movie_cd = Column(String(20), index=True)
kobis_data = Column(JSON)
tmdb_id = Column(Integer, index=True)
```

### 2. `ai_engine.py` — dual-write 3줄 제거 (ExternalSource upsert는 유지)
```python
# 삭제할 줄:
meta.kobis_data = result.kobis_match
meta.kobis_movie_cd = result.kobis_match["movieCd"]
meta.tmdb_id = result.tmdb_match["id"]
```

### 3. `workers/tasks/metadata.py`

**sync_kobis / backfill_kobis**: 각 ExternalMetaSource 사전 조회로 insert/update 카운트 전환:
```python
prev = db.query(ExternalMetaSource).filter(...).first()
_upsert_external_source(...)
if prev: updated += 1 else: inserted += 1
```
kobis_movie_cd / kobis_data 쓰기 제거.

**_async_sync_tmdb**: `ContentMetadata.tmdb_id.is_(None)` → ExternalMetaSource anti-join:
```python
.outerjoin(ExternalMetaSource,
    (ExternalMetaSource.content_id == Content.id) &
    (ExternalMetaSource.source_type == ExternalSourceType.tmdb))
.filter(ExternalMetaSource.id.is_(None), ...)
```
`meta.tmdb_id = result["id"]` 쓰기 제거.

**_async_enrich_content**: `meta.tmdb_id`, `meta.kobis_movie_cd`, `meta.kobis_data` 쓰기 제거.

### 4. Alembic 0009 — 3 컬럼 + 인덱스 drop
```python
op.drop_index("ix_content_metadata_kobis_movie_cd", "content_metadata")
op.drop_index("ix_content_metadata_tmdb_id", "content_metadata")
op.drop_column("content_metadata", "kobis_movie_cd")
op.drop_column("content_metadata", "kobis_data")
op.drop_column("content_metadata", "tmdb_id")
```

## Acceptance Criteria
```bash
cd /home/ktalpha/Work/mediaX/backend
source .venv/bin/activate
DATABASE_URL=sqlite:///./media_ax_dev.db alembic upgrade head
python3 -c "
from api.programming.metadata.models.content import ContentMetadata
assert not hasattr(ContentMetadata, 'kobis_movie_cd'), 'kobis_movie_cd still present'
assert not hasattr(ContentMetadata, 'tmdb_id'), 'tmdb_id still present'
from workers.tasks.metadata import sync_kobis
print('ALL PASS')
"
```

## 금지사항
- `tmdb_data` 컬럼 건드리지 않음 (display용 TMDB 풍부 데이터)
- `_kobis_search_and_save` 수정 금지
- `schemas.py`의 `TmdbSyncedItem.tmdb_id` 필드 건드리지 않음 (ext.external_id 읽기 — 이미 ExternalMetaSource 기반)
