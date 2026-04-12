# apps/web/config/ — 앱 설정·네비게이션

## 파일

| 파일 | 역할 |
|------|------|
| `docs.ts` | 전체 네비게이션 트리 (`NavSection[]`) |
| `site-config.ts` | 앱 이름·설명·버전·기본 경로·외부 링크 |

## docs.ts — 네비게이션 구조

`NavSection[]` 타입: 6개 AX 섹션 × 3개 항목 = 18개 nav 항목

```
Programming  → contents, metadata, schedule
Design       → assets, generate, batch
Ingest       → receive, encoding, qc
Analytics    → viewing, revenue, settlement
Marketing    → promotion, crm, ad
Monitoring   → incidents, quality, security
```

`sidebar.tsx`가 이 구조를 읽어 사이드바를 동적으로 렌더링함.  
새 AX 항목 추가 시 여기에 먼저 등록 → `app/(main)/` 에 페이지 파일 추가.

## 주의
- 섹션 아이콘은 `components/layout/sidebar.tsx`의 `SECTION_ICONS` 매핑에서 관리
- `site-config.ts`의 `defaultPath`는 루트 리다이렉트(`app/page.tsx`)에서 사용됨
