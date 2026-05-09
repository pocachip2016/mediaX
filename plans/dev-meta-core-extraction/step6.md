# Step 6: kobis-backfill-expand

> GitHub: 미생성 | Milestone: dev-meta-core-extraction (← Dam M.7 이관)

## 읽어야 할 파일
- `backend/workers/tasks/metadata.py:211-296` (sync_kobis 패턴 참고)
- `backend/workers/celery_app.py` (task_routes 확인)
- `plans/dev-meta-core-extraction/step5.md` (fuzzy 매칭 패턴)

## 현황 문제점
- sync_kobis는 전일 개봉작만 처리 — 1990년대 등 과거 작품 ExternalMetaSource 미연결
- 최신 인기작(박스오피스 상위) 소급 매핑도 없음

## 작업

### `backfill_kobis` Celery 태스크 추가 (`workers/tasks/metadata.py`)

```python
@celery_app.task(name="workers.tasks.metadata.backfill_kobis")
def backfill_kobis(start_year: int = 1990, end_year: int = 1999):
```

- KOBIS `searchMovieList.json`을 `openStartDt=YYYY0101 / openEndDt=YYYY1231` 로 연도별 페이지 순회
- 연도마다 `TmdbSyncLog(source=kobis_backfill, target_year=year)` 생성
- 각 영화: 정확 매칭 → fuzzy fallback(step5 패턴, difflib ratio≥0.85) → `_upsert_external_source`
- log.items_inserted/updated/errors/status 갱신 (sync_kobis 패턴 동일)
- 스킵 조건: `ExternalMetaSource`가 이미 존재 → `items_unchanged` 카운트

### `celery_app.py` task_routes에 backfill_kobis 추가
```python
"workers.tasks.metadata.backfill_kobis": {"queue": "metadata"},
```

## Acceptance Criteria
```bash
cd /home/ktalpha/Work/mediaX/backend
source .venv/bin/activate
DATABASE_URL=sqlite:///./media_ax_dev.db python3 -c "
from workers.tasks.metadata import backfill_kobis
import inspect
sig = inspect.signature(backfill_kobis.run if hasattr(backfill_kobis, 'run') else backfill_kobis)
# start_year, end_year 파라미터 확인
from api.programming.metadata.models import TmdbSyncSource
assert hasattr(TmdbSyncSource, 'kobis_backfill')
print('ALL PASS')
"
```

## 금지사항
- KOBIS API 실제 호출 금지 (API 키 없는 환경)
- Beat 스케줄 등록 금지 — 백필은 수동/일회성 태스크
- start_year/end_year 기본값 변경 금지 (1990~1999 소급이 원래 요구사항)
