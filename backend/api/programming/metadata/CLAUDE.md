# backend/api/programming/metadata/ — 1.1 메타데이터 AI 모듈

## 파일 구성
| 파일 | 역할 |
|------|------|
| `models/` | SQLAlchemy 모델 패키지 (도메인별 분리) |
| `models/content.py` | Content, ContentMetadata, CpEmailLog |
| `models/taxonomy.py` | GenreCode, TagCode, ContentGenre, ContentTag |
| `models/person.py` | PersonMaster, ContentCredit |
| `models/image.py` | ContentImage |
| `models/external.py` | ExternalMetaSource, ContentAIResult |
| `models/__init__.py` | 모든 모델 re-export (하위호환) |
| `schemas.py` | Pydantic 요청/응답 스키마 |
| `service.py` | 비즈니스 로직 (CRUD, 검수, 통계) |
| `router.py` | FastAPI 라우터 8개 엔드포인트 |
| `ai_engine.py` | Ollama 호출, KOBIS/TMDB 조회, 품질 스코어 |

## DB 모델 (총 14개 테이블)
### 핵심 (0001 마이그레이션)
| 테이블 | 설명 |
|--------|------|
| `contents` | 콘텐츠 원본 (movie/series/season/episode 계층) |
| `content_metadata` | AI 처리 메타 + 품질 스코어 (0~100) |
| `cp_email_logs` | CP사 이메일 수신·엔티티 추출 이력 |
| `external_meta_cache` | KOBIS/TMDB API 캐시 (레거시) |

### 확장 (0002 마이그레이션)
| 테이블 | 설명 |
|--------|------|
| `genre_codes` | 장르 마스터 — 대분류/소분류 계층, 지니TV 표준 20개 기본 시딩 |
| `tag_codes` | 태그 마스터 (mood/theme/keyword/ai) |
| `content_genres` | 콘텐츠-장르 M:N (is_primary, source) |
| `content_tags` | 콘텐츠-태그 M:N (confidence_score) |
| `person_master` | 인물 마스터 — TMDB/KOBIS 연결, 중복 병합(canonical_id) |
| `content_credits` | 콘텐츠-인물 관계 (role, character_name, cast_order) |
| `content_images` | 이미지 (poster/thumbnail/stillcut/banner/logo) |
| `external_meta_sources` | 외부 시스템 원본 메타 — content_id FK 명시적 연결 |
| `content_ai_results` | AI 결과 엔진별·태스크별 저장 (is_final 플래그) |

### 파이프라인 확장 (0003 마이그레이션)
| 테이블 | 설명 |
|--------|------|
| `content_batch_jobs` | CSV/Excel 배치 업로드 이력 (status: pending/parsing/processing/done/failed) |

### ContentStatus 흐름
```
waiting → processing → staging → approved
                              ↘ rejected
          (review: 70~89점 AI 처리 후 검수 큐)
```
- `staging` = 에이전틱 검색(TMDB+KOBIS) 완료, 운영자 검토 대기

## 품질 스코어 기준
| 점수 | 처리 |
|------|------|
| 90+ | `approved` 자동 등록 |
| 70~89 | `review` 담당자 검수 큐 |
| ~70 | `review` AI 보강 제안 |

## AI 엔진 (ai_engine.py + llm/ 패키지)
- **멀티 프로바이더:** `AI_ENGINE` 환경변수로 엔진 선택 (`gemini` | `groq` | `ollama`)
- **폴백 체인:** 지정 엔진 실패 → 나머지 엔진 순서대로 자동 시도
- **기본값:** `gemini` → `gemini-2.0-flash-lite`
- **Groq:** `llama-3.3-70b-versatile` (무료 30 RPM)
- **Ollama:** `llama3.2:3b` 로컬 (Docker 필요)
- **외부 API:** KOBIS + TMDB 병렬 비동기 조회 (`asyncio.gather`)
- **AI 결과 기록:** 처리 후 `ContentAIResult` 테이블에 엔진명 + is_final 기록

### llm/ 패키지 구조
| 파일 | 역할 |
|------|------|
| `base.py` | `AbstractLLMProvider` 추상 클래스 |
| `gemini.py` | `GeminiProvider` — google-genai SDK |
| `groq.py` | `GroqProvider` — groq SDK |
| `ollama.py` | `OllamaProvider` — httpx 직접 호출 |
| `__init__.py` | `get_provider_chain()` 팩토리 |

### 키 발급 링크
- Gemini: https://aistudio.google.com/app/apikey
- Groq: https://console.groq.com/keys

## 주요 엔드포인트 (총 25개)
```
GET  /api/programming/metadata/dashboard              # 오늘 통계
GET  /api/programming/metadata/contents               # 목록 — 필터: status, cp_name(ilike), title(ilike), content_type, production_year
POST /api/programming/metadata/contents               # 수동 등록
GET  /api/programming/metadata/contents/{id}          # 상세
POST /api/programming/metadata/contents/{id}/process  # AI 처리 트리거
GET  /api/programming/metadata/contents/{id}/hierarchy # 시리즈 계층 트리 (StagingItem 재귀)
POST /api/programming/metadata/contents/{id}/enrich   # 에이전틱 검색 수동 트리거
GET  /api/programming/metadata/queue                  # 검수 큐 (70~89점)
POST /api/programming/metadata/queue/{id}/action      # 승인/수정/반려
POST /api/programming/metadata/generate               # 실시간 메타 AI 생성
GET  /api/programming/metadata/emails                 # CP 이메일 이력
GET  /api/programming/metadata/staging                # 검토 대기풀 (staging 상태)
POST /api/programming/metadata/staging/bulk-approve   # 벌크 승인
POST /api/programming/metadata/staging/bulk-reject    # 벌크 반려
GET  /api/programming/metadata/pipeline/status        # 파이프라인 현황
POST /api/programming/metadata/upload/batch           # CSV/Excel 배치 업로드
GET  /api/programming/metadata/upload/batch/{job_id}  # 배치 작업 상태 조회

# 메타 3분류 (글자/이미지/영상)
GET  /api/programming/metadata/text                   # 글자메타 목록
GET  /api/programming/metadata/text/{id}              # 글자메타 상세
PUT  /api/programming/metadata/text/{id}              # 글자메타 수정 (synopsis/genre/tags/completed)
POST /api/programming/metadata/text/bulk-complete     # 글자메타 일괄 완료
GET  /api/programming/metadata/image                  # 이미지메타 목록
GET  /api/programming/metadata/image/{id}             # 이미지메타 상세 (ContentImageOut[] 포함)
GET  /api/programming/metadata/video                  # 영상메타 목록
GET  /api/programming/metadata/video/{id}             # 영상메타 상세
PUT  /api/programming/metadata/video/{id}             # 영상메타 수정
POST /api/programming/metadata/video/bulk-complete    # 영상메타 일괄 완료
GET  /api/programming/metadata/service-readiness      # 글자+이미지+영상 완료 통계
GET  /api/programming/metadata/tmdb                   # TMDB 매핑 콘텐츠 목록 — 필터: content_type, search(ilike)
```

## 알려진 주의사항
- `Content.children` 자기참조 관계: `remote_side="Content.id"` 필수
- SQLite 개발 시 `connect_args={"check_same_thread": False}` 자동 적용 (`shared/database.py`)
- `ExternalMetaSource`에는 `fetched_at` 없음 → `matched_at` 사용 (schemas, service, workers 모두 동일)
- `PersonMaster` 인물명 필드는 `name_ko` / `name_en` — `name` 컬럼 없음
