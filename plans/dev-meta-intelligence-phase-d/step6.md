# D.6 — Aggregator opt-in integration

## 목표
메타 보강 시 WebSearch를 선택적으로 활성화 (기본 OFF).

## 산출물

### 백엔드 파일 수정
1. **`backend/api/meta_core/aggregator.py`**
   - `aggregate_content(content_id, db, enable_web_search=False)` 파라미터 추가
   - `aggregate_batch(content_ids, db, enable_web_search=False)` 파라미터 추가
   - `_add_websearch_suggestions(content_id, db)` 함수 신규 (빈 필드 탐지 + WebSearch)
   - `_create_websearch_suggestion(content_id, field_name, search_results, db)` 함수 신규

2. **`backend/api/meta_core/intelligence/schemas.py`**
   - `BulkAcceptRequest.enable_web_search: bool = False` 필드 추가

3. **`backend/api/meta_core/intelligence/router.py`**
   - import: `aggregate_content`, `check_bulk_allowed`, `BulkQuotaError`
   - `bulk_accept()` 함수 수정:
     - enable_web_search=true 시 check_bulk_allowed 가드
     - aggregate_content 호출 (enable_web_search 전달)
     - BulkQuotaError → 422 응답

### 테스트 파일
- **`backend/tests/meta_core/test_aggregator_websearch.py`** — 7개 케이스
  1. enable_web_search=False (기본, WebSearch 미호출)
  2. enable_web_search=True (WebSearch 호출)
  3. 빈 필드 없음 (WebSearch 스킵)
  4. 빈 필드 있음 + WebSearch 결과
  5. LLM 추출 성공 → FieldSuggestion 생성
  6. LLM 추출 실패 (empty) → 무시
  7. Bulk guard 검증

## 구현 세부

### _add_websearch_suggestions 로직

```python
def _add_websearch_suggestions(content_id, db):
    # 1. Content 조회
    content = db.query(Content).filter(Content.id == content_id).first()
    
    # 2. 빈 필드 탐지 (synopsis, cast, director)
    target_fields = []
    if not content.metadata.synopsis or content.metadata.synopsis.strip() == "":
        target_fields.append("synopsis")
    
    # 3. WebSearch 실행
    search_query = f"{content.title} {content.production_year} 시놉시스"
    results, provider = search_with_fallback(search_query, db, num=5)
    
    # 4. 필드별 LLM 추출
    for field_name in target_fields:
        _create_websearch_suggestion(content_id, field_name, results, db)
```

### _create_websearch_suggestion 로직

```python
def _create_websearch_suggestion(content_id, field_name, results, db):
    snippet = " ".join(r.snippet for r in results[:3])[:500]
    
    # Field별 프롬프트
    if field_name == "synopsis":
        prompt = f"웹 검색 결과에서 시놉시스 2~3문장:\n{snippet}"
    
    # LLM 추출 (Gemini→Groq→Ollama)
    extracted = llm.generate(prompt)
    
    # FieldSuggestion 생성
    suggestion = FieldSuggestion(
        content_id=content_id,
        field_name=field_name,
        value_json=extracted,
        source_type=ExternalSourceType.websearch,
        confidence_score=0.5,  # Phase C 정책
        status="pending",
    )
    db.add(suggestion)
    db.flush()
```

### bulk_accept 엔드포인트

```
POST /api/meta-core/contents/{content_id}/resolutions/bulk-accept
{
  "fields": ["synopsis", "cast"],
  "enable_web_search": true  # 신규 필드
}

검증:
1. enable_web_search=true 시 check_bulk_allowed("brave", expected=2, limit=60)
2. Guard fail → 422 BulkQuotaError
3. Guard pass → aggregate_content(content_id, db, enable_web_search=true)
```

## 특징

- **기본 OFF**: enable_web_search=False (명시적 opt-in만 호출)
- **Confidence 0.5**: Phase C 정책 (낮음, 인간 검수 필수)
- **Bulk guard**: 예상 호출 수 사전 체크 (50% safety margin)
- **Fallback chain**: Gemini→Groq→Ollama (최소 synopsis 보장)

## Verify 체크

```bash
bash .claude/verify.sh phase-d-step6
```

- ✓ aggregator.py enable_web_search 파라미터
- ✓ aggregate_batch enable_web_search 파라미터
- ✓ _add_websearch_suggestions, _create_websearch_suggestion 함수
- ✓ BulkAcceptRequest.enable_web_search 필드
- ✓ bulk_accept check_bulk_allowed 가드
- ✓ test_aggregator_websearch.py 존재 (7 케이스)
- ✓ BulkQuotaError → 422 응답

## 다음 스텝
D.7 — Monitoring API (3 GET endpoints)

## 참고
- WebSearch confidence: 0.50 (Phase C와 동일)
- Bulk safety margin: 50% (expected > remaining * 0.5 → reject)
- Default: opt-in only (enable_web_search=false가 기본)
