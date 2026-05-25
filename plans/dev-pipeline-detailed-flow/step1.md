# Step 1: dpf-schema (Phase B)

> Milestone: dev-pipeline-detailed-flow

## 작업
9-stage 모델의 DB 스키마 + alembic migration + 백필.

산출:
- `backend/api/programming/metadata/models.py` — enum 4개 추가
  - `PipelineStage` (s1_intake ~ s9_publish)
  - `IntakeChannel` (email_poll / manual / bulk_csv / dam_webhook)
  - `StageEventType` (entered / completed / skipped / failed / retried / gate_opened / advanced)
  - `FailureCode` (none / llm_parse_error / tmdb_quota_exceeded / ...)
- `backend/api/programming/metadata/models.py` — Content 컬럼 4 추가
  - `intake_channel`, `current_stage`, `failure_code`, `gate_overrides(JSON)`
- `backend/api/programming/metadata/models.py` — `StageEvent` 신규 테이블 + 2 index
- `backend/alembic/versions/0018_pipeline_stage_model.py`
  - enum CREATE TYPE 4개
  - content ALTER 4 columns
  - stage_event CREATE TABLE
  - backfill: status → current_stage 역매핑 UPDATE
- `backend/tests/test_stage_event_schema.py` — 5 pytest
  - enum value 매핑
  - StageEvent CRUD
  - Content 신규 컬럼 nullable 동작
  - backfill 매핑 정확성
  - index 존재 확인

## 검증
```bash
cd backend && alembic upgrade head
pytest tests/test_stage_event_schema.py -v
```

## Acceptance Criteria
```bash
/verify dpf-schema
```

## 모델 전환 안내
- 구현은 Sonnet.
- 완료 후 `/model haiku` 로 전환 후 `/verify dpf-schema` 실행.
