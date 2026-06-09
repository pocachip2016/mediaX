# ADR-013 홈 큐레이션 모듈 — 하이브리드 아키텍처 (Index)

- **상태**: Accepted (2026-06-09)
- **모듈**: `1.3 큐레이션` (`backend/api/programming/curation/`, 신규)
- **관련**: ADR-011(편성 통합 노드), ADR-012(자동편성 파이프라인)

## 결정 요약

홈 큐레이션을 **별도 모듈로 신설하되, 슬롯 구조·콘텐츠 배치·테마 매칭은 기존 `scheduling` 의 `ProgrammingNode/Link` DAG 를 재사용**하는 하이브리드로 구축한다. 큐레이션 고유 개념(홈 화면 배치 컨텍스트, 배너 주간 편성안 승인 흐름)만 신규 `curation` 테이블로 둔다.

### 근거
- `scheduling` 이 이미 슬롯=container 노드, 테마관=rule·rank 노드, AI배너=auto P1~P6 파이프라인, 콘텐츠 매칭=`match_service`/`suggest_service` 를 제공한다. `catalog` 도 동일 노드 모델을 공유한다.
- 큐레이션 노드 로직을 신규로 만들면 DAG·매칭·발행 로직이 통째로 중복된다 → 재사용.
- 단, 큐레이션 고유 개념(디바이스/시간대 노출 위치, 배너 편성안 승인 워크플로우)은 노드 모델에 없으므로 신규 테이블로 분리한다.

## 핵심 재사용 매핑

| 큐레이션 개념 | 재사용 대상 | 위치 |
|--------------|-----------|------|
| 홈 슬롯 컨테이너 | `ProgrammingNode(kind=container)` | `scheduling/models.py` |
| 슬롯 내 콘텐츠/테마관 배치 | `ProgrammingLink` | `scheduling/models.py` |
| 테마관·기획전 | `ProgrammingNode(kind=rule/rank, theme_features, embed_theme)` | `scheduling/models.py` |
| 테마관 자동 생성 | `auto_service` P1~P6 (auto_enabled 노드) | `scheduling/auto_service.py` |
| 테마 콘텐츠 매칭 | `match_service`(cosine+facet) + `suggest_service` | `scheduling/match_service.py` |
| 편성안 발행 | `node_service.publish_node_set` + `ProgrammingNodeSet.status` | `scheduling/node_service.py` |

## 범위 경계

### MVP (이 ADR)
1. **홈 슬롯 구조** — 슬롯 A~F·디바이스·시간대·위치 → `ProgrammingNodeSet` 바인딩. 상세: [01-slot-model](adr-013-01-slot-model.md)
2. **배너 AI 주간 편성안** — draft→review→approved→published 워크플로우. 상세: [02-banner-pipeline](adr-013-02-banner-pipeline.md)
3. **테마관·기획전 자동 생성** — `auto_service` 재사용(별도 테이블 불필요). 상세: [02-banner-pipeline](adr-013-02-banner-pipeline.md)

### 후속 (Phase 2 — 이 ADR 범위 밖)
- 개인화 추천 고도화(협업필터링/콘텐츠기반 ML) — `docs/1_programming/1.3_curation/1.3.4_personalization.md`
- 트렌드 감지 외부연동(SNS/뉴스/시상식) — `1.3.5_trend_engine.md`
- A/B 테스트 프레임워크 + 성과 측정(노출/CTR/전환 런타임 집계) — `1.3.6_ab_test.md`, `1.3.0` 성과 리포트

## 신규 테이블 (MVP 2개, alembic 0048)
- `home_slots` — 슬롯 배치 컨텍스트 → node_set 바인딩
- `curation_banner_plans` — 배너 주간 편성안 승인 워크플로우

스키마 상세: [01-slot-model](adr-013-01-slot-model.md)

## plan 스텝 인덱스

`plans/dev-curation/index.json` (8 step):
1. **adr-013-curation** — 이 ADR 3문서 + plan 스캐폴드 (완료)
2. curation-model-migration — 모델 + alembic 0048
3. slot-service — 슬롯 CRUD + resolve
4. banner-service — 편성안 생성/CTR스텁/승인/발행 + 테마관 auto 트리거
5. curation-endpoints — router + main 마운트
6. fe-nav-slot-board — nav + 슬롯 보드 골격 + api
7. fe-banner-review — 편성안 리뷰/승인 패널
8. curation-triggers(선택) — 주간 자동 편성안 Beat
