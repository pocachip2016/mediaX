# plans/ — 모듈 구현 계획

> 세션 시작 시 해당 plan 파일 하나만 읽으면 docs/ 탐색 없이 바로 작업 가능.  
> 서브모듈이 3개 이상이면 `{모듈}/` 디렉토리 + `README.md` + 서브플랜 파일 구조 사용.

## 전체 현황

| 영역 | 디렉토리 | 상태 |
|------|----------|------|
| 1. 프로그래밍 AX | [1_programming/](1_programming/) | 일부 완료 |
| 2. 디자인 AX | [2_design/](2_design/) | not-started |
| 3. 인제스트 AX | [3_ingest/](3_ingest/) | not-started |
| 4. 분석 AX | [4_analytics/](4_analytics/) | not-started |
| 5. 마케팅 AX | [5_marketing/](5_marketing/) | not-started |
| 6. 모니터링 AX | [6_monitoring/](6_monitoring/) | not-started |
| 7. 공통 인프라 | [7_common_infra/](7_common_infra/) | not-started |
| 10. 배포/송출 AX | [10_distribution/](10_distribution/) | not-started |

---

## 1_programming/ 상세

| 모듈 | 상태 | 진행 중인 서브플랜 |
|------|------|------------------|
| [1.1_metadata/](1_programming/1.1_metadata/) | 기반 ✅ / 서브플랜 진행 중 | 1.1.2·1.1.4·1.1.6·1.1.8·1.1.9 |
| [1.2_catalog/](1_programming/1.2_catalog/) | not-started | — |
| [1.3_curation/](1_programming/1.3_curation/) | not-started | — |
| [1.4_approval/](1_programming/1.4_approval/) | not-started | — |
| [1.5_cp_supply/](1_programming/1.5_cp_supply/) | not-started | — |

---

## plan 파일 템플릿

```markdown
# {모듈명} 구현 계획
상태: planning | in-progress | done
마지막 수정: YYYY-MM-DD

## 범위
- 설계 문서: docs/{경로}/
- 핵심 기능: (3줄 이내)

## 의존성
- 선행 모듈:
- 외부 API:

## 백엔드 파일
- [ ] api/{모듈}/models/
- [ ] api/{모듈}/schemas.py
- [ ] api/{모듈}/service.py
- [ ] api/{모듈}/router.py

## 프론트 파일
- [ ] app/(main)/{경로}/page.tsx
- [ ] lib/api.ts 추가 함수

## 테스트
- [ ] tests/api/{모듈}/test_service.py

## 세션 분할
- [ ] 세션 1:
- [ ] 세션 2:

## 완료 기준
- [ ] pytest PASS
- [ ] Swagger 확인
```
