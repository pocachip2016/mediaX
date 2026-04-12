# backend/api/programming/ — 편성 기획 AX API

## 모듈 구성
| 디렉토리 | 문서 | 상태 |
|---------|------|------|
| `metadata/` | 1.1 메타데이터 AI 자동 분류 | ✅ 구현 완료 |
| `catalog/` | 1.2 VOD 카탈로그 관리 | 🔜 예정 |
| `curation/` | 1.3 홈 큐레이션 AI | 🔜 예정 |
| `approval/` | 1.4 편성 결재·워크플로우 | 🔜 예정 |
| `cp_supply/` | 1.5 CP사 수급 관리 | 🔜 예정 |

## 라우터 등록
`router.py`에서 각 서브모듈 라우터를 prefix로 포함.
`main.py` → `/api/programming` prefix로 마운트.

## 1.1 metadata/ 파일 구성
| 파일 | 역할 |
|------|------|
| `models.py` | Content, ContentMetadata, CpEmailLog, ExternalMetaCache |
| `schemas.py` | Pydantic 요청/응답 스키마 |
| `service.py` | CRUD, 검수 액션, 대시보드 통계 |
| `router.py` | FastAPI 라우터 (8개 엔드포인트) |
| `ai_engine.py` | Ollama llama3.2:3b 호출, KOBIS/TMDB 조회, 품질 스코어 |

엔드포인트·DB 테이블 상세 → `metadata/CLAUDE.md` 참조
