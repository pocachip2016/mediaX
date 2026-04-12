# backend/workers/ — Celery 워커

## 역할
비동기 AI 처리·배치·이메일 폴링을 Celery로 실행.

## 파일
| 파일 | 역할 |
|------|------|
| `celery_app.py` | Celery 앱 인스턴스 + Beat 스케줄 + 큐 라우팅 |
| `tasks/metadata.py` | 메타데이터 AI 처리·이메일 폴링·KOBIS/TMDB 동기화 |
| `tasks/design.py` | AI 이미지 생성·브랜드 검수·CDN 업로드 |
| `tasks/ingest.py` | 인코딩·QC·DRM·CDN |
| `tasks/analytics.py` | 리포트·정산 배치 |

## 큐 구성
| 큐 | 태스크 |
|----|--------|
| `metadata` | AI 처리, 이메일 폴링, KOBIS/TMDB 동기화 |
| `design.high` | 긴급 이미지 생성 |
| `design.normal` | 일반 이미지 생성 |
| `ingest` | 영상 처리 |
| `analytics` | 통계 배치 |

## Beat 스케줄
| 태스크 | 주기 |
|--------|------|
| `poll_cp_emails` | 5분 |
| `sync_kobis` | 매일 03:00 |
| `sync_tmdb` | 매주 월 02:00 |
| `reeval_quality_scores` | 매일 01:00 |

## 실행
```bash
# 워커
celery -A workers.celery_app worker --loglevel=info -Q metadata,design.normal,...

# Beat 스케줄러
celery -A workers.celery_app beat --loglevel=info

# Docker
docker compose up worker
```
