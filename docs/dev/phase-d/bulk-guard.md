# §4. Bulk Guard

## 위험 시나리오

운영자가 review 큐에서 100건을 선택해 "Bulk WebSearch enrich" 버튼 클릭. 가드 없으면:

```
100건 × 4 provider 폴백 시도 = 최대 400 호출
└─ Brave 일 60 한도 → 처음 60건 흡수 후 소진
   └─ SerpAPI 일 3 한도 → 다음 3건 흡수 후 소진
      └─ Gemini 일 200 한도 → 나머지 37건 흡수 후 소진 = 일일 한도 18% 단발 소진
         └─ 같은 날 다른 작업 (단건 보강, trending Beat) 모두 차단
```

→ **단일 bulk 작업 1회 = 일 쿼터 절반 이상 소진** 가능. 운영 사고 위험.

## 가드 룰

```python
# guard.py
def check_bulk_allowed(expected_calls: int, provider: str) -> None:
    """
    Bulk 호출 사전 가드. 위반 시 BulkQuotaError raise.
    """
    if not config.WEBSEARCH_BULK_ALLOWED:
        raise BulkQuotaError(
            detail="WEBSEARCH_BULK_ALLOWED=false — bulk 차단",
            expected=expected_calls,
            remaining=0,
        )
    daily_limit = config.get(f"WEBSEARCH_{provider.upper()}_DAILY")
    used = quota_manager.current_count(f"websearch:{provider}")
    remaining = daily_limit - used
    if expected_calls > remaining * 0.5:
        raise BulkQuotaError(
            detail=f"{provider} 잔여 쿼터 {remaining} 의 50% 초과 호출 시도",
            expected=expected_calls,
            remaining=remaining,
        )
```

### 거부 룰: `expected > remaining * 0.5`

이유: 1회 bulk 가 잔여 쿼터의 절반 이상을 가져가면, 같은 날 다른 작업이 폴백 체인으로 떨어진다.
50% 마진을 두면 단건 보강 + trending Beat + 다음 운영자 bulk 시도 모두 흡수 가능.

### 예외 케이스

- **Cache hit 예상 비율 적용 안 함** — 가드 단계에서 cache hit 율을 알 수 없음.
  실제 호출 시점에 cache_get → 0 quota. 가드는 보수적으로 모든 건이 cache miss 라고 가정.
- **Provider별 독립 가드** — bulk 가 "어떤 provider 를 쓸지" 사전에 모름.
  → 폴백 체인 첫 provider (Brave) 기준으로만 체크. 폴백 발생 시 추가 거부 안 함.
  → bulk 운영자는 결과 응답에서 provider 분포 확인 후 다음 작업 판단.

## API 응답

bulk-accept / bulk-promote 엔드포인트가 BulkQuotaError 잡았을 때:

```json
HTTP 422 Unprocessable Entity
{
  "detail": "WebSearch bulk quota guard tripped",
  "provider": "brave",
  "expected_calls": 100,
  "remaining_quota": 30,
  "guard_threshold": 15,
  "suggestion": "bulk 분할 (≤15건) 또는 익일 재시도"
}
```

UI 는 422 응답 받으면 운영자에게 "쿼터 가드 발동" 모달 + "분할 실행" 버튼 제시.

## 단발 호출 예외

`expected=1` 단건 호출은 가드 룰에서 자동 통과 (`1 > remaining*0.5` 불성립 — `remaining≥3` 가정).
→ 단건 보강은 가드 영향 없음. UI 버튼 1클릭 = 1 호출.

## 운영 권장

bulk 작업은 다음 시간대만:
- KST 04:30 직후 (Beat trending 5건 소진 후 잔여 55+건)
- KST 21:00 이후 (당일 운영 마감, 익일 재시작 직전)

KST 12:00~18:00 운영 피크에는 bulk 자제. 단건 보강만.
