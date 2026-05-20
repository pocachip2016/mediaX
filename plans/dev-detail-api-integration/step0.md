# Step 0: dai-adr (Phase A)

> Milestone: dev-detail-api-integration

## 작업
콘텐츠 상세 API 호출 실패 원인 진단 + 해결 방향 ADR-004 작성.

## 진단 결과
- 백엔드: `GET /api/programming/metadata/contents/1201` ✅ 200 OK (curl)
- 브라우저: CORS preflight `OPTIONS` ❌ 400 Bad Request
- 원인: `backend/main.py` `allow_origins`에 `localhost:3003` 누락 (3000~3002, 4000만 허용)
- 영향: 프론트 dev 서버가 3000 포트 사용 불가 시 자동 fallback → 차단

## 산출
- `docs/dev/dev-detail-api-integration/adr-004-api-integration.md`
- `plans/dev-detail-api-integration/index.json`
- `plans/dev-detail-api-integration/step0.md`

## Acceptance Criteria
```bash
/verify --skip "doc-only ADR + plan skeleton step"
```

## 금지사항
- 코드 수정 금지. Step 0 은 분석/설계 전용.
