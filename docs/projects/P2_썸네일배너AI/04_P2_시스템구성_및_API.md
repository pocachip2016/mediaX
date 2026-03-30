# P2 썸네일·배너 AI 생성 - 시스템 구성 및 API

## 1. 기술 스택
Pillow, smartcrop-python, Celery, Redis, FastAPI, MinIO (S3 호환 로컬 오브젝트 스토리지) [25].

## 2. 주요 API
* `POST /api/v1/images/generate`: 콘텐츠 이미지 생성 요청 [26].
* `GET /api/v1/images/qc/pending`: QC 대기 이미지 목록 [26].
* `POST /api/v1/images/{image_id}/approve`: 이미지 검수 승인 [26].
