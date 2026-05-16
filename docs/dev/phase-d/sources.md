# §1. Provider 비교 + 폴백 순서

## 4 Provider 비교

| Provider | 무료 한도 | 정확도 | 응답 시간 | 한국어 | 비고 |
|----------|-----------|--------|-----------|--------|------|
| **Brave Search** | 월 2000 (≈일 66) | 중상 | ~300ms | 양호 (`country=kr`) | 광고 없는 결과, API 안정적 |
| **SerpAPI (Serper)** | 월 100 (≈일 3) | **상** (Google 직결) | ~400ms | **최상** (`gl=kr&hl=ko`) | 무료 한도 매우 작음 — 보강용 |
| **Gemini Grounding** | RPD 25~200 (모델별) | 상 (LLM 합성) | ~2s | 양호 | grounding tool `google_search` 활성, RPD 차감 |
| **Ollama + DDG** | 무제한 (local) | 하 (DDG 결과 + LLM 추출) | ~5s | 보통 | 무한 백업, 응답 시간 길어 단발성만 |

## 폴백 순서: Brave → SerpAPI → Gemini Grounding → Ollama+DDG

### 결정 근거

1. **Brave 우선** — 무료 한도 가장 넉넉(일 60 사용 정책), 응답 빠름. 일반 케이스 80% 이상 흡수.
2. **SerpAPI 보조** — 한국어 정확도가 가장 높음. Brave 결과 빈약하거나 한도 소진 시 사용.
3. **Gemini Grounding 3순위** — RPD 200(flash 기준)이지만 1 호출당 3~5 source URL fetch + LLM 합성으로 비용 상대적으로 큼. 정확도 필요한 케이스만.
4. **Ollama+DDG 최후 fallback** — 무료 한도 모두 소진 시에도 작업 흐름이 끊기지 않도록 보장.

### 한국어 지원 매트릭스

| Provider | KR 전용 결과 | 영문 cross-search | 한국어 snippet 품질 |
|----------|--------------|-------------------|---------------------|
| Brave | `country=kr&search_lang=ko` | `country=us` 별도 호출 가능 | 양호 |
| SerpAPI | `gl=kr&hl=ko` | `gl=us&hl=en` 가능 | 최상 (Google 결과 그대로) |
| Gemini | grounding 자동 selection | LLM 자동 양쪽 검색 | 합성문 (원본 snippet 미노출) |
| Ollama+DDG | DDG `kl=kr-ko` | `kl=us-en` 가능 | 보통 (DDG 자체 한계) |

## 호출당 비용 (운영 참고)

| Provider | 무료 티어 1회 비용 | 유료 시 1회 비용 |
|----------|---------------------|------------------|
| Brave | $0 (월 2000 내) | $5 / 1000 calls |
| SerpAPI | $0 (월 100 내) | $50 / 1000 calls |
| Gemini Grounding | $0 (RPD 내) | $35 / 1000 calls (Flash) |
| Ollama+DDG | $0 (전기료만) | $0 |

mediaX 정책: **유료 전환 시 즉시 OFF** — `WEBSEARCH_PROVIDERS=ollama` 한정으로 강제 폴백.

## 응답 정규화

모든 provider 결과는 다음 dataclass 로 통일:

```python
@dataclass
class WebSearchResult:
    url: str
    title: str
    snippet: str
    source_domain: str  # urlparse(url).netloc
    score: float        # provider 자체 score 또는 순위 기반 0~1
```

provider별 응답 스키마 차이는 각 provider 클래스 내부에서 흡수.
