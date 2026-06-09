# ADR-013-01 슬롯 모델 + ProgrammingNode 재사용

> 상위: [adr-013-curation_index](adr-013-curation_index.md)

## 신규 테이블 1 — `home_slots`

홈 화면 슬롯 정의. 슬롯이 **어떤 `ProgrammingNodeSet` 을 어느 디바이스·시간대·위치에 노출하는지** 의 배치 컨텍스트만 담는다(콘텐츠 트리는 node_set 이 보유).

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | Integer PK | |
| `slot_code` | Enum(A~F) | 홈 슬롯 위치 코드 |
| `slot_type` | Enum | `banner`/`theme`/`personal`/`genre`/`ranking`/`promo` (docs 1.3.1 슬롯 A~F) |
| `device` | Enum | `all`/`tv`/`mobile`/`web` |
| `time_band` | Enum | `all`/`morning`/`afternoon`/`evening`/`night` |
| `position` | Integer | 동일 (device,time_band) 내 정렬 순서 |
| `node_set_id` | FK→`programming_node_sets.id` (SET NULL) | 노출할 편성 세트 |
| `is_active` | Boolean default true | |
| `created_at`/`updated_at` | DateTime | |

`__table_args__`: `Index(slot_code, device, time_band)` — resolve 조회 최적화.

### 런타임 resolve 규칙
홈 화면 조립 시 `resolve(device, time_band)`:
1. `is_active=true` 슬롯 중 `device ∈ {요청device, all}` AND `time_band ∈ {요청time_band, all}` 필터.
2. 구체값(tv/evening)이 `all` 보다 우선 — 동일 slot_code 에 구체·all 둘 다 있으면 구체값 채택.
3. `slot_code, position` 정렬 후 각 슬롯의 `node_set` → `node_service` 트리로 콘텐츠 전개.

## 신규 테이블 2 — `curation_banner_plans`

배너 슬롯(A)용 **주간 편성안 승인 워크플로우**. 워크플로우 상세는 [02-banner-pipeline](adr-013-02-banner-pipeline.md).

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | Integer PK | |
| `week_start` | Date | 편성 주(월요일) |
| `status` | Enum | `draft`/`review`/`approved`/`published` |
| `node_set_id` | FK→`programming_node_sets.id` | 편성안이 묶은 배너 노드 세트 |
| `ctr_prediction` | Float nullable | CTR 예측(스텁, Phase 2 실측) |
| `reviewer` | String(100) nullable | 승인 담당자 |
| `reviewed_at` | DateTime nullable | |
| `published_at` | DateTime nullable | |
| `created_at`/`updated_at` | DateTime | |

`__table_args__`: `UniqueConstraint(week_start)` — 주당 1 편성안.

## ProgrammingNode 재사용 (신규 테이블 없음)

- **슬롯 내부 구조 / 테마관 / 콘텐츠 배치** 는 전부 `ProgrammingNode/Link` 로 표현. `home_slots.node_set_id` 가 진입점.
- 테마관·기획전 = `ProgrammingNode(kind=rule/rank)` — `theme_features`(테마 키워드), `rule_query`(매칭 규칙), `embed_theme`(시맨틱 임베딩) 그대로 사용.
- 신규 enum 외에 노드 스키마 변경 **없음** — 하이브리드의 핵심.

## 모델 파일 배치
- `backend/api/programming/curation/models.py` — `HomeSlot`, `CurationBannerPlan` + enum(`SlotCode`, `SlotType`, `Device`, `TimeBand`, `BannerPlanStatus`)
- `scheduling.models` 의 `ProgrammingNode/Set/Link` 는 import 재사용(중복 정의 금지 — 모듈 shadowing 규칙).
- alembic `0048_curation_models.py` — 2 테이블 create.
