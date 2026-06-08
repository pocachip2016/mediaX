# ADR-011-05: 콘텐츠 의미 프로파일 (Ingest-time Content Understanding Profile)

> 부모: [adr-011-programming-link_index.md](adr-011-programming-link_index.md) · 관련: [03. AI 자동 LINK](adr-011-03-ai-autolink.md)

## 원칙: 근거는 read-time이 아니라 ingest-time에 precompute

AI 자동 LINK(Tier 1·2)의 "근거(evidence)"를 **추천 순간(read-time)에 large LLM으로 생성하면** 비용·지연·합법성 리스크가 크다. 대신 **메타입력 단계(ingest-time)에 콘텐츠 의미 프로파일(CUP)을 1회 precompute**해 저장하고, 추천 순간엔 **벡터 cosine + facet 겹침**만 계산한다(거의 공짜·설명가능).

```
[ingest-time, 1회/콘텐츠]  시놉시스/메타 → 임베딩 + facet 추출 → CUP 저장
[read-time, 추천 시]       노드 theme벡터 ↔ CUP 벡터 cosine + facet overlap → confidence
```

노드도 대칭으로 `theme_features`(facet) + theme 벡터를 가져, 추천 = 양쪽 프로파일의 거리.

## 근거 소스 — 비용·합법성·가치 (POC 결정)

| 소스 | AI/HW 비용 | 합법성 | 가치 | POC |
|------|-----------|--------|------|-----|
| 구조화 메타(장르/연도/국가) | 0 | 안전 | 중 | ✅ Tier0 |
| 시놉시스 임베딩(Ollama bge-m3) | ~0 로컬 | 안전(파생) | 상 | ✅ |
| 로컬 LLM facet 추출(Ollama 3b) | 낮음(배치) | 안전 | 상 | ✅ off-peak |
| WebSearch/전문가평 → facet | 네트워크+쿼터 | ⚠ 파생만 저장 | 중상 | ✅ 파생만 |
| 자막/STT dialogue 임베딩 | 높음(GPU) | ⚠ 파일·권리 필요 | 상 | 🔜 슬롯 예약 |
| 포스터/키프레임 CLIP | 중(GPU) | 안전 | 중 | 🔜 Dam 인프라 |
| 시청로그 협업필터 | 0 | 안전 | 상 | ❌ 로그 없음 |

POC 제약: 미디어/자막 미보유(향후 TEST 영상), Ollama만(임베딩도 Ollama 서빙), 직접 서비스 안 함(시청로그 없음). → POC 근거는 **구조메타 + 시놉시스 임베딩 + 로컬 LLM facet + WebSearch 파생**으로 닫히며 전부 로컬·무료.

## CUP 스키마 (`content_semantic_profile`, 1:1 with content)

| 컬럼 | 타입 | 비고 |
|------|------|------|
| `content_id` | FK UNIQUE | |
| `facets` | JSONB | 통제어휘 (아래) |
| `keywords` | JSON | 핵심 키워드 |
| `embed_synopsis` | JSON float[] | bge-m3 1024-dim |
| `embed_dialogue` | JSON, null | 자막/STT 확보 시 |
| `embed_visual` | JSON, null | CLIP 확보 시 |
| `essence` | Text | 1~2문장 로컬 LLM 증류 |
| `provenance` | JSONB | 기여 소스(합법성 감사 + confidence 가중) |
| `model_version` | String | 재계산 트리거 |
| `computed_at` | TIMESTAMPTZ | |

벡터는 Postgres JSON(SSOT). 코드베이스 관례(JSONB, SQLite-compat) 준수 — pgvector 미사용.

## facet 통제어휘 (한국어 편성 맥락)

자유서술 금지 → 통제어휘 강제(매칭 일관·설명가능). 상수 모듈 `scheduling/facets.py`로 코드화(LLM 출력 검증 + overlap 점수 공용).

```
mood:     [경쾌, 감성, 긴장, 따뜻, 어두움, 코믹, 로맨틱, 비장]
occasion: [주말, 가족시청, 심야, 명절, 연말, 비오는날, 몰아보기]
audience: [아동, 청소년, 성인, 가족, 시니어]
tempo:    [느림, 보통, 빠름]
tone:     [진지, 가벼움, 풍자, 다큐멘터리]
setting:  {era: [현대,시대극,근미래,중세], place: [한국,미국,일본,유럽,가상]}
themes:   [성장, 복수, 우정, 가족, 생존, 범죄, 사랑, 전쟁, 음모]
```

## 앙상블 confidence (read-time, 비싼 LLM 1콜 대체)

약신호 3개 가중합이 단일 LLM 판정보다 싸고 안정적:

```
confidence = w_rule·rule_match + w_facet·facet_overlap + w_cos·synopsis_cosine
reason     = provenance + 일치 facet 목록 + cosine 값  (설명가능)
```

POC 가중치 초안 `(0.3, 0.3, 0.4)` — active-learning(확정/반려)으로 추후 보정.

## 합법성

미디어 미보유 → STT 이슈 현 단계 없음. WebSearch/전문가평은 **facet/키워드 파생만 저장, 원문 verbatim 금지**(로컬 LLM이 읽고 파생만; 원문은 기존 `WebSearchCache`에만 잔류, CUP엔 전사 안 함). 임베딩 저장 = 재구성 불가 방패. TMDB 어트리뷰션 준수.

## POC 단순화 / 연기

- **kNN = Python 브루트포스 cosine**: 후보를 Tier0 `rule_engine`로 수백건 축소 후 cosine. **ES kNN(9200)은 미배선·scale-phase 연기**(config만 존치). ADR-03 Tier 2의 ES는 스케일 단계 명세.
- **dialogue/visual 벡터**: nullable 슬롯만 예약, 미디어 확보 시 채움(스키마 변경 불필요).
- **협업필터**: 시청로그 확보 시 도입(가장 싸고 강한 근거).
