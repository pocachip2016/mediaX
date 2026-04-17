# 1.1 메타데이터 — 서브플랜 인덱스

> 기반 구현(모델·라우터·25개 API·6 Beat·11 프론트)은 완료.  
> 이 디렉토리는 설계 문서(docs/1_programming/1.1_metadata/)와 현재 구현 사이의 갭을 채운다.

## 서브플랜 현황

| 파일 | 대응 설계 문서 | 상태 | 핵심 작업 |
|------|--------------|------|----------|
| [1.1.2_ai_engines.md](1.1.2_ai_engines.md) | 1.1.2 AI 처리 엔진 | planning | Claude API 프로바이더 + 스트리밍 UX |
| [1.1.4_ui_screens.md](1.1.4_ui_screens.md) | 1.1.4 UI 화면 | planning | 화면 4(품질 리포트) + 화면 5(분류 체계) |
| [1.1.6_vams.md](1.1.6_vams.md) | 1.1.6~7 VAMS | planning | 키프레임·장면·썸네일 서브시스템 전체 |
| [1.1.8_ext_meta.md](1.1.8_ext_meta.md) | 1.1.8 외부 메타 | planning | 3-source 병합 로직 |
| [1.1.9_schedule.md](1.1.9_schedule.md) | 1.1.9 수집 스케줄 | planning | 누락 Celery 태스크 6개 |

## 완료된 기반 구현

참조: `plans/programming/1.1_metadata.md` (done ✅)

- 모델 14개 테이블, 25개 API 엔드포인트
- Celery Beat 6개 태스크 (poll_cp_emails, sync_kobis, sync_tmdb, enrich, reeval_quality_scores 등)
- 프론트 11개 페이지
- pytest 4개 PASS
