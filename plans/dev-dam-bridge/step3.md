# Step 3: dam-feedback-receiver

> GitHub: 미생성 | Milestone: dev-dam-bridge

## 읽어야 할 파일
- `backend/api/meta_core/public_api/router.py` (엔드포인트 추가 위치)
- `backend/alembic/versions/0009_drop_legacy_meta_columns.py` (마이그레이션 패턴)

## 목적
Dam이 자산↔작품 매핑 결과를 mediaX에 통보하는 수신 엔드포인트.
수신된 이벤트는 `dam_events` 테이블에 로그로 저장.

## 작업

### 1. `DamEvent` 모델 (`api/meta_core/public_api/schemas.py`에 스키마, 모델은 `tmdb_cache.py` 옆에 별도 파일)
새 파일: `api/meta_core/public_api/models.py`
```python
class DamEvent(Base):
    __tablename__ = "dam_events"
    id = PK
    event_type = String(50)   # asset_matched | asset_unlinked | asset_confirmed
    content_id = Integer (soft FK — Dam이 보내는 mediaX content_id)
    asset_id = String(200)    # Dam 측 자산 ID
    confidence = Float nullable
    match_method = String(50) nullable  # clip_similarity | ocr_text | manual | web_search
    confirmed = Boolean default False
    payload_json = JSON
    received_at = TIMESTAMP server_default now
```

### 2. Alembic 0010 — dam_events 테이블 생성

### 3. `public_api/schemas.py` — DamEventRequest Pydantic 스키마
```python
class DamEventRequest(BaseModel):
    event_type: str
    content_id: int
    asset_id: str
    confidence: Optional[float]
    match_method: Optional[str]
    confirmed: bool = False
    payload: Optional[dict]
```

### 4. `public_api/router.py` — POST /dam-events 엔드포인트
- `DamEventRequest` 파싱 → `DamEvent` 행 저장 → `{"accepted": true, "id": N}` 반환

### 5. `alembic/env.py` — DamEvent import 추가

## Acceptance Criteria
```bash
cd /home/ktalpha/Work/mediaX/backend
source .venv/bin/activate
DATABASE_URL=sqlite:///./media_ax_dev.db alembic upgrade head
python3 -c "
from api.meta_core.public_api.models import DamEvent
assert DamEvent.__tablename__ == 'dam_events'
from api.meta_core.public_api.router import router
paths = [r.path for r in router.routes]
assert '/dam-events' in paths, paths
print('ALL PASS')
"
```

## 금지사항
- content_id FK 제약 추가 금지 (Dam이 삭제된 content_id를 보낼 수도 있음 — soft FK)
- 인증 추가 금지 (내부망 신뢰, step4 이후 고려)
