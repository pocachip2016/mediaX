# backend/api/programming/metadata/ — 1.1 메타데이터 AI 모듈

## 파일 구성
| 파일 | 역할 |
|------|------|
| `models.py` | SQLAlchemy 모델 4개 |
| `schemas.py` | Pydantic 요청/응답 스키마 |
| `service.py` | 비즈니스 로직 (CRUD, 검수, 통계) |
| `router.py` | FastAPI 라우터 8개 엔드포인트 |
| `ai_engine.py` | Ollama 호출, KOBIS/TMDB 조회, 품질 스코어 |

## DB 모델
| 테이블 | 설명 |
|--------|------|
| `contents` | 콘텐츠 원본 (단편/시리즈/에피소드) |
| `content_metadata` | AI 처리 메타 + 품질 스코어 (0~100) |
| `cp_email_logs` | CP사 이메일 수신·엔티티 추출 이력 |
| `external_meta_cache` | KOBIS/TMDB API 캐시 |

## 품질 스코어 기준
| 점수 | 처리 |
|------|------|
| 90+ | `approved` 자동 등록 |
| 70~89 | `review` 담당자 검수 큐 |
| ~70 | `review` AI 보강 제안 |

## AI 엔진 (ai_engine.py)
- **모델:** Ollama `llama3.2:3b` (기본) → `OLLAMA_MODEL` 환경변수로 변경 가능
- **외부 API:** KOBIS + TMDB 병렬 비동기 조회 (`asyncio.gather`)
- **폴백:** API 키 없으면 `None` 반환, 점수만 낮아짐

## 주요 엔드포인트
```
GET  /api/programming/metadata/dashboard       # 오늘 통계
GET  /api/programming/metadata/contents        # 목록 (상태/CP 필터)
POST /api/programming/metadata/contents        # 수동 등록
POST /api/programming/metadata/contents/{id}/process  # AI 처리 트리거
GET  /api/programming/metadata/queue           # 검수 큐 (70~89점)
POST /api/programming/metadata/queue/{id}/action      # 승인/수정/반려
POST /api/programming/metadata/generate        # 실시간 메타 AI 생성
GET  /api/programming/metadata/emails          # CP 이메일 이력
```

## 알려진 주의사항
- `Content.children` 자기참조 관계: `remote_side="Content.id"` 필수
- SQLite 개발 시 `connect_args={"check_same_thread": False}` 자동 적용 (`shared/database.py`)
