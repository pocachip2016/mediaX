# Step 2: content-changefeed

> GitHub: 미생성 | Milestone: dev-dam-bridge

## 읽어야 할 파일
- `backend/api/meta_core/public_api/router.py` (step1 완성)
- `backend/workers/tasks/metadata.py` (태스크 추가 위치)
- `backend/main.py` (lifespan / startup에 changefeed 등록)

## 목적
Content INSERT/UPDATE/DELETE 발생 시 Dam에 HTTP POST 발신.
Dam은 이 webhook을 받거나 `/contents/since` 폴링 중 하나를 사용.

## 설계
- SQLAlchemy mapper 이벤트 (`after_insert`, `after_update`, `after_delete`) → Celery 태스크 `send_dam_webhook.delay(..., countdown=2)`
- Celery 태스크: `DAM_WEBHOOK_URL` 미설정 시 graceful skip
- 이벤트 등록: `api/meta_core/public_api/changefeed.py` → `setup_changefeed_events()` 함수, `main.py` startup에서 1회 호출

## Payload
```json
{
  "event": "insert | update | delete",
  "content_id": 123,
  "title": "...",
  "content_type": "movie",
  "occurred_at": "ISO8601 UTC"
}
```

## 작업

### 1. `api/meta_core/public_api/changefeed.py` 신설
```python
def setup_changefeed_events():
    from sqlalchemy import event
    from api.programming.metadata.models.content import Content

    @event.listens_for(Content, "after_insert")
    def _insert(mapper, connection, target): ...

    @event.listens_for(Content, "after_update")
    def _update(mapper, connection, target): ...

    @event.listens_for(Content, "after_delete")
    def _delete(mapper, connection, target): ...
```
각 이벤트는 `send_dam_webhook.delay(event_type, target.id, target.title, ..., countdown=2)` 호출.

### 2. `workers/tasks/metadata.py` 에 `send_dam_webhook` 태스크 추가
```python
@celery_app.task(name="workers.tasks.metadata.send_dam_webhook")
def send_dam_webhook(event_type, content_id, title, content_type, occurred_at):
    url = getattr(settings, "DAM_WEBHOOK_URL", "")
    if not url: return {"skipped": True}
    httpx.post(url, json={...}, timeout=5.0)
```

### 3. `main.py` lifespan에 `setup_changefeed_events()` 호출

## Acceptance Criteria
```bash
cd /home/ktalpha/Work/mediaX/backend
source .venv/bin/activate
DATABASE_URL=sqlite:///./media_ax_dev.db python3 -c "
from api.meta_core.public_api.changefeed import setup_changefeed_events
setup_changefeed_events()
from workers.tasks.metadata import send_dam_webhook
import inspect
assert 'event_type' in inspect.signature(send_dam_webhook.run if hasattr(send_dam_webhook,'run') else send_dam_webhook).parameters
print('ALL PASS')
"
```

## 금지사항
- mapper 이벤트 내에서 직접 httpx.post 금지 (동기 블로킹 → 트랜잭션 지연)
- `DAM_WEBHOOK_URL` 없을 때 예외 발생 금지
