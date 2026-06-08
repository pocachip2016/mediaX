# ADR-011-03: AI 자동 LINK — 추천 파이프라인 (Tier 0~6)

> 부모: [adr-011-programming-link_index.md](adr-011-programming-link_index.md)

## 원칙: AI는 추천, 사람은 확정 (human-in-the-loop)

자동 LINK는 즉시 노출되지 않는다. `programming_links` 에 `source=ai`, `confidence`,
`status=suggested` 로 저장 → 운영자가 검수 패널에서 **확정(active)** 또는 **반려(rejected)**.
기존 staging/review-queue 패턴을 그대로 재사용한다.

## 파이프라인 4단계

```
① 후보 수집(Retrieve) → ② 적합도 채점(Score) → ③ 정렬(Rank) → ④ 운영자 확정(Review)
   싼 단계로 넓게 거름        AI로 정밀 점수        지표 블렌딩       사람이 승인
```

비용 핵심 = **캐스케이드**: 싼 단계(필터/벡터)로 후보를 좁힌 뒤 비싼 LLM은 소수에만.

## Tier 표 (mediaX 기존 인프라 재사용)

| Tier | 방법 | 잡는 것 | 재사용 | 도입 |
|------|------|---------|--------|------|
| **0** | 규칙 필터 (AI 아님) | 장르·연도·국가·연령 | 카탈로그 쿼리 | Phase 3.1 |
| **1** ⭐ | LLM 의도 해석: 자연어 → `rule_query`+태그 | 모호한 기획 의도 | AI 엔진 폴백(gemini/groq/ollama) | Phase 3.2 |
| **2** ⭐ | 임베딩 매칭(벡터 kNN): 시놉시스+장르+태그 ↔ 노드 theme 벡터 | 무드·유사작 | Elasticsearch kNN(9200) + `theme_features` | Phase 3.3 |
| **3** | LLM 제로샷 판정: 콘텐츠별 적합도 0~1 + 근거 | 주관적 테마 | AI 엔진 → `ContentAIResult` | 후속 |
| **4** | 신호 블렌딩 랭킹: popularity+recency 가중합 | TOP10·인기순 | `ContentDistribution.popularity_*` | 후속 |
| **5** | RAG 트렌드 시드: 웹 트렌드 → 노드 후보 | 외부 트렌드 | WebSearch 4-provider + `ExternalCuration` | 후속 |
| **6** | 자동 카피 생성(역방향): 멤버 → headline/sub | 큐레이션 문구 | AI 엔진 → 노드 copy | 후속 |

## 1차 범위: Tier 0 + 1 + 2

추가 의존성 없이 기존 인프라로 가능하고 효용이 가장 큰 조합. Tier 3~6은 후속 단계로 분리.

### Tier 1 — LLM 의도 해석
입력: 운영자 자연어("여름에 어울리는 시원한 액션") + 노드 컨텍스트.
출력: `rule_query`(JSON) + 후보 태그 리스트. AI 엔진 폴백 체인 호출.
실패 시 Tier 0 규칙 입력 폼으로 폴백.

### Tier 2 — 임베딩 매칭
- 콘텐츠 벡터: `synopsis + genres + tags` 임베딩 → ES kNN 인덱스(증분 갱신).
- 노드 theme 벡터: `theme_features + headline_copy` 임베딩.
- 자동 LINK 후보 = 노드 벡터의 kNN 상위 + cosine 점수 → `confidence`.

## 추천 결과 저장 / 검수

- 후보는 `programming_links(source=ai, status=suggested, confidence)` 로 일괄 insert.
- 각 후보에 **근거(reason)** 메타 첨부(어떤 규칙/유사도/LLM 사유) — 설명가능성.
- 검수 패널: 적합도 정렬, 신뢰도<임계값 자동 제외 토글, 선택/전체 확정, 재생성.
- 확정 = status active, 반려 = status rejected(재추천 시 제외 학습 신호).

## 불변 규칙

1. AI 추천은 절대 자동 노출 금지 — 반드시 status=suggested 경유.
2. rule(Tier 0) 산출 멤버는 저장 안 하고 read-time 계산(중복 저장 방지). ai 확정분만 active 링크로 영속.
3. confidence·reason 없는 ai 링크 생성 금지(검수 신뢰성).
