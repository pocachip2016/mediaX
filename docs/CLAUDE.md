# docs/ — 미디어AX 설계 문서

> 6개 AX 모듈 + 공통 인프라의 전체 설계 사양 (60개+ 문서)

## 하부 프로젝트 구성

| No | 디렉토리 | 핵심 책임 | 상태 |
|----|---------|----------|------|
| 1 | `1_programming/` | 메타데이터·카탈로그·큐레이션·결재·CP수급 (5모듈) | ✅ 확정 |
| 2 | `2_design/` | 이미지 자동 생성·템플릿·DAM (9섹션) | ✅ 확정 |
| 3 | `3_ingest/` | 수신→인코딩→QC→DRM→CDN (11섹션) | ✅ 확정 |
| 4 | `4_analytics/` | 시청·매출·행동 분석·CP 정산 (7섹션) | ✅ 확정 |
| 5 | `5_marketing/` | 프로모션·CRM/푸시·광고 상품 (7섹션) | ✅ 확정 |
| 6 | `6_monitoring/` | 장애·품질·보안·운영 감시 (8섹션) | ✅ 확정 |
| - | `7_common_infra/` | IAM·알림·MDM·스토리지·DW·검색·스케줄러 (10섹션) | ✅ 확정 |

## 디렉토리 인덱스

| 디렉토리 | 내용 |
|---------|------|
| `0_overview/` | 프로젝트 전체 개요·비즈니스 구조·역할 정의 |
| `1_programming/1.1_metadata/` | AI 메타데이터 파이프라인 (구현 완료, `CLAUDE.md` 있음) |
| `1_programming/1.2_catalog/` | VOD 카탈로그 관리 설계 |
| `1_programming/1.3_curation/` | 홈 큐레이션 AI 설계 |
| `1_programming/1.4_approval/` | 편성 결재·워크플로우 설계 |
| `1_programming/1.5_cp_supply/` | CP사 수급 관리 설계 |
| `8_architecture/` | 통합 아키텍처·API 계약 (18개) |
| `9_todo/` | 이슈·로드맵·작업 목록 |
| `10_distribution/` | 외부 배포·CDN·방송 송출 |

## 비즈니스 모듈 → 기술 문서 매핑

| 비즈니스 모듈 | 핵심 시스템 | 관련 docs 경로 |
|-------------|-----------|--------------|
| M1. 파트너·판권 관리 | CMT | `1_programming/1.5_cp_supply/` |
| M2. AI 콘텐츠·가공 | CMS + VAMS + AI | `1_programming/1.1_metadata/`, `3_ingest/`, `2_design/` |
| M3. 상품·편성·큐레이션 | PMS | `1_programming/1.2_catalog/`, `1.3_curation/` |
| M4. 캠페인·마케팅 | 마케팅 자동화 | `5_marketing/` |
| M5. 배포·송출 | AMOC | `10_distribution/` |
| M6. 정산·통계 | ERP 연동 | `4_analytics/` |

상세 매핑: `0_overview/0.2_business_structure.md`  
API 계약 전체: `8_architecture/8.2_api_contracts.md`
