# 1.1 메타데이터 모듈 — AI 설계 개요

> 이 파일은 1.1_metadata 하위 문서들의 핵심 설계 원칙을 요약합니다.  
> 상세 사양은 각 하위 문서를 참조하세요.

---

## 핵심 설계 원칙

### 1. 메타 입수 3가지 경로

| 경로 | 방식 | 문서 |
|------|------|------|
| CP 이메일 자동 감지 | Celery Beat + imaplib → Claude API 엔티티 추출 | [1.1.1](1.1.1_data_pipeline.md) |
| 실시간 UI 자동완성 | 제목 입력 → Claude API 스트리밍 → 담당자 확정 | [1.1.4](1.1.4_ui_screens.md) |
| 하이브리드 수동 입력 | 기존 CMS 방식 유지 + 필드별 AI 추천 채우기 | [1.1.4](1.1.4_ui_screens.md) |

### 2. AI 엔진 구성 (5개)

| 엔진 | 역할 | 문서 |
|------|------|------|
| A | 장르·카테고리·태그 자동 분류 | [1.1.2](1.1.2_ai_engines.md) |
| B | 시놉시스·줄거리 자동 생성 | [1.1.2](1.1.2_ai_engines.md) |
| C | 인물 정보 자동 태깅 (OCR + 얼굴인식 + STT) | [1.1.2](1.1.2_ai_engines.md) |
| D | 감성·분위기 태깅 (CLIP 이미지 임베딩 포함) | [1.1.2](1.1.2_ai_engines.md) |
| E | 메타 품질 스코어링 (0~100점, 자동/검수/반려 판정) | [1.1.2](1.1.2_ai_engines.md) |

### 3. 오케스트레이션 전략

- **Phase 1 (MVP):** Celery Beat 단일 스택 — n8n 없이 운영
- **Phase 2 이후:** n8n IMAP 노드 PoC → FastAPI Webhook → Celery 큐 연동
- 상세 스케줄: [1.1.9](1.1.9_ingestion_schedule.md)

### 4. 단편 vs 시리즈 수집 전략

| 구분 | 전략 |
|------|------|
| 단편 (Movie) | 1회성 전체 메타 수집 (EBUCore 단일 레코드) |
| 시리즈 (Series) | Parent-Child 구조 — 시즌 메인 먼저 수집 → 에피소드 반복 수집 |

---

## Phase별 로드맵 요약

| Phase | 기간 | 핵심 목표 |
|-------|------|----------|
| Phase 1 | 1개월 | Celery Beat 스케줄러, CP 이메일 폴링, KOBIS/TMDB 기초 연동 |
| Phase 2 | 2개월 | n8n PoC, Claude API 상세 메타 생성, 시리즈 계층 수집, Ollama 배치 도입 |
| Phase 3 | 3개월 | TwelveLabs 영상 분석, CLIP 이미지 임베딩, Whisper STT, Scene Search 벡터 인덱스 |

---

## 관련 문서

- [1.1.1 데이터 입수 파이프라인](1.1.1_data_pipeline.md)
- [1.1.2 AI 처리 엔진](1.1.2_ai_engines.md)
- [1.1.3 메타 데이터 스키마](1.1.3_metadata_schema.md)
- [1.1.4 UI 화면 구성](1.1.4_ui_screens.md)
- [1.1.5 품질 스코어링](1.1.5_quality_scoring.md)
- [1.1.9 수집 스케줄 및 오케스트레이션](1.1.9_ingestion_schedule.md)

*최종 수정: 2026-04-11*
