# Step 9: review-backend

> GitHub: 미생성 | Milestone: dev-meta-intelligence (Phase B — 골격, B 진입 시점에 상세화)

## 읽어야 할 파일
- `backend/api/meta_core/aggregator.py` (step7 — manual 결정도 같은 적용 경로 재사용)
- step8 의 GET 엔드포인트들

## 목적
검수자가 pending FieldResolution 을 처리하는 쓰기 API. accept / pick / merge / reject.

## 작업 (윤곽)

| 메서드 | 경로 | 동작 |
|---|---|---|
| POST | `/contents/{id}/resolutions/{field}/accept` | auto 결정 그대로 확정 (이미 applied 면 no-op) |
| POST | `/contents/{id}/resolutions/{field}/pick` | body: `{suggestion_id}` — 1개 선택, decision=manual_pick, applied_to_content=true |
| POST | `/contents/{id}/resolutions/{field}/merge` | body: `{suggestion_ids: [...], method: "union"|"llm_merge"}` — C 분류 전용 |
| POST | `/contents/{id}/resolutions/{field}/reject` | decision=rejected, applied_to_content=false (값 제거) |
| POST | `/contents/{id}/resolutions/bulk-accept` | body: `{fields: [...]}` — 일괄 confirm |

LLM merge 처리:
- `meta_core/aggregator.py:llm_merge_synopses(values: list[str]) -> str` 추가 (검수 시점에만 호출)
- ai_engine 의 폴백 체인 재사용 (Gemini → Groq → Ollama)
- 호출당 비용 가시화: `external_sync_log` 에 `external_source=llm_merge` 1행 기록

audit:
- 모든 쓰기는 `decided_by` 에 username (인증 미들웨어가 있으면), `decided_at` 자동
- 변경 이력은 별도 테이블 만들지 않음 (FieldResolution row 하나가 audit 그 자체)

## Acceptance Criteria
```bash
pytest backend/tests/meta_core/test_review_backend.py
# manual pick → ContentMetadata 반영 확인
# reject → ContentMetadata 에서 제거 확인
# llm_merge → external_sync_log 행 1개 추가 확인
bash .claude/verify.sh meta-intelligence-step9
```

## 금지사항
- **Aggregator 우회 금지.** 모든 쓰기는 aggregator 의 적용 함수를 통해 ContentMetadata 변경.
  이유: 단일 적용 경로 — 검증·롤백 일관성.
- **LLM 자동 호출 금지.** merge 는 검수자가 명시 요청한 경우만.
  이유: ADR §7 비용 가드.
- **bulk-accept 에 reject 포함 금지.** accept 만.
  이유: 무심코 일괄 reject 위험. reject 는 항상 1건씩 사유와 함께.
