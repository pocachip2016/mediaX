# backend/ — FastAPI 백엔드 루트

## 역할
MediaX 전체 REST API 서버. 6개 AX 모듈 + 공통 인프라 + 배포 API 제공.

## 진입점
- `main.py` — FastAPI 앱, CORS, 라우터 등록
- `Dockerfile` — uvicorn 실행
- `.env.example` → `.env` 복사 후 키 입력

## 디렉토리 구조
```
backend/
├── api/              ← 모듈별 라우터 (도메인 로직)
│   ├── programming/  ← 편성 기획 AX (1.1~1.5)
│   ├── design/       ← 디자인 AX
│   ├── ingest/       ← 인제스트 AX
│   ├── analytics/    ← 통계 AX
│   ├── marketing/    ← 마케팅 AX
│   ├── monitoring/   ← 모니터링 AX
│   ├── distribution/ ← 외부 배포
│   └── common/       ← 공통 인프라
├── shared/           ← 전역 설정·DB·미들웨어
├── workers/          ← Celery 워커 + 태스크
└── alembic/          ← DB 마이그레이션
```

## 실행
```bash
# 개발 (로컬 — SQLite 사용)
cd backend
# .env의 DATABASE_URL을 sqlite:///./media_ax_dev.db 로 설정
python3 -c "from shared.database import Base, engine; import api.programming.metadata.models; Base.metadata.create_all(engine)"
uvicorn main:app --port 8000

# 개발 (Docker PostgreSQL 사용)
docker compose up -d postgres redis ollama
# .env의 DATABASE_URL을 postgresql://media_ax:media_ax@localhost:5432/media_ax 로 설정
alembic upgrade head
uvicorn main:app --reload --port 8000

# Docker 전체
docker compose up
```

## API 문서
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health: http://localhost:8000/health

## 현재 .env 상태
- `DATABASE_URL`: SQLite (`media_ax_dev.db`) — 로컬 개발용
- Docker 운영 시 `.env.example`의 postgres/redis 호스트명으로 변경 필요
