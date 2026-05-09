# Step 0: public-api-module

> GitHub: 미생성 | Milestone: dev-dam-bridge

## 읽어야 할 파일
- `backend/api/meta_core/router.py` (현재 빈 라우터 — 확장 위치)
- `backend/api/meta_core/models/__init__.py` (re-export 목록)

## 목적
Dam 폴러/webhook 연동의 기반이 되는 `meta_core/public_api/` 서브모듈 신설.
실제 엔드포인트 구현은 step1(내보내기), step2(changefeed), step3(피드백 수신)에서 순차 추가.
이 step은 **모듈 골격 + ContentSummary 스키마** 만 만든다.

## 작업

### 1. `api/meta_core/public_api/__init__.py` — 패키지 마커

### 2. `api/meta_core/public_api/schemas.py` — Dam이 소비하는 Pydantic 스키마

```python
class ContentSummary(BaseModel):
    content_id: int
    title: str
    original_title: Optional[str]
    content_type: str          # movie | series | season | episode
    production_year: Optional[int]
    status: str
    updated_at: datetime

class ContentSummaryPage(BaseModel):
    items: list[ContentSummary]
    next_ts: Optional[int]     # 다음 폴링용 unix timestamp (millis)
    total: int
```

### 3. `api/meta_core/public_api/router.py` — 빈 APIRouter + 스텁 헬스체크

```python
router = APIRouter()

@router.get("/health")
def meta_core_health():
    return {"status": "ok", "module": "meta_core_public_api"}
```

### 4. `api/meta_core/router.py` — public_api 라우터 마운트
```python
from api.meta_core.public_api.router import router as public_api_router
router.include_router(public_api_router)
```

## Acceptance Criteria
```bash
cd /home/ktalpha/Work/mediaX/backend
source .venv/bin/activate
python3 -c "
from api.meta_core.public_api.schemas import ContentSummary, ContentSummaryPage
from api.meta_core.public_api.router import router
assert any(r.path == '/health' for r in router.routes)
print('ALL PASS')
"
```

## 금지사항
- 실제 DB 쿼리 없음 — 이 step은 골격만
- main.py 라우터 등록 변경 없음 (이미 step1에서 `/api/meta-core` prefix로 등록됨)
