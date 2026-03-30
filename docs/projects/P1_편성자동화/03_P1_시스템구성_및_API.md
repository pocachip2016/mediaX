# P1 편성 AI 자동화 - 시스템 구성 및 API

## 1. 시스템 아키텍처 (기술 스택)
* **백엔드:** Python 3.11, FastAPI [12].
* **프론트엔드:** React 18, FullCalendar [12].
* **DB & AI:** PostgreSQL 16, Ollama (llama3) [12].
* **스케줄러/큐:** Celery, Redis, Apache Airflow [12].

## 2. 주요 API
* `GET /api/v1/contents`: 콘텐츠 검색 및 목록 [13].
* `POST /api/v1/schedules`: 편성 추가 [13].
* `POST /api/v1/recommend/weekly`: 비동기 주간 편성 추천 생성 [13].
