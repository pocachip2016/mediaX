# Step 1: Bulk Core Actions

> GitHub: (미생성) | Milestone: dev-api-consolidation

## Context

bulk reprocess/enrich/process/recall/delete 5개 엔드포인트를 구현한다.
모두 비동기 패턴: ids 검증 → ContentBatchJob 생성 → Celery task 큐잉 → 202 + JobStatusOut 반환.

## 읽어야 할 파일

- Step 0 완료 후: `backend/api/programming/metadata/schemas.py` (BulkActionRequest, BulkActionResponse 등)
- `backend/api/programming/metadata/models/content.py` — ContentBatchJob 모델
- `backend/api/programming/metadata/service.py` — 기존 service 함수 패턴 참고
- `backend/api/programming/metadata/router.py` — 기존 route 정의 방식

## 작업

### 1. `backend/api/programming/metadata/service.py`에 5개 함수 추가

```python
async def bulk_reprocess(
    db: Session,
    ids: List[int],
    reason: Optional[str] = None,
    sync_mode: bool = False  # env BULK_SYNC_MODE
) -> JobStatusOut:
    """
    Bulk reprocess — review/processing.error 상태인 contents만 처리.
    부적합 상태는 errors[] 에 모음.
    """

async def bulk_enrich(db, ids, reason, sync_mode) -> JobStatusOut:
    """Bulk external rematch."""

async def bulk_process(db, ids, reason, sync_mode) -> JobStatusOut:
    """Bulk 즉시 처리 (status = processed)."""

async def bulk_recall(db, ids, reason, sync_mode) -> JobStatusOut:
    """Bulk recall — approved/rejected만 → review로 되돌림."""

async def bulk_delete(db, ids, reason, sync_mode) -> JobStatusOut:
    """Soft delete (is_deleted=True)."""
```

**공통 패턴:**
- ids 존재 여부 검증 (DB에서 로드)
- 상태 조건 필터링 (부적합하면 errors[] 추가)
- ContentBatchJob 생성 (action_type, target_ids, status='pending')
- sync_mode=True면 동기 실행 (await process_bulk_* task), 아니면 Celery .delay() 큐잉
- 202 + JobStatusOut 반환

### 2. `backend/api/programming/metadata/router.py`에 5개 route 추가

```python
@router.post("/bulk/reprocess", response_model=BulkActionResponse)
async def api_bulk_reprocess(req: BulkActionRequest, db: Session = Depends(get_db)):
    ...

@router.post("/bulk/enrich", response_model=BulkActionResponse)
async def api_bulk_enrich(req, db): ...

@router.post("/bulk/process", response_model=BulkActionResponse)
async def api_bulk_process(req, db): ...

@router.post("/bulk/recall", response_model=BulkActionResponse)
async def api_bulk_recall(req, db): ...

@router.delete("/bulk", response_model=BulkActionResponse)
async def api_bulk_delete(req, db): ...
```

### 3. `backend/workers/metadata_tasks.py`에 Celery task 추가

```python
@shared_task
def process_bulk_reprocess(job_id: str):
    """ContentBatchJob.id=job_id를 처리."""

@shared_task
def process_bulk_enrich(job_id: str):
    """..."""
```

기존 `process_content_metadata` task 재사용 (for 루프로 각 content_id에 대해 호출).

### 4. 테스트: `backend/tests/api/programming/metadata/test_dev_api_consolidation_bulk_core.py`

- 각 endpoint 5건 (happy path + 부적합 상태 rejection)
- mock Celery in sync mode (BULK_SYNC_MODE=true)

## Acceptance Criteria

```bash
cd backend
bash .claude/verify.sh dev-api-step1
# 또는
pytest tests/api/programming/metadata/test_dev_api_consolidation_bulk_core.py -v
```

## 금지사항

- ContentActionLog 기록은 아직 금지. Step 2에서 retrofit
- hard delete 금지 (soft only)
- 상태 전이 검증 로직 없음 == 버그 금지 (상태 조건 반드시 명시)
