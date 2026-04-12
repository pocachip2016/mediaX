# 미디어AX 프로젝트 기획서

> **프로젝트명:** 미디어AX (Media AI Transformation)
> **대상 조직:** KT 지니TV VOD 서비스 운영사
> **최종 사용자:** 사내 편성/제작 담당자 + 외부 클라이언트 (CP사, 광고주)
> **현재 단계:** 상세 설계 완료
> **목표:** 6개 하부 프로젝트 + 공통 인프라를 개별 설계 후 통합 웹 솔루션으로 구현

---

## 1. 하부 프로젝트 구성

| No | 하부 프로젝트 | 설계 상태 | 모듈/섹션 수 | 핵심 책임 |
|----|-------------|-----------|-------------|----------|
| 1 | 편성 기획 AX | ✅ 확정 | 5개 모듈 | 메타데이터 + 카탈로그 + 큐레이션 + 결재 + CP수급 |
| 2 | 디자인 AX | ✅ 확정 | 9개 섹션 | 이미지 자동 생성 + 템플릿 + DAM |
| 3 | 인제스트 AX | ✅ 확정 | 11개 섹션 | 수신 → 인코딩 → QC → DRM → CDN |
| 4 | 통계 AX | ✅ 확정 | 7개 섹션 | 시청/매출/행동 분석 + CP 정산 |
| 5 | 마케팅 AX | ✅ 확정 | 7개 섹션 | 프로모션 + CRM/푸시 + 광고 상품 |
| 6 | 모니터링 AX | ✅ 확정 | 8개 섹션 | 장애/품질/보안/운영 감시 |
| 공통 | 공통 인프라 레이어 | ✅ 확정 | 10개 섹션 | IAM + 알림 + MDM + 스토리지 + DW + 검색 + 스케줄러 |

---

## 2. 비즈니스 모듈 구조 (M1~M6)

> 기술 모듈과 별개로, 운영자 업무 흐름 기준의 비즈니스 도메인 구조.
> 각 모듈은 핵심 시스템(CMT, VAMS, PMS, AMOC 등)으로 구현된다.

| 비즈니스 모듈 | 핵심 시스템 | 대응 기술 문서 |
|-------------|-----------|--------------|
| M1. 파트너 및 판권 관리 | CMT (Content Management Tool) | `1_programming/1.5_cp_supply/` |
| M2. AI 콘텐츠 및 가공 관리 | CMS + VAMS + AI Dashboard | `1_programming/1.1_metadata/` + `3_ingest/` + `2_design/` |
| M3. 상품 및 편성/큐레이션 | PMS (Product Management System) | `1_programming/1.2_catalog/` + `1.3_curation/` |
| M4. 지능형 캠페인/마케팅 | 마케팅 자동화 | `5_marketing/` |
| M5. 배포 및 송출 관리 | AMOC (Asset Management & Output Control) | `10_distribution/` |
| M6. 정산/통계 시스템 | ERP 연동 | `4_analytics/` |

상세 매핑: `0_overview/0.2_business_structure.md`

---

## 3. 모듈 간 데이터 흐름

```
[CP사] ──영상──→ [인제스트 AX]
                      │
         ┌────────────┼──────────────┐
         ▼            ▼              ▼
    스틸컷/분석    핑거프린트/CDN   자막/감성
         │            │              │
         ▼            ▼              ▼
    [디자인 AX]  [편성 기획 AX]  [편성 기획 AX]
    썸네일/배너   모듈2 카탈로그   모듈1 메타데이터
         │            │              │
         └─────┬──────┘              │
               ▼                     │
         [편성 기획 AX] ←────────────┘
          모듈3 큐레이션
          모듈4 결재
          모듈5 CP수급
               │
     ┌─────────┼─────────┐
     ▼         ▼         ▼
[마케팅 AX] [통계 AX] [모니터링 AX]
```

### 핵심 API 계약 (18개)

| ID | 제공자 → 소비자 | 데이터 |
|----|----------------|--------|
| A | 인제스트 → 편성 모듈1 | 얼굴인식, 음성분석, 자막, 감성 |
| B | 인제스트 → 편성 모듈2 | 핑거프린트, 서비스URL, CDN |
| C | 인제스트 → 디자인 | 스틸컷/키프레임 소스 |
| D | 편성 모듈1 → 편성 모듈2 | 메타 분류, 품질 스코어 |
| E | 편성 모듈1 → 디자인 | 장르/감성 태그 |
| F | 편성 모듈2 → 편성 모듈3 | 신규 콘텐츠, 홀드백, 만료 |
| G | 편성 모듈1 → 편성 모듈3 | 감성 태그, 인물 정보 |
| H | 편성 모듈2 → 마케팅 | 가격/신규/홀드백 트리거 |
| I | 편성 모듈3 → 마케팅 | 트렌드, 큐레이션 슬롯 |
| J | 편성 모듈2 → 통계 | 가격/라이선스/카탈로그 |
| K | 편성 모듈3 → 통계 | 큐레이션 성과 |
| L | 마케팅 → 통계 | 캠페인 성과 |
| M | 통계 → 편성 모듈3 | 시청 데이터 |
| N | 통계 → 마케팅 | 행동/세그먼트 데이터 |
| O | 전체 → 모니터링 | 헬스/로그/감사 이벤트 |
| P | 디자인 → 편성 모듈3 | 기획전 커버 이미지 |
| Q | 마케팅 → 디자인 | 프로모션 배너 트리거 |
| R | 통계 → 편성 모듈5 | CP별 시청/매출 데이터 |

상세: `8_architecture/8.2_api_contracts.md`

---

## 4. 규모 지표

| 항목 | 수치 |
|------|------|
| 월 신규 VOD | 1,000~5,000건 |
| 디자인 에셋 월 처리량 | 500~2,000건 |
| DB 테이블 총계 | ~99개 |
| 모듈 간 API 계약 | 18개 |
| 전체 문서 파일 수 | 60개+ |

---

## 5. 기술 스펙 (MVP 확정)

### 프론트엔드
- **프레임워크:** Next.js 16 + TypeScript
- **모노레포:** Turbo monorepo (npm workspaces)
- **UI 패키지:** `@workspace/ui` — shadcn/ui 컴포넌트 공유 라이브러리
- **스타일:** Tailwind CSS v4 (OKLch 색상 공간)
- **테마:** next-themes (라이트/다크 모드)
- **앱 위치:** `mediaX-CMS/apps/web/`

### 백엔드
- **프레임워크:** Python FastAPI
- **ORM:** SQLAlchemy + Alembic
- **작업 큐:** Celery + Redis

### AI 엔진 (외부 API — GPU 없음)
- **텍스트 분석:** Claude API 또는 OpenAI GPT-4o
- **이미지 분석:** Claude Vision 또는 GPT-4o Vision
- **얼굴 인식:** AWS Rekognition 또는 Google Cloud Vision
- **OCR:** Naver Clova OCR 또는 Google Vision OCR

### 데이터베이스
- **메인 DB:** PostgreSQL
- **검색:** Elasticsearch
- **캐시:** Redis

### 인프라 (로컬 MVP)
- Docker Compose / Nginx / Grafana + Prometheus

### 개발 환경
- 팀 1~2명, Python + JS/TS, 로컬 서버

### 호출 구조
```
브라우저 → Next.js (UI) → FastAPI → PostgreSQL
                               ↓
                         Celery 워커 (AI 처리·배치)
```

### 프로젝트 구조
```
mediaX/
├── docs/
│   ├── 0_overview/        # 프로젝트 전체 개요
│   ├── 1_programming/     # 편성 기획 AX
│   ├── 2_design/          # 디자인 AX
│   ├── 3_ingest/          # 인제스트 AX
│   ├── 4_analytics/       # 통계 AX
│   ├── 5_marketing/       # 마케팅 AX
│   ├── 6_monitoring/      # 모니터링 AX
│   ├── 7_common_infra/    # 공통 인프라 레이어
│   ├── 8_architecture/    # 통합 아키텍처
│   ├── 9_todo/            # 작업 목록 및 이슈
│   └── 10_distribution/   # 외부 배포
├── mediaX-CMS/            # Turbo 모노레포 (프론트엔드)
│   ├── apps/
│   │   └── web/           # Next.js 16 앱 (App Router)
│   │       ├── app/(main)/        # 라우트 그룹 — 메인 레이아웃
│   │       │   ├── programming/   # 편성 기획 AX 페이지
│   │       │   ├── design/        # 디자인 AX 페이지
│   │       │   ├── ingest/        # 인제스트 AX 페이지
│   │       │   ├── analytics/     # 통계 AX 페이지
│   │       │   ├── marketing/     # 마케팅 AX 페이지
│   │       │   └── monitoring/    # 모니터링 AX 페이지
│   │       ├── components/layout/ # AppSidebar, Header
│   │       ├── config/            # site-config.ts, docs.ts
│   │       └── lib/               # nav.ts 네비게이션 헬퍼
│   └── packages/
│       ├── ui/            # @workspace/ui — shadcn/ui 공유 컴포넌트
│       ├── typescript-config/
│       └── eslint-config/
├── backend/               # Python FastAPI
│   ├── api/
│   │   ├── programming/
│   │   ├── design/
│   │   ├── ingest/
│   │   ├── analytics/
│   │   ├── marketing/
│   │   ├── monitoring/
│   │   ├── common/
│   │   └── distribution/
│   ├── workers/           # Celery 워커 (AI 처리·배치·CDN 업로드)
│   ├── shared/            # 공통 스키마·타입·미들웨어
│   └── alembic/           # DB 마이그레이션
└── docker-compose.yml     # 전체 서비스 통합 오케스트레이션
```
