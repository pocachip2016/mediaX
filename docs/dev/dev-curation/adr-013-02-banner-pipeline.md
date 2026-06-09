# ADR-013-02 배너 AI 편성 워크플로우 + 테마관 자동 생성

> 상위: [adr-013-curation_index](adr-013-curation_index.md)

## 배너 주간 편성안 워크플로우

`curation_banner_plans.status` 상태 머신 (docs 1.3.2 "주간 편성안 자동 생성 → 리뷰/조정 → 승인 → 반영 → 성과 리포트"):

```
draft ──(submit)──> review ──(approve)──> approved ──(publish)──> published
  │                    │                                              │
  └─ 생성 직후          └─ 담당자 조정(node_set 편집)                   └─ 홈 슬롯 A 노출
```

| 전이 | 트리거 | 동작 |
|------|--------|------|
| → `draft` | `banner_service.create_plan(week_start)` | auto 파이프라인 결과 노드 수집 → 새 `ProgrammingNodeSet` 생성 → CTR 예측 스텁 계산 |
| draft → review | `submit_plan(id)` | 담당자 리뷰 대기 상태로 |
| review → approved | `approve_plan(id, reviewer)` | `reviewer`/`reviewed_at` 기록 |
| approved → published | `publish_plan(id)` | `node_service.publish_node_set(node_set_id)` 호출 + `published_at` + 배너 슬롯(A) `home_slots.node_set_id` 바인딩 |

### CTR 예측 스텁 인터페이스
```python
def predict_ctr(db, node_set_id) -> float:
    """배너 편성안 CTR 예측. MVP: 노드 수·신뢰도 기반 휴리스틱 스텁.
    Phase 2: 학습 모델 교체 (curation_performance 실측 학습)."""
```
MVP 는 `node_set` 내 active 링크 평균 `confidence` × 가중치 같은 단순 휴리스틱. 실측 학습은 후속.

## 테마관·기획전 자동 생성 (auto_service 재사용)

docs 1.3.3 "트렌드 감지 → 테마 키워드 추출 → 매칭 콘텐츠 수집 → 카피 생성 → 승인" 은 **ADR-012 auto 파이프라인 P1~P6 과 동형**:

| 1.3.3 단계 | auto_service 대응 | 비고 |
|-----------|------------------|------|
| 테마 키워드 추출 | P1 define (theme_features) | 노드 정의 |
| 매칭 콘텐츠 수집 | P2 match (`match_service` cosine+facet) | 재사용 |
| 보강 | P3 enrich | 재사용 |
| 점수화 | P4 score | 재사용 |
| 충돌 검사 | P5 conflict (`conflict_service`) | 재사용 |
| 승인·발행 | P6 publish | 재사용 |

따라서 테마관 자동 생성은 **신규 코드 없이** `ProgrammingNode(kind=rule/rank, auto_enabled=true)` 로 만들고 auto tick 이 처리한다. 큐레이션은 **테마관 노드를 홈 슬롯(B)에 바인딩** 하는 레이어만 담당.

- 카피(제목/설명) 생성 = `node.headline_copy`/`sub_copy` (기존 필드). AI 카피 생성 훅은 P3 enrich 내 기존 로직 재사용.

## banner_service 책임 (`curation/banner_service.py`)
- `create_plan(week_start)` — 배너용 auto_enabled 노드 수집 → node_set 묶기 → CTR 스텁 → draft 생성
- `submit_plan`/`approve_plan`/`publish_plan` — 상태 전이 (멱등)
- `predict_ctr` — CTR 휴리스틱 스텁
- 테마관 자동 생성은 `scheduling.auto_service` 위임 (큐레이션은 트리거/바인딩만)

## 트리거 (plan step 8, 선택)
- 주간 Beat: 매주 월요일 배너 `create_plan(this_week)` 자동 호출 → draft 대기
- 테마관 재매칭: 신규 콘텐츠 임베딩 갱신 시 `scheduling_auto.rematch` 훅 재사용
