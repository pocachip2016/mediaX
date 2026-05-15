# Meta Intelligence — Phase D (WebSearch 기반 콘텐츠 발굴)

> 상태: **draft** | 작성: 2026-05-16 | 관련 task: `plans/dev-meta-intelligence-phase-d/`
> 선행 ADR:
> - `docs/dev/meta-intelligence.md` (Phase A/B — 5단계 데이터 흐름·필드 5분류)
> - `docs/dev/phase-c/_index.md` (SEED 라이프사이클·소스 우선순위·승격 가드)
> 본 디렉토리는 Phase D 의 모든 step (D.0 ~ D.8) 이 참조하는 단일 진실원이다.
> 임계·정책의 변경은 해당 섹션 파일을 먼저 수정한 뒤 step 진행한다.

---

## §0. Phase D 의 위치

Phase C 는 정형 API 4종(TMDB Trending, KOBIS 박스오피스, KMDB 신규 등록, OMDb)에서만 SEED 를 발굴한다.
그 결과 다음과 같은 콘텐츠는 발굴 사각지대다:

- **OTT 단독작** — Watcha / Wavve / Coupang Play exclusive (TMDB·KOBIS 미등록 다수)
- **신규 인디 작품** — 정형 DB 등록 전 미디어·블로그 노출만 있는 단계
- **국지적 화제작** — 특정 커뮤니티·언론에서만 다뤄지는 작품

Phase D 는 **WebSearch** 를 다섯 번째 소스로 추가해 이 사각지대를 메운다.
다만 정형 API 와 달리 WebSearch 는 호출당 비용 또는 무료 쿼터 제약이 강하므로,
"호출 가능 여부 사전 가드" 와 "발굴 정확도 보수적 가정" 두 축이 본 ADR 의 중심이다.

---

## §1. 두 축의 제약

### 축 A — 무료 쿼터 초과 절대 금지

| Provider | 무료 한도 | mediaX 정책 (daily) |
|----------|-----------|---------------------|
| Brave Search | 월 2000 (≈일 66) | 60 |
| SerpAPI (Serper) | 월 100 (≈일 3) | 3 |
| Gemini Grounding | RPD 25~200 (모델별) | 200 (flash 기준) |
| Ollama + DDG | 무제한 (local) | ∞ (fallback) |

정책 한도는 무료 티어를 80% 수준에서 안전 마진을 두고 설정한다.
초과 시점에 자동으로 다음 provider 폴백 → 최종 Ollama+DDG fallback.

### 축 B — 공통 모듈 + 선택적 on/off

WebSearch 는 두 경로에서 호출 가능:
1. **DiscoverySource** — SEED 발굴 (Phase C 와 같은 위치)
2. **Aggregator** — 기존 콘텐츠 메타 보강 (Phase B 와 같은 위치)

두 경로 모두 기본은 OFF, 명시적 opt-in 만 호출. 특히 bulk insert 시나리오는
별도 플래그 `WEBSEARCH_BULK_ALLOWED` + 사전 잔여 쿼터 체크로 이중 가드.

---

## §2. 핵심 결정 요약

| 결정 | 내용 | 상세 |
|------|------|------|
| Provider 폴백 순서 | Brave → SerpAPI → Gemini → Ollama+DDG | [sources.md](sources.md) |
| 쿼터 키 단위 | `websearch:{provider}:daily:{YYYYMMDD_KST}` | [quota-policy.md](quota-policy.md) |
| Cache TTL | 7일 SHA256 query_hash + provider 분리 | [cache-policy.md](cache-policy.md) |
| Bulk 가드 | `WEBSEARCH_BULK_ALLOWED` + `expected > remaining * 0.5` 거부 | [bulk-guard.md](bulk-guard.md) |
| on/off 환경변수 | 3개 (ENABLED / BULK_ALLOWED / PROVIDERS CSV) | [on-off-policy.md](on-off-policy.md) |
| Aggregator 기본값 | `enable_web_search=False` | [on-off-policy.md](on-off-policy.md) |
| SEED confidence base | 0.50 (낮음) — 인간 검토 필수 | Phase C 정책 동일 |
| Trending Beat | `WEBSEARCH_TRENDING_ENABLED=true` 시 04:30 KST, 5 쿼리 | [on-off-policy.md](on-off-policy.md) |

---

## 섹션 인덱스

| § | 파일 | 다루는 결정 |
|---|---|---|
| §1 | [sources.md](sources.md) | 4 Provider 비교 + 폴백 순서 + 한국어 지원 매트릭스 |
| §2 | [quota-policy.md](quota-policy.md) | Redis key 컨벤션 + provider별 daily limit + KST 리셋 |
| §3 | [on-off-policy.md](on-off-policy.md) | 3 env 플래그 + Aggregator opt-in + Beat 조건 |
| §4 | [bulk-guard.md](bulk-guard.md) | bulk 시나리오 분석 + 거부 룰 + 예외 케이스 |
| §5 | [cache-policy.md](cache-policy.md) | WebSearchCache 7일 TTL + SHA256 + provider 컬럼 |
| §6 | [monitoring-data-model.md](monitoring-data-model.md) | `/quota`, `/cache-stats`, `/recent` API 스키마 |

---

## §3. Phase A/B/C 와의 연결도

```
                       ┌────────────────────────────────────────────┐
                       │  외부 소스                                 │
                       │  TMDB · KOBIS · KMDB · OMDb · WebSearch(D) │
                       └────────────────┬───────────────────────────┘
                                        │
                  ┌─────────────────────┼─────────────────────┐
                  ▼                     ▼                     ▼
        ┌─────────────────┐  ┌───────────────────┐  ┌──────────────┐
        │ DiscoverySource │  │ enrich_content    │  │ aggregator   │
        │ (Phase C + D)   │  │ (Phase B)         │  │ (Phase B+D)  │
        │ → ContentSeed   │  │ → MetadataCandidate│  │ → FieldSugg  │
        └────────┬────────┘  └─────────┬─────────┘  └──────┬───────┘
                 │                     │                   │
                 ▼                     ▼                   ▼
        ┌─────────────────────────────────────────────────────────┐
        │  검수 백엔드 (Phase B/C resolution & promote API)       │
        └─────────────────────────────────────────────────────────┘
```

Phase D 는 새로운 파이프라인 단계를 추가하지 않고, 기존 두 진입점(DiscoverySource·aggregator)에
WebSearch 를 다섯 번째 소스로 끼워넣는다. 자체 검수 API 는 별도 신설 안 함 — Phase B/C 의
resolution & promote 흐름을 그대로 활용.

---

## §4. 비범위 (out of scope)

- 자체 크롤러 (네이버/다음 영화 직접 스크래핑) — 법적·운영 리스크
- 유료 API (Google Custom Search 유료 티어) — 비용 예측 불가
- WebSearch 결과의 자동 Content 승격 — Phase C 정책 그대로 인간 검토 필수
- 다국어 검색 (영문 외) 비주력 — `country=kr&hl=ko` 한정
