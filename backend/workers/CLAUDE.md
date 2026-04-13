# backend/workers/ — Celery 워커

## 역할
비동기 AI 처리·배치·이메일 폴링을 Celery로 실행.

## 파일
| 파일 | 역할 |
|------|------|
| `celery_app.py` | Celery 앱 인스턴스 + Beat 스케줄(6개) + 큐 라우팅 |
| `tasks/metadata.py` | 메타데이터 AI 처리·에이전틱 검색·이메일 폴링·KOBIS/TMDB 동기화 |
| `tasks/design.py` | AI 이미지 생성·브랜드 검수·CDN 업로드 |
| `tasks/ingest.py` | 인코딩·QC·DRM·CDN |
| `tasks/analytics.py` | 리포트·정산 배치 |

## tasks/metadata.py 주요 태스크
| 태스크 | 설명 |
|--------|------|
| `process_content_metadata` | AI 처리 (장르/시놉시스/태그/스코어) |
| `enrich_content_metadata` | 에이전틱 멀티소스 검색 — TMDB 시리즈 재귀 수집, KOBIS 검색, ExternalMetaSource·ContentCredit·ContentImage 저장 → status=staging |
| `poll_cp_emails` | IMAP 이메일 폴링 → CpEmailLog + Content(waiting) 생성 |
| `sync_kobis` | 전일 KOBIS 신규 영화 → kobis_movie_cd 매핑 업데이트 |
| `check_missing_episodes` | TMDB 에피소드 수 vs DB 불일치 감지 |
| `retry_failed_enrichments` | 6h 이상 stalled 항목 재시도 |

## 큐 구성
| 큐 | 태스크 |
|----|--------|
| `metadata` | AI 처리, 이메일 폴링, KOBIS/TMDB 동기화 |
| `design.high` | 긴급 이미지 생성 |
| `design.normal` | 일반 이미지 생성 |
| `ingest` | 영상 처리 |
| `analytics` | 통계 배치 |

## Beat 스케줄
| 태스크 | 주기 | 설명 |
|--------|------|------|
| `poll_cp_emails` | 5분 | CP 이메일 폴링 → Content(waiting) 생성 |
| `sync_kobis` | 매일 03:00 | 전일 신규 영화 → kobis_movie_cd 매핑 (완성) |
| `sync_tmdb` | 매주 월 02:00 | TMDB 주간 동기화 (스텁) |
| `reeval_quality_scores` | 매일 01:00 | review 상태 콘텐츠 재처리 |
| `check_missing_episodes` | 매일 04:00 | TMDB vs DB 에피소드 수 불일치 감지 → enrich 재실행 |
| `retry_failed_enrichments` | 6시간 | 6h 이상 processing 상태 → 재시도 (max 3회, 초과 시 rejected) |

## 실행
```bash
# 워커
celery -A workers.celery_app worker --loglevel=info -Q metadata,design.normal,...

# Beat 스케줄러
celery -A workers.celery_app beat --loglevel=info

# Docker
docker compose up worker
```
