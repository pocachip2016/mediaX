@../CLAUDE.md

# mediaX — VOD AI Transformation Platform

## 프로젝트 구조
```
mediaX/
├── backend/          # FastAPI + Celery (Python)
├── mediaX-CMS/       # Next.js 16 Turbo 모노레포 (프론트엔드)
├── docs/             # 설계 문서 (60개+)
└── docker-compose.yml
```

## 빠른 시작
서비스는 docker compose로 통일 운영. 로컬 uvicorn 직접 실행 금지.

```bash
cp backend/.env.example backend/.env  # 키 입력 후
docker compose up -d postgres redis ollama
docker exec -it mediax-ollama-1 ollama pull llama3.2:3b  # 최초 1회 (~2GB)
cd backend && alembic upgrade head
docker compose up
```

프론트엔드 별도 dev: `cd mediaX-CMS && nvm use 22 && npm run dev` (→ http://localhost:3000)

## 구현 현황
| 모듈 | 백엔드 | 프론트엔드 | 주요 기능 |
|------|--------|-----------|-----------|
| 1.1 메타데이터 AI — 기반 | ✅ | ✅ | 14개 테이블, 26개 API, Gemini LLM 폴백 체인 |
| 1.1 파이프라인 자동화 | ✅ | ✅ | staging 상태, 에이전틱 TMDB 검색, Beat 6개 |
| 1.1 TMDB 동기화 | ✅ | ✅ | sync_tmdb Beat 매일 02:00 |
| dev-poster-recommend | ✅ | ✅ | 다중 포스터 후보 추천(TMDB /images) + 운영자 primary 선택 UI |
| dev-meta-intelligence Phase D | ✅ | ✅ | WebSearch 4 provider 폴백 체인(Brave/SerpAPI/Gemini/Ollama) + QuotaManager + BulkGuard + /monitoring/web-search UI |
| dev-ai-review-queue | ✅ | ✅ | 통합 검수 흐름 — Review Queue 리스트 + MetadataDiffPanel + MetadataEnrichPanel + VisualAssetCandidatePanel + Dam Link Display |
| content-register | ✅ | ✅ | 신규 VOD 등록 — Hero card(포스터+10필드) + 3탭 패널(글자/이미지/영상) + enrich 자동 활성 |
| dev-dam-poster-ingest | ✅ | — | Dam poster 자동 등록 파이프라인 — webhook 확장 + Beat catch-up |
| dev-kmdb-cache | ✅ | — | kmdb_movie_cache 테이블 + _upsert_kmdb_movie + discover_kmdb 캐시 통합 + backfill_kmdb Beat 06:00 KST + enrich 캐시 우선 조회 |
| dev-meta-hierarchy Phase A~E | ✅ | ✅ | 영화/시리즈/시즌/에피소드 content_kind SSOT + read-time 상속(year/country/synopsis/genre/poster) + FE 검색/3탭/추천 조건부 라우팅. ADR-001 + 38 테스트 pass |
| 1.2 카탈로그 | 스텁 | 스텁 | |
| 1.3 큐레이션 | 스텁 | 스텁 | |
| 1.4 결재 워크플로우 | 스텁 | 스텁 | |
| 1.5 CP 수급 관리 | 스텁 | 스텁 | |
| dev-service-distribution | 미착수 | 미착수 | ContentDistribution(IPTV/OTT) + ServiceCategory + DeviceVariant |

## 주요 포트
FastAPI 8000 · Next.js 3000 · Postgres 5432 · Redis 6379 · Ollama 11434 · Elasticsearch 9200

## Where to look
- 상세 TODO: `@TODO.md`
- 설계 문서 인덱스: `docs/CLAUDE.md` (디렉토리 진입 시 자동 로드)
- 진행 중 plan: `@plans/` (`plans/dev-<slug>/` 만 dev task)
