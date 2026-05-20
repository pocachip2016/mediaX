# ADR-003 — Content Detail Unified Shell

- **Status**: Proposed (2026-05-20)
- **Phase**: dev-detail-unified-shell / Step 0
- **Related**: ADR-001 (content_kind routing), ADR-002 (pipeline test console)

## Context

콘텐츠 상세 흐름이 3개 페이지로 분리돼 일관성을 잃음:

| 경로 | 레이아웃 | 문제 |
|---|---|---|
| `/contents/[id]` | DetailLeafLayout + 6탭 + 추천 토글 | 추천이 우측 토글로 가려져 있음 |
| `/contents/[id]/edit` | max-w-2xl 좁은 폼 | 콘텐츠 컨텍스트(포스터·식별) 사라짐 |
| `/contents/[id]/recommend` | StickyActionBar + 7개 신규 컴포넌트 | view 와 완전히 다른 레이아웃 |

같은 콘텐츠를 보는데 모드 전환 시 시선이 점프하고, 좌측 현재 상태가 보존되지 않음.

## D1 — Unified Shell 결정

좌측은 모드 불문 동일 (현재 상태), 우측은 `?mode=view|edit|review` 에 따라 패널 교체.

```
┌── Header (모드 토글: ◉보기 ○편집 ○검수) ────────────────────┐
└──────────────────────────────────────────────────────────────┘
┌─ 좌측 ~40% ──────────────┐ ┌─ 우측 ~60% — 모드별 ──────────┐
│ [포스터 240×340]          │ │ [A] 포스터 안내/편집/점검     │
│ [후보 썸네일 60×90 ×N]    │ │ [B] 시놉시스 추천/편집/점검   │
│ [식별 정보]               │ │ [C] 메타 필드 추천/편집/점검  │
│ [시놉시스 (좁은 폭)]      │ │ [D] Footer (편집·검수만)      │
│ [6필드 (1열)]             │ │                               │
│ [Accordion]               │ │                               │
│ [Children (container만)]  │ │                               │
└──────────────────────────┘ └───────────────────────────────┘
```

**우측 모드 불문 5슬롯 [A][B][C][D][E]** 항상 같은 위치 — 모드 토글 시 레이아웃 점프 없음.

## D2 — 우측 모드별 컨텐츠

| 슬롯 | [보기] | [편집] | [검수] |
|---|---|---|---|
| [A] 포스터 | primary 안내 | URL 입력 / 후보 선택 | needs_sel 점검 |
| [B] 시놉시스 | AI 통합 + 원본 비교 | textarea + 추천 가져오기 | conflict 점검 |
| [C] 메타 필드 | 필드별 추천 + 적용 | 필드별 input | 필드별 상태 + Bulk Guard |
| [D] Footer | (없음) | 저장/취소 | 검수자·메모·승인/반려 |

좌측 변경(예: 시놉시스 출처 토글 ●CP→○TMDB) → 우측 추천 카드의 "원본 비교"에서 해당 소스 하이라이트.

## D3 — URL 매핑

| 기존 | 신규 |
|---|---|
| `/contents/[id]` | `/contents/[id]?mode=view` (default) |
| `/contents/[id]/edit` | `/contents/[id]?mode=edit` (redirect from `/edit`) |
| `/contents/[id]/recommend` | `/contents/[id]?mode=review` (redirect from `/recommend`) |
| `/contents/review` | 유지 — 행 클릭 시 `?mode=review&return=review` |

기존 URL 들은 `redirect()` 로 호환 유지.

## D4 — 컴포넌트 트리

```
<ContentDetailPage> (/contents/[id]/page.tsx)
├── <DetailHeader/>          (신규 — 브레드크럼+상태+모드토글+액션바)
├── <ContentShell>           (신규 — 좌측 컬럼)
│   ├── <PosterCard/>         (재사용 - PosterRow 단순화)
│   ├── <PosterCandidates/>   (신규 - 60×90 thumb row)
│   ├── <IdentityCard/>       (신규)
│   ├── <SynopsisCard/>       (신규 - 출처 토글 포함)
│   ├── <MetaFieldsList/>     (신규 - 1열 그리드)
│   ├── <SecondaryAccordion/> (재사용)
│   └── <ChildrenTable/>      (재사용 — container 만)
└── <ModePane mode={mode}>    (신규 라우터)
    ├── <ViewPane/>            (신규 [A][B][C])
    ├── <EditPane/>            (신규 [A][B][C][D])
    └── <ReviewPane/>          (신규 [A][B][C][D])
```

## D5 — 재사용 / 신규 매트릭스

| 자산 | 위치 | 재사용 / 신규 |
|---|---|---|
| `MetadataDiffPanel` | components/contents/ | 재사용 → ViewPane [C] 흡수 |
| `MetadataEnrichPanel` | components/contents/ | 재사용 → ViewPane [B] AI 통합 영역 |
| `ContentForm` | components/contents/ | 재사용 → EditPane [B][C] 분해 |
| `ShortMetaGrid` | recommend/ | 재사용 → MetaFieldsList 로 (좌측 read-only) |
| `SynopsisRow` | recommend/ | 분해 → 좌측 SynopsisCard + 우측 [B] |
| `PosterRow` | recommend/ | 분해 → 좌측 PosterCard + 좌측 PosterCandidates |
| `SecondaryAccordion` | recommend/ | 재사용 (이동) |
| `StickyActionBar` | recommend/ | 재사용 → DetailHeader 흡수 |
| `useContentReviewActions` | hooks/ | 재사용 (ReviewPane) |
| **신규**: `ContentShell` | shell/ | 좌측 layout 컨테이너 |
| **신규**: `DetailHeader` | shell/ | 모드 토글 포함 |
| **신규**: `ViewPane` | panes/ | [A][B][C] 슬롯 |
| **신규**: `EditPane` | panes/ | [A][B][C][D] 슬롯 |
| **신규**: `ReviewPane` | panes/ | [A][B][C][D] 슬롯 |

## D6 — Step 계획 (8 step)

| Step | 이름 | Phase | 범위 | 모델 |
|---|---|---|---|---|
| 0 | dus-adr | A | ADR + plan skeleton | Opus |
| 1 | dus-shell-extract | B | ContentShell 좌측 컬럼 분리 | Sonnet |
| 2 | dus-view-pane | C | ViewPane [A][B][C] 추천 패널 | Sonnet |
| 3 | dus-edit-pane | C | EditPane 4슬롯 + `/edit` redirect | Sonnet |
| 4 | dus-review-pane | C | ReviewPane 4슬롯 + `/recommend` redirect | Sonnet |
| 5 | dus-mode-routing | D | `?mode=` URL + 모드 토글 | Sonnet |
| 6 | dus-queue-integration | D | review 큐 행 클릭 → `?mode=review` | Sonnet |
| 7 | dus-wrap | E | TODO/CLAUDE.md + verify.sh | Haiku |

각 step 끝에서 STOP + 모델 전환 안내 (CLAUDE.md Model Switch Protocol).

## D7 — Out of Scope

- 시리즈/시즌/에피소드 hierarchy 변경 — ADR-001 그대로 유지
- 검수 큐 테이블 자체 재설계 — review/page.tsx 행 클릭 URL 만 변경
- 권한/역할 시스템 — 기존 admin 가정
- 모바일 반응형 — 데스크탑 우선, follow-up

## D8 — Acceptance Criteria

- 좌측 7요소 모두 ContentShell 안에서 렌더
- 우측 3 모드(view/edit/review) 전환 시 [A][B][C] 슬롯이 같은 위치
- `/contents/[id]` (default view) / `/edit` / `/recommend` 3 URL 모두 동작 (redirect 포함)
- `npm run typecheck` pass
- 검수 큐 행 클릭 시 `?mode=review&return=review` 로 이동

## 참고

- 기존 ADR-001 의 leaf/container 분기는 ContentShell 내부에서 그대로 처리
- ADR-002 의 Pipeline Test Console 흐름과 연계 — 검수 큐 → ?mode=review 통합
