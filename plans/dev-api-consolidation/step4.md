# Step 4: Content Detail — Advanced (changelog/lock/preview-clip) + ContentAuditLog

> GitHub: (미생성) | Milestone: dev-api-consolidation

## Context

Content 상세 페이지의 고급 기능 3가지를 구현하고, 필드 단위 변경 추적을 위해 ContentAuditLog를 신규 생성한다.
또한 Content 모델에 locked_fields 컬럼을 추가하고, Step 3의 함수들을 retrofit해서 locked_fields 체크를 추가한다.

## 읽어야 할 파일

- Step 0~3 완료 후: 스키마들, 기존 service/router
- `backend/api/programming/metadata/models/content.py` — Content, ContentAIResult
- `backend/alembic/versions/` — 마이그레이션 패턴

## 작업

### 1. Content 모델 수정: `backend/api/programming/metadata/models/content.py`

```python
class Content(Base):
    # ...기존 컬럼...
    locked_fields: List[str] = Column(JSON, default=list)  # ['synopsis', 'genre']
```

### 2. ContentAuditLog 모델 추가

```python
class ContentAuditLog(Base):
    __tablename__ = "content_audit_logs"
    
    id: int = Column(Integer, primary_key=True)
    content_id: int = Column(Integer, ForeignKey("contents.id"))
    field: str = Column(String)  # 'synopsis'
    old_value: str = Column(String, nullable=True)  # JSON 문자열
    new_value: str = Column(String, nullable=True)  # JSON 문자열
    source: str = Column(String)  # 'promote_ai', 'apply_external', 'lock_fields', ...
    actor: str = Column(String, nullable=True)  # user ID or system
    at: datetime = Column(DateTime, default=utcnow)
```

### 3. Alembic 마이그레이션: `backend/alembic/versions/{date}_add_audit_log_and_locked_fields.py`

- Content 테이블에 locked_fields column 추가
- content_audit_logs 테이블 생성

### 4. Service 함수: `backend/api/programming/metadata/service.py`

```python
async def get_changelog(db: Session, content_id: int) -> ContentChangelogOut:
    """ContentAuditLog 조회 및 시간순 정렬."""

async def lock_fields(db: Session, content_id: int, fields: List[str], reason: Optional[str] = None):
    """
    Content.locked_fields 업데이트.
    각 field마다 ContentAuditLog 기록 (source='lock_fields').
    """

async def request_preview_clip(db: Session, content_id: int) -> Dict:
    """
    Celery task 큐잉 (generate_preview_clip stub).
    Content.preview_clip_status = 'queued' 설정.
    job_id 반환.
    """

def _record_audit_log(db, content_id, field, old, new, source):
    """Helper: ContentAuditLog 기록."""
```

### 5. Routes: `backend/api/programming/metadata/router.py`

```python
@router.get("/contents/{id}/changelog", response_model=ContentChangelogOut)
async def api_get_changelog(id: int, db: Session = Depends(get_db)):
    ...

@router.post("/contents/{id}/lock")
async def api_lock_fields(id: int, req: LockFieldsRequest, db: Session = Depends(get_db)):
    ...

@router.post("/contents/{id}/preview-clip")
async def api_request_preview_clip(id: int, db: Session = Depends(get_db)):
    ...
```

### 6. Celery Task (Stub): `backend/workers/metadata_tasks.py`

```python
@shared_task
def generate_preview_clip(content_id: int):
    """
    Stub implementation.
    실제 ffmpeg 처리는 dev-preview-clip 별도 task에서.
    여기서는 task 큐잉만 — content.preview_clip_status = 'processing'으로 업데이트.
    """
    pass
```

### 7. Retrofit Step 3

partial_reprocess(), apply_external_fields()에 locked_fields 체크 추가:

```python
async def partial_reprocess(...):
    # ...
    locked = set(content.locked_fields or [])
    fields = [f for f in fields if f not in locked]  # 필터링
    # ...

async def apply_external_fields(...):
    locked = set(content.locked_fields or [])
    fields = [f for f in fields if f not in locked]
    # ...
```

promote_ai_result()에도 ContentAuditLog 기록 추가:

```python
async def promote_ai_result(...):
    # ...
    _record_audit_log(db, content_id, 'is_final', old_result_id, ai_result_id, 'promote_ai')
```

### 8. 테스트: `backend/tests/api/programming/metadata/test_dev_api_consolidation_detail_advanced.py`

- get_changelog: 변경 이력 조회
- lock_fields: 필드 잠금 + audit log 기록
- request_preview_clip: task 큐잉 + status='queued' 확인
- locked_fields 필터링: partial_reprocess/apply_external_fields에서 locked 필드 제외 확인

## Acceptance Criteria

```bash
cd backend
bash .claude/verify.sh dev-api-step4
# 또는
pytest tests/api/programming/metadata/test_dev_api_consolidation_detail_advanced.py -v
alembic upgrade head
```

## 금지사항

- preview-clip은 stub만. 실제 ffmpeg 호출은 dev-preview-clip task에서
- locked_fields는 in-memory 처리 (DB 저장O, 별도 API 없음)
- audit log는 모든 필드 단위 변경 시 자동 기록 필수
