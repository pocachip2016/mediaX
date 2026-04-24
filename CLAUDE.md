@../CLAUDE.md

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
| 모듈 | 백엔드 | 프론트엔드 | 주요 기능 |
|------|--------|-----------|-----------|
| 1.1 메타데이터 AI — 기반 | ✅ | ✅ | 14개 테이블, 26개 API, Gemini LLM 폴백 체인 |
| 1.1 파이프라인 자동화 | ✅ | ✅ | staging 상태, 에이전틱 TMDB 검색, Beat 6개, staging/upload/monitoring 화면 |
| 1.1 TMDB 동기화 | ✅ | ✅ | sync_tmdb Beat 매일 02:00, TMDB 탐색 목록 페이지 |
| 1.2 카탈로그 | 스텁 | 스텁 | |
| 1.3 큐레이션 | 스텁 | 스텁 | |
| 1.4 결재 워크플로우 | 스텁 | 스텁 | |
| 1.5 CP 수급 관리 | 스텁 | 스텁 | |

## 주요 포트
| 서비스 | 포트 |
|--------|------|
| FastAPI | 8000 |
| Next.js | 3000 (또는 3002) |
| PostgreSQL | 5432 |
| Redis | 6379 |
| Ollama | 11434 |
| Elasticsearch | 9200 |

## Claude 자동 행동 규칙 (매 세션 항상 적용)

### 파일 읽기
- 100줄 이상 파일: Read 전 Grep으로 함수명·줄번호 확인 후 offset+limit 사용
- 전체 파일 Read 금지 (50줄 이하 또는 신규 파일 예외)
- 대형 파일 탐색 패턴: `Grep "^def "` → 줄번호 → 필요한 함수만 읽기

### 세션 진입
- plans/{모듈}.md 존재 시 반드시 먼저 읽고 시작 (docs/ 전체 탐색 금지)
- 선언한 세션 범위 외 파일 수정 금지
- Explore 에이전트 3회 이상 호출 후에는 /compact 제안

### 완료 보고
- "완료" 보고 전 pytest 또는 `python3 -c "from X import Y; print('OK')"` 실행 필수
- plan 체크박스 + docs/9_todo/9.0_todo.md 갱신이 완료 처리의 일부

### CLAUDE.md 관리
- 각 CLAUDE.md 60줄 이하 유지
- 추가 전 자문: "코드에서 확인 가능한가?" → 가능하면 추가 금지
- 엔드포인트 목록·테이블 컬럼 상세·파일 트리는 CLAUDE.md에 쓰지 않음

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
