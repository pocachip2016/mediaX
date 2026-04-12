# backend/shared/ — 전역 공유 모듈

## 파일
| 파일 | 역할 |
|------|------|
| `config.py` | `Settings` (pydantic-settings) — 환경변수 전체 관리 |
| `database.py` | SQLAlchemy 엔진·세션·`Base`·`get_db` DI |
| `middleware/` | 인증·로깅·레이트리밋 미들웨어 |
| `schemas/` | 공통 Pydantic 스키마 (페이지네이션, 에러 응답 등) |

## 환경변수 (config.py)
| 키 | 기본값 | 설명 |
|----|--------|------|
| `DATABASE_URL` | postgresql://... | PostgreSQL 연결 |
| `REDIS_URL` | redis://... | Redis (Celery broker) |
| `OLLAMA_URL` | http://localhost:11434 | Ollama API |
| `OLLAMA_MODEL` | llama3.2:3b | 기본 LLM 모델 |
| `IMAP_HOST/USER/PASS` | — | CP 이메일 폴링 |
| `TMDB_API_KEY` | — | TMDB 외부 메타 |
| `KOBIS_API_KEY` | — | 영진위 KOBIS |
| `ANTHROPIC_API_KEY` | — | Claude API (Phase 2) |

## 주의
- 모든 API 모듈은 `from shared.database import get_db`를 DI로 사용
- 새 모델 추가 시 `alembic/env.py`에 import 추가 필수
