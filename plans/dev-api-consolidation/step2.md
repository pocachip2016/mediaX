# Step 2: Job Lifecycle + ContentActionLog

> GitHub: (미생성) | Milestone: dev-api-consolidation

## Context

job 상태 조회·undo·retry 3개 엔드포인트를 추가하고, ContentActionLog 모델을 신규 생성해 undo 기능을 지원한다.
또한 Step 1의 bulk 액션들을 retrofit해서 ContentActionLog 기록을 추가한다.

## 읽어야 할 파일

- Step 0, 1 완료 후: `backend/api/programming/metadata/schemas.py` (JobStatusOut 등)
- `backend/api/programming/metadata/models/content.py` — 기존 Content, ContentBatchJob
- `backend/api/programming/metadata/service.py` — Step 1 함수들
- `backend/alembic/versions/` — 마이그레이션 패턴

## 작업

### 1. ContentActionLog 모델 추가: `backend/api/programming/metadata/models/content.py`

```python
class ContentActionLog(Base):
    __tablename__ = "content_action_logs"
    
    action_id: str = Column(String, primary_key=True)  # UUID
    content_ids: List[int] = Column(JSON)  # target IDs
    action_type: str = Column(String)  # 'bulk_reprocess', 'bulk_enrich', ...
    before_state: Dict = Column(JSON)  # {id: {status, ...}}
    executed_at: datetime = Column(DateTime, default=utcnow)
    reverted_at: Optional[datetime] = Column(DateTime, nullable=True)
```

### 2. Alembic 마이그레이션: `backend/alembic/versions/{date}_add_content_action_log.py`

ContentActionLog 테이블 생성. 기존 데이터는 없으므로 downgrade 무시.

```bash
cd backend
alembic revision --autogenerate -m "Add ContentActionLog model"
# 또는 수동 작성
```

### 3. Service 함수 추가: `backend/api/programming/metadata/service.py`

```python
async def get_job_status(db: Session, job_id: str) -> JobStatusOut:
    """ContentBatchJob 조회 + progress_percent 계산."""

async def bulk_undo(db: Session, action_id: str) -> UndoActionOut:
    """
    24시간 이내만 가능.
    before_state 기반으로 각 content 상태를 역으로 복구.
    reverted_at 기록.
    """

async def retry_failed_in_job(db: Session, job_id: str) -> JobStatusOut:
    """
    ContentBatchJob의 failed items만 추출해서 새 job 생성.
    원본 상태로 복구 후 새 job 큐잉.
    """
```

### 4. Routes: `backend/api/programming/metadata/router.py`

```python
@router.get("/contents/jobs/{job_id}", response_model=JobStatusOut)
async def api_get_job_status(job_id: str, db: Session = Depends(get_db)):
    ...

@router.post("/bulk/undo", response_model=UndoActionOut)
async def api_bulk_undo(req: UndoActionRequest, db: Session = Depends(get_db)):
    ...

@router.post("/contents/jobs/{job_id}/retry-failed", response_model=BulkActionResponse)
async def api_retry_failed_in_job(job_id: str, db: Session = Depends(get_db)):
    ...
```

### 5. Retrofit Step 1: ContentActionLog 기록 추가

Step 1의 `bulk_reprocess()`, `bulk_enrich()`, `bulk_process()`, `bulk_recall()`, `bulk_delete()`에 아래 로직 추가:

```python
# before_state 캡처 (status만으로 충분)
before_state = {c.id: {"status": c.status} for c in contents}

# ContentBatchJob 생성 (기존)
job = ContentBatchJob(...)

# NEW: ContentActionLog 기록
action_log = ContentActionLog(
    action_id=job.id,
    content_ids=[c.id for c in contents],
    action_type="bulk_reprocess",  # or enrich, process, recall, delete
    before_state=before_state,
)
db.add(action_log)
db.commit()
```

### 6. 테스트: `backend/tests/api/programming/metadata/test_dev_api_consolidation_jobs.py`

- get_job_status: pending → queued → processing → completed 상태 변화 확인
- undo: 24시간 이내 undo 성공, 이후 실패
- retry_failed: 실패한 items만 새 job 생성

## Acceptance Criteria

```bash
cd backend
bash .claude/verify.sh dev-api-step2
# 또는
pytest tests/api/programming/metadata/test_dev_api_consolidation_jobs.py -v
alembic upgrade head  # 마이그레이션 성공 확인
```

## 금지사항

- Retrofit 시 Step 1 함수의 기존 로직 변경 금지 (ContentActionLog 기록만 추가)
- 24시간 경계값 테스트: 정확히 86400초 검증
- undo 후 action_log.reverted_at 설정 필수
