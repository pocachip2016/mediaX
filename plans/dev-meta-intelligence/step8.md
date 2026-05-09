# Step 8: resolution-api

> GitHub: 미생성 | Milestone: dev-meta-intelligence (Phase B — 골격, B 진입 시점에 상세화)

## 읽어야 할 파일
- `backend/api/meta_core/models/intelligence.py`
- `backend/api/meta_core/router.py` (현재 라우터 마운트)
- `backend/api/programming/metadata/router.py` (REST 컨벤션)

## 목적
검수 UI 가 호출할 REST 엔드포인트. **읽기 전용** 위주, 쓰기는 다음 step9.

## 작업 (윤곽)

엔드포인트 (모두 prefix `/api/meta-core`):

| 메서드 | 경로 | 응답 | 비고 |
|---|---|---|---|
| GET | `/contents/{id}/gap` | GapReport | step4 호출 결과 |
| GET | `/contents/{id}/resolutions` | `{auto: [...], pending: [...]}` | 자동 확정·검수 대기 분리 |
| GET | `/contents/{id}/resolutions/{field}` | FieldResolution + 후보 suggestion 목록 | 검수 카드 1장 |
| GET | `/contents/{id}/match-edges` | MatchEdge 목록 (decided / undecided) | 매칭 검토 |
| GET | `/queue/resolutions?decision=pending` | 페이지네이션 검수 큐 | 콘텐츠 cross-cut |

스키마는 `meta_core/public_api/schemas.py` 가 아닌 별도 `meta_core/intelligence/schemas.py` 로 분리 (Dam 용 public API 와 섞이지 않게).

## Acceptance Criteria
```bash
# Swagger 등록 확인
curl -s http://localhost:8000/openapi.json | python3 -c "
import json, sys
d = json.load(sys.stdin)
paths = list(d['paths'].keys())
for p in ['/api/meta-core/contents/{id}/gap',
         '/api/meta-core/contents/{id}/resolutions',
         '/api/meta-core/queue/resolutions']:
    assert any(p.replace('{id}','{content_id}') in x or p in x for x in paths), p
print('OK')
"
pytest backend/tests/meta_core/test_resolution_api.py
bash .claude/verify.sh meta-intelligence-step8
```

## 금지사항
- **이 step 에서 쓰기 엔드포인트 추가 금지.** GET 만.
  이유: 읽기 안정화 후 step9 에서 쓰기.
- **Dam public_api 라우터에 합치지 마라.** 의도된 외부 인터페이스가 다름.
  이유: public_api 는 read-only export, intelligence 는 검수자 전용.
