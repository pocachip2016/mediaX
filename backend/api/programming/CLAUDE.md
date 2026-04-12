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

## 주요 API
| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/api/programming/metadata/dashboard` | 오늘 통계 |
| GET | `/api/programming/metadata/contents` | 목록 (상태·CP 필터) |
| POST | `/api/programming/metadata/contents` | 수동 등록 |
| POST | `/api/programming/metadata/contents/{id}/process` | AI 처리 트리거 |
| GET | `/api/programming/metadata/queue` | 검수 큐 (70~89점) |
| POST | `/api/programming/metadata/queue/{id}/action` | 승인/수정/반려 |
| POST | `/api/programming/metadata/generate` | 실시간 메타 생성 |
| GET | `/api/programming/metadata/emails` | CP 이메일 이력 |

## DB 테이블
- `contents` — 콘텐츠 원본
- `content_metadata` — AI 처리 메타 + 품질 스코어
- `cp_email_logs` — CP 이메일 수신 이력
- `external_meta_cache` — KOBIS/TMDB 캐시
