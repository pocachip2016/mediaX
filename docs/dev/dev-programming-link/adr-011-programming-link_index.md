# ADR-011: 편성 통합 모델 (Programming Node + Link DAG)

> Status: **Proposed** · Date: 2026-06-08 · Supersedes: catalog `Category`/`ContentCategory`, distribution `ServiceCategory`/`ServiceCategoryItem`
> Task: `plans/dev-programming-link/` · Module: `backend/api/programming/scheduling/`

## 1. 배경 / 문제

편성(programming)은 카테고리(장르·메타 기준), 큐레이션(시즌 문구·특집), TOP10(랭킹) 등
**여러 기준의 노드**가 *연관 콘텐츠* 또는 *다른 노드*를 내포하고, 콘텐츠/노드가
**여러 곳에 계층적으로 소속**되는 구조다. 현재 코드베이스는 이를 3개의 단절된 체계로 표현한다:

| 체계 | 테이블 | 한계 |
|------|--------|------|
| 카탈로그 분류 | `categories` + `content_categories` | 카테고리가 **단일 부모**(트리) — 여러 곳에 못 걸림 |
| 서비스 큐레이션 | `service_categories` + `service_category_items` | 노드끼리 **중첩 불가**, 카탈로그와 단절 |
| 작품 계층 | `contents.parent_id` | series→season→episode (정상, 유지) |

핵심 미지원: **① 노드가 노드를 내포 ② 노드/콘텐츠의 다중 소속(DAG)**. 트리로는 표현 불가능.

## 2. 결정

**통합(Integration).** 카탈로그·큐레이션 두 체계를 **단일 편성 그래프(DAG)** 로 합치고,
기존 화면·API도 신규 모델로 **전환**한다. 작품 계층(`contents.parent_id`)은 본질적 소유
관계이므로 **그대로 둔다**.

핵심 분리: **노드 정체성(무엇인가) ↔ 배치(어디에 걸리나)**.
배치를 별도 엣지(`ProgrammingLink`)로 빼서 다중 부모·노드 중첩·배치별 기간/문구를 표현한다.

신규 3테이블:
- `programming_node_sets` — 편성안 버전(draft/published)
- `programming_nodes` — 편성 노드(kind: container|rule|rank|manual)
- `programming_links` — 배치 엣지(child_type: node|content) = DAG의 간선

섹션 문서:
- [01. 도메인 모델 (3축 분리 + Node/Link DAG)](adr-011-01-domain-model.md)
- [02. 마이그레이션 전략 (통합 이관 + 레거시 제거)](adr-011-02-migration.md)
- [03. AI 자동 LINK (Tier 0~6 추천 파이프라인)](adr-011-03-ai-autolink.md)
- [04. 편성 운영 GUI (3컬럼 보드 + 캘린더 + 그래프)](adr-011-04-gui.md)

## 3. 결과 / 영향

- ✅ 노드 중첩·다중 소속·배치별 기간/문구를 단일 모델로 표현
- ✅ 장르 카테고리 = `kind=rule`(자동), 특집 = `kind=manual`, TOP10 = `kind=rank` 통일
- ✅ AI 자동 LINK가 같은 `programming_links`에 `source=ai/confidence/status=suggested`로 흘러감 (사람이 확정)
- ✅ 기존 catalog/큐레이션 화면·API를 신규 모델로 전환 (Phase 5) — 단일 운영 일원화
- ⚠ 마이그레이션 중 구·신 테이블 일시 공존(Phase 2~5), 전환 완료 후 레거시 제거(Phase 5)

## 4. 대안 (기각)

- **B. 신규 레이어만 추가(공존)**: 저위험이나 두 체계 영구 공존 → 통합 빚. 운영 일원화 목적상 기각.
- **단일 부모 트리 유지**: 편성 핵심 요구(다중 소속·노드 중첩) 미충족. 기각.
