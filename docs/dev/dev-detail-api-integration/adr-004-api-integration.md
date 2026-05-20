# ADR-004 — Content Detail API Integration

- **Status**: Proposed (2026-05-20)
- **Phase**: dev-detail-api-integration / Step 0
- **Related**: ADR-003 (unified shell)

## Context

ADR-003 통합 shell 완료 후, Review Queue → 상세 페이지 진입 시 "콘텐츠를 찾을 수 없습니다." 발생.

### 진단 결과

| 항목 | 상태 |
|---|---|
| 백엔드 health | ✅ 200 OK |
| `GET /api/programming/metadata/contents/1201` (curl) | ✅ 200 OK + 전체 데이터 |
| `OPTIONS` preflight (Origin: `http://localhost:3003`) | ❌ **400 Bad Request** |
| 응답에 `access-control-allow-origin` 헤더 | ❌ 없음 |
| 백엔드 CORS 허용 목록 | `3000, 3001, 3002, 4000` (3003 없음) |
| 프론트 dev 서버 실행 포트 | **3003** (3000 사용 중 → 자동 fallback) |

### 근본 원인

`backend/main.py`의 `CORSMiddleware.allow_origins` 가 `localhost:3000~3002` 만 허용.
프론트가 3003 포트로 fallback 시 CORS preflight 실패 → 브라우저가 모든 API 호출 차단.

콘텐츠 상세 페이지 (`[id]/page.tsx`)는 mock fallback 없음 → `content === null` → "찾을 수 없습니다."

## D1 — 해결 방향

| 옵션 | 장점 | 단점 |
|---|---|---|
| A. 백엔드 CORS 확장 (3003 추가) | 즉시 해결, 영구 | 포트 별 하드코딩 |
| B. CORS regex 패턴 (`localhost:\d+`) | 모든 dev 포트 자동 허용 | 운영 환경 별도 설정 필요 |
| C. 프론트 dev 서버 3000 고정 | 백엔드 변경 없음 | 매번 3000 비워야 함 |
| D. 상세 페이지에 mock fallback 추가 | 백엔드 없이도 동작 | 데이터 일관성 ↓ |

**선택**: **B (regex 패턴)** + **D (mock fallback)** 병행.
- B: 근본 해결, dev 환경 안정화
- D: API 장애 시에도 UI 동작 보장 (Review Queue 와 동일 패턴)

## D2 — 변경 범위

**Backend**:
- `backend/main.py` — `allow_origins` → `allow_origin_regex=r"http://localhost:\d+"` 전환
- 운영 환경 분기 (env-based)

**Frontend**:
- `[id]/page.tsx` — `getContent` 실패 시 mock content 폴백 + `isMock` 배지
- mock 데이터는 `lib/mockContent.ts` 별도 분리 (재사용 가능)

## D3 — Step 계획 (5 step)

| Step | 이름 | Phase | 범위 | 모델 |
|---|---|---|---|---|
| 0 | dai-adr | A | ADR + 진단 + plan skeleton | Opus |
| 1 | dai-cors-regex | B | backend CORS regex 전환 + 환경 분기 | Sonnet |
| 2 | dai-mock-content | C | lib/mockContent.ts + 페이지 fallback | Sonnet |
| 3 | dai-e2e-verify | D | Review Queue → 상세 진입 E2E 확인 | Sonnet |
| 4 | dai-wrap | E | TODO/CLAUDE.md + verify.sh | Haiku |

## D4 — Out of Scope

- 운영 환경 CORS 정책 (별도 ADR)
- 인증/세션 처리 (현재 admin 가정)
- 상세 페이지 다른 API 호출 (poster, dam, image meta 등) — Step 2 에서 동일 패턴 일괄 적용

## D5 — Acceptance Criteria

- `curl -X OPTIONS -H "Origin: http://localhost:3003" ...` → 200 OK
- Review Queue 행 클릭 → 콘텐츠 상세 페이지에 실제 데이터 표시
- API 차단 시 mock fallback 동작 (isMock 배지)
- `npm run typecheck` pass
