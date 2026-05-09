# Step 1: content-export-api

> GitHub: 미생성 | Milestone: dev-dam-bridge

## 읽어야 할 파일
- `backend/api/meta_core/public_api/schemas.py` (ContentSummary — step0)
- `backend/api/meta_core/public_api/router.py` (엔드포인트 추가 위치)
- `backend/api/programming/metadata/models/content.py:79-80` (created_at/updated_at)

## 작업

### `public_api/router.py` 에 2개 엔드포인트 추가

#### `GET /contents/since`
- Query param: `ts: int = 0` (unix milliseconds, 0 = 전체)
- Filter: `COALESCE(updated_at, created_at) >= datetime.utcfromtimestamp(ts/1000)`
- 페이지: `limit: int = 500` (Dam 폴러 기본 배치)
- 정렬: `COALESCE(updated_at, created_at) ASC` → 결정론적 커서
- 응답: `ContentSummaryPage` — `next_ts = 마지막 항목 COALESCE(updated_at, created_at) millis + 1`
- ts=0이고 결과 없으면 `next_ts = now millis`

#### `GET /contents/{content_id}`
- Content 단건 조회
- 없으면 404

### DB 의존성
`get_db()` — `shared/database.py` 의 `SessionLocal` 패턴.

## Acceptance Criteria
```bash
cd /home/ktalpha/Work/mediaX/backend
source .venv/bin/activate
DATABASE_URL=sqlite:///./media_ax_dev.db python3 -c "
from api.meta_core.public_api.router import router
paths = [r.path for r in router.routes]
assert '/contents/since' in paths, paths
assert '/contents/{content_id}' in paths, paths
print('ALL PASS')
"
```

## 금지사항
- 페이지네이션 cursor 구현 금지 (ts 기반 단순 필터로 충분)
- 인증/권한 추가 금지 (내부 서비스 간 통신 — step3 이후 고려)
