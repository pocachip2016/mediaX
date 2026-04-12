# backend/api/ — AX 모듈별 API

## 구조
각 AX 모듈은 독립 디렉토리로 분리. `main.py`에서 `/api/{모듈}` prefix로 마운트.

| 디렉토리 | prefix | 상태 |
|---------|--------|------|
| `programming/` | `/api/programming` | ✅ 1.1 metadata 구현 완료 |
| `design/` | `/api/design` | 스텁 |
| `ingest/` | `/api/ingest` | 스텁 |
| `analytics/` | `/api/analytics` | 스텁 |
| `marketing/` | `/api/marketing` | 스텁 |
| `monitoring/` | `/api/monitoring` | 스텁 |
| `distribution/` | `/api/distribution` | 스텁 |
| `common/` | `/api/common` | 스텁 |

## 모듈 추가 패턴
새 모듈 추가 시 아래 파일 세트 생성:
```
api/{module}/
├── __init__.py
├── router.py     # APIRouter 정의
├── models.py     # SQLAlchemy 모델
├── schemas.py    # Pydantic 스키마
├── service.py    # 비즈니스 로직
└── CLAUDE.md     # 이 문서 형식 참고
```
`main.py`에 `include_router()` 추가.
`alembic/env.py`에 모델 import 추가.
