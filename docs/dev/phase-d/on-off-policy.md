# §3. On/Off Policy

## 3 환경변수 + 1 부가 플래그

| 변수 | 기본값 | 효과 |
|------|--------|------|
| `WEBSEARCH_ENABLED` | `true` | 모든 WebSearch 호출 마스터 스위치 |
| `WEBSEARCH_BULK_ALLOWED` | `false` | bulk 시나리오에서만 별도 체크 — 기본 OFF |
| `WEBSEARCH_PROVIDERS` | `brave,serpapi,gemini,ollama` | CSV — 폴백 체인 순서 |
| `WEBSEARCH_TRENDING_ENABLED` | `false` | Beat 자동 trending discovery on/off |

운영 중 즉시 차단 시: `WEBSEARCH_ENABLED=false` → 컨테이너 재시작 → 모든 호출 거부.

## 호출 경로별 기본값

| 경로 | 기본 | opt-in 방법 |
|------|------|-------------|
| `WebSearchDiscoverySource.discover()` | OFF | 명시적 호출만 (Beat or on-demand task) |
| `aggregate_content(content_id)` | OFF | `enable_web_search=True` 파라미터 |
| 단건 보강 API `/contents/{id}/enrich` | OFF | `?include_web_search=true` query |
| Bulk 보강 API `/intelligence/bulk-accept` | OFF | body `enable_web_search=true` + `WEBSEARCH_BULK_ALLOWED=true` 둘 다 필요 |
| Bulk 발굴 API `/seeds/bulk-promote` | n/a | WebSearch는 발굴 단계에만 영향, bulk-promote 자체는 영향 X |
| Beat trending discovery | OFF (`WEBSEARCH_TRENDING_ENABLED=false`) | env true 시 04:30 KST 자동 |

## opt-in 검증 흐름

```python
# aggregator.py 진입부
if enable_web_search:
    if not config.WEBSEARCH_ENABLED:
        # 호출자가 enable_web_search=True 했지만 마스터 스위치 OFF
        log.warning("WebSearch requested but globally disabled")
        enable_web_search = False
    elif is_bulk_context and not config.WEBSEARCH_BULK_ALLOWED:
        log.warning("WebSearch bulk requested but bulk disabled")
        enable_web_search = False
```

## Aggregator 기본 OFF 이유

Phase B aggregator 는 **bulk 자동 호출** 위치다 (Beat 4:30 가 모든 review 큐에 대해 일괄 실행).
여기에 WebSearch 가 default ON 이면 매일 review 큐 N 건 × WebSearch 4 provider 호출 → 분 단위 쿼터 소진.

→ **반드시 명시적 호출자**가 `enable_web_search=True` 로 켜야 함. UI 버튼 또는 단건 보강 시에만.

## Trending Beat 의 안전성

`WEBSEARCH_TRENDING_ENABLED=true` 시에도:
- 일 1회 04:30 KST
- 사전 정의 5 쿼리 한정 (예: "한국 드라마 신작 2026", "넷플릭스 한국 시리즈 2026" 등)
- Brave 우선 → 5 호출 = Brave 일 60 한도의 8% 소비

→ 정책 위반 가능성 거의 없음. 그럼에도 기본 OFF, 운영자 명시 enable 필요.

## 변경 이력 추적

env 값 변경은 컨테이너 재시작 시점에 `ExternalSyncLog(source="websearch_config_change")` 1행 기록.
운영 감사 추적용.
