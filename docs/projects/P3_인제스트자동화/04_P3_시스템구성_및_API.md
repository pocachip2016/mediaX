# P3 인제스트 자동화 - 시스템 구성 및 API

## 1. 기술 스택
파일 폴링용 watchdog, pandas, openpyxl, chardet, Celery, FastAPI, React [37].

## 2. 주요 API
* `POST /api/v1/ingest/upload`: 파일 수동 업로드 지원 [38].
* `GET /api/v1/distributors/{id}/mappings`: 배급사 매핑 프로파일 규칙 조회 [38].
* `POST /api/v1/ingest/items/{item_id}/approve`: 항목 승인 후 P1/P2/P4 트리거 발행 [38].
