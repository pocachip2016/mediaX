# mediaX — KT 지니TV VOD AI Transformation Platform

## 프로젝트 구조
```
mediaX/
├── backend/          # FastAPI + Celery (Python)
├── mediaX-CMS/       # Next.js 16 Turbo 모노레포 (프론트엔드)
├── docs/             # 설계 문서 (60개+)
├── docker-compose.yml
└── CLAUDE.md
```

## 빠른 시작

### 로컬 개발 (Docker 없이)
```bash
# 백엔드
cd backend
# .env: DATABASE_URL=sqlite:///./media_ax_dev.db
python3 -c "from shared.database import Base, engine; import api.programming.metadata.models; Base.metadata.create_all(engine)"
uvicorn main:app --port 8000
# → http://localhost:8000/docs

# 프론트엔드 (별도 터미널)
cd mediaX-CMS
nvm use 22
npm run dev
# → http://localhost:3000 (또는 3002)
```

### Docker 전체 실행
```bash
cp backend/.env.example backend/.env  # 키 입력 후
docker compose up -d postgres redis ollama
# llama3.2:3b 최초 다운로드 (약 2GB)
docker exec -it mediax-ollama-1 ollama pull llama3.2:3b
# .env: DATABASE_URL=postgresql://media_ax:media_ax@localhost:5432/media_ax
cd backend && alembic upgrade head
docker compose up
```

## 구현 현황
| 모듈 | 백엔드 | 프론트엔드 |
|------|--------|-----------|
| 1.1 메타데이터 AI | ✅ | ✅ |
| 1.2 카탈로그 | 스텁 | 스텁 |
| 1.3 큐레이션 | 스텁 | 스텁 |
| 1.4 결재 워크플로우 | 스텁 | 스텁 |
| 1.5 CP 수급 관리 | 스텁 | 스텁 |

## 주요 포트
| 서비스 | 포트 |
|--------|------|
| FastAPI | 8000 |
| Next.js | 3000 (또는 3002) |
| PostgreSQL | 5432 |
| Redis | 6379 |
| Ollama | 11434 |
| Elasticsearch | 9200 |

## 각 디렉토리 CLAUDE.md
- [docs/CLAUDE.md](docs/CLAUDE.md)
- [mediaX-CMS/CLAUDE.md](mediaX-CMS/CLAUDE.md)
- [backend/CLAUDE.md](backend/CLAUDE.md)
- [backend/api/CLAUDE.md](backend/api/CLAUDE.md)
- [backend/api/programming/CLAUDE.md](backend/api/programming/CLAUDE.md)
- [backend/api/programming/metadata/CLAUDE.md](backend/api/programming/metadata/CLAUDE.md)
- [backend/shared/CLAUDE.md](backend/shared/CLAUDE.md)
- [backend/workers/CLAUDE.md](backend/workers/CLAUDE.md)
- [backend/alembic/CLAUDE.md](backend/alembic/CLAUDE.md)
- [mediaX-CMS/apps/web/CLAUDE.md](mediaX-CMS/apps/web/CLAUDE.md)
- [mediaX-CMS/apps/web/lib/CLAUDE.md](mediaX-CMS/apps/web/lib/CLAUDE.md)
- [mediaX-CMS/apps/web/components/CLAUDE.md](mediaX-CMS/apps/web/components/CLAUDE.md)
