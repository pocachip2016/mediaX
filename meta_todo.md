# Metadata 영역 구현 현황 & 잔여 과제

작성일: 2026-04-16
기준: `mediaX-CMS/apps/web/app/research.md` + 실측 조사(프론트 11개 페이지 + 백엔드 router/service/workers/llm)

---

## 1. 구현 현황

### 1.1 프론트엔드 (총 11개 페이지 / 3,719 라인)

| 페이지 | 라인 | API 연동 | 상태 |
|---|---:|:---:|---|
| `/programming/metadata` (Dashboard) | 397 | ✅ 4 API | KPI·파이프라인·최근 콘텐츠·서비스 준비도 완전 구현 |
| `/programming/metadata/staging` | 551 | ✅ getStaging, bulkApprove | CP↔AI diff, 벌크 승인/반려, 계층 트리 완성 |
| `/programming/metadata/upload` | 312 | ✅ submitBatch | CSV 드래그&드롭 + 미리보기 완성 |
| `/programming/metadata/queue` | 296 | ✅ getQueue, reviewAction | 70~89점 검수 큐 + 5개 점수 분석 완성 |
| `/programming/metadata/create` | 282 | ✅ generate, createContent | 실시간 AI 메타 생성 (300ms 디바운스) |
| `/programming/metadata/text` | 481 | ✅ textMetaApi | 시리즈-시즌-에피소드 트리 편집 |
| `/programming/metadata/text/review` | 319 | ✅ textMetaApi | 미완료 필터 + 벌크 승인 |
| `/programming/metadata/image` | 264 | ✅ imageMetaApi.list | 5종 타입별 완료 현황 표시 |
| `/programming/metadata/image/upload` | 211 | ⚠️ 부분 | 파일 선택 UI만, **실제 업로드는 1s Mock** |
| `/programming/metadata/video` | 380 | ✅ videoMetaApi | 해상도/코덱/비트레이트 편집 |
| `/programming/metadata/video/qc` | 226 | ✅ videoMetaApi | 미완료 QC 벌크 완료 |

### 1.2 백엔드 (라우터 25개, 모델 20개, Beat 6개)

**완전 구현 (✅)**
- **Router** `backend/api/programming/metadata/router.py` — CRUD/검수 큐/Staging/배치/메타3분류/service-readiness/TMDB 등 25개 엔드포인트
- **Service** `service.py` — `get_staging_queue`, `bulk_approve_staging`, `process_batch_rows`(CSV/Excel 파싱+Content 생성), `get_text_meta_list`(계층 재귀), `get_service_readiness` 등 비즈니스 로직 100%
- **LLM 체인** `llm/` — Gemini / Groq / Ollama 3개 프로바이더 + `get_provider_chain()` 폴백
- **Beat 태스크** `workers/tasks/metadata.py` — `poll_cp_emails`(5m), `sync_kobis`(매일 03:00), `sync_tmdb`(매일 02:00), `enrich_content_metadata`(TMDB 시리즈 재귀→시즌/에피소드 자동 생성)

**부분 구현 (⚠️)**
- `reeval_quality_scores`(매일 01:00) — review 상태만 재처리 큐 등록
- `check_missing_episodes`(매일 04:00) — Beat 스케줄 선언 존재, 실동작 확인 필요
- `retry_failed_enrichments`(6h) — Beat 스케줄 선언 존재, 실동작 확인 필요

**종합 평가**: 수신→AI 처리→Staging→검수→승인 워크플로우가 End-to-End로 연결된 **프로덕션 레디 상태**.

---

## 2. 진행해야 할 작업 (TODO)

### A. 기능 공백 메우기 (Priority 1)

- [ ] **A-1. 이미지 업로드 실연동**
  - Front: `mediaX-CMS/apps/web/app/(main)/programming/metadata/image/upload/page.tsx` — Mock 1초 지연 로직을 실제 업로드로 교체
  - Back: `POST /api/programming/metadata/image/upload` 신설 (저장소 업로드 + `ContentImage` 레코드 생성)
  - 수정 파일: `backend/api/programming/metadata/router.py`, `service.py`

- [ ] **A-2. Excel(xlsx) 파싱 지원**
  - Back: `service.py::process_batch_rows`에 `openpyxl` 기반 xlsx 경로 추가
  - Front: `/metadata/upload` 파싱 로직에서 xlsx 분기 처리

- [ ] **A-3. Dashboard 자동 새로고침 (30s)**
  - Front: `/metadata/page.tsx`에 `setInterval` 주기 갱신 — `/monitoring/pipeline/page.tsx` 패턴 재사용

### B. Beat 태스크 완성도 확인 (Priority 2)

- [ ] **B-4. `check_missing_episodes`, `retry_failed_enrichments` 태스크 코드 존재 여부 검증**
  - 대상: `backend/workers/tasks/metadata.py`, `backend/workers/celery_app.py`
  - 미구현 시 실장

### C. 시각화 보강 (Priority 3)

- [ ] **C-5. TMDB/KOBIS 매칭 시각화**
  - Front: `/metadata/create`에서 외부 소스 매칭 결과(포스터 썸네일·신뢰도) UI 노출
  - 백엔드 응답에 이미 포함되어 있으나 프론트 미표시

- [ ] **C-6. `ContentAIResult` 조회 API 신설 검토**
  - `GET /api/programming/metadata/contents/{id}/ai-results` — 엔진별 AI 결과 이력

### D. 문서 동기화 (Priority 4)

- [ ] **D-7. `backend/api/programming/CLAUDE.md` 업데이트**
  - metadata 파일 구성표가 구버전 (`models.py` 단일 파일로 표기 / 실제는 `models/` 패키지 + `llm/` 폴더)

- [ ] **D-8. `backend/api/programming/metadata/CLAUDE.md` 갱신**
  - "FastAPI 라우터 8개 엔드포인트" → 실제 25개로 수정

---

## 3. 수정 대상 파일 매트릭스

| 파일 | 작업 |
|---|---|
| `mediaX-CMS/apps/web/app/(main)/programming/metadata/image/upload/page.tsx` | A-1 |
| `backend/api/programming/metadata/router.py` | A-1, C-6 |
| `backend/api/programming/metadata/service.py` | A-1, A-2 |
| `mediaX-CMS/apps/web/app/(main)/programming/metadata/upload/page.tsx` | A-2 |
| `mediaX-CMS/apps/web/app/(main)/programming/metadata/page.tsx` | A-3 |
| `backend/workers/tasks/metadata.py` | B-4 |
| `backend/workers/celery_app.py` | B-4 |
| `mediaX-CMS/apps/web/app/(main)/programming/metadata/create/page.tsx` | C-5 |
| `backend/api/programming/CLAUDE.md` | D-7 |
| `backend/api/programming/metadata/CLAUDE.md` | D-8 |

재사용 기존 유틸:
- 30초 자동 갱신 패턴 → `/monitoring/pipeline/page.tsx` (`setInterval(fetch, 30_000)`)
- Mock 폴백 패턴 → metadata 페이지 공통
- Celery Beat 등록 → `workers/celery_app.py::beat_schedule`
- 멀티 프로바이더 폴백 → `llm/__init__.py::get_provider_chain`

---

## 4. 검증 방법

1. **백엔드 기동**: `cd backend && uvicorn main:app --port 8000` → http://localhost:8000/docs 에서 25개 엔드포인트 확인
2. **Celery Beat**: `celery -A workers.celery_app beat` 기동 → `celerybeat-schedule` 확인, 각 태스크 실행 시각 로그 검증
3. **프론트**: `cd mediaX-CMS && npm run dev -- -H 0.0.0.0 -p 4000` → http://localhost:4000/programming/metadata 11개 서브 페이지 Smoke 테스트
4. **E2E**: 샘플 CSV 업로드 → `/upload/batch/{job_id}` 폴링 → Staging 큐 반영 → 벌크 승인 → 콘텐츠 상세 `approved` 확인
5. **이미지 업로드 (A-1 완료 후)**: 실제 파일 업로드 → `/image/{id}` 응답의 `ContentImageOut[]`에 새 이미지 포함 확인
