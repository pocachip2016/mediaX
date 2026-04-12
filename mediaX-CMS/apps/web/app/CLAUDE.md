# apps/web/app/ — Next.js App Router 페이지

## 레이아웃 계층

```
app/
├── layout.tsx          # 루트: Geist 폰트, ThemeProvider, globals.css import
├── page.tsx            # / → /programming/contents 리다이렉트
└── (main)/             # 라우트 그룹: AppSidebar + Header 레이아웃
    ├── layout.tsx      # SidebarProvider + AppSidebar + SidebarInset
    ├── programming/    # 편성 기획 AX
    ├── design/         # 디자인 AX
    ├── ingest/         # 인제스트 AX
    ├── analytics/      # 통계 AX
    ├── marketing/      # 마케팅 AX
    └── monitoring/     # 모니터링 AX
```

## 구현된 페이지 (22개)

| 경로 | 상태 |
|------|------|
| `/programming/metadata` | ✅ 구현 완료 |
| `/programming/metadata/queue` | ✅ 구현 완료 |
| `/programming/metadata/create` | ✅ 구현 완료 |
| `/programming/contents` | 스텁 |
| `/programming/schedule` | 스텁 |
| `/programming/tmdb` | 스텁 |
| `/design/assets`, `/design/generate`, `/design/batch` | 스텁 |
| `/ingest/receive`, `/ingest/encoding`, `/ingest/qc` | 스텁 |
| `/analytics/viewing`, `/analytics/revenue`, `/analytics/settlement` | 스텁 |
| `/marketing/promotion`, `/marketing/crm`, `/marketing/ad` | 스텁 |
| `/monitoring/incidents`, `/monitoring/quality`, `/monitoring/security` | 스텁 |

## 새 페이지 추가 패턴

1. `config/docs.ts`의 `NavSection[]`에 항목 등록
2. `app/(main)/<섹션>/<항목>/page.tsx` 파일 생성
3. 사이드바는 자동으로 반영됨 (별도 sidebar 수정 불필요)

## 주의
- `(main)` 라우트 그룹은 URL에 포함되지 않음
- 모든 페이지에 Mock 데이터 폴백 포함 — 백엔드 없이 UI 확인 가능
- API 연결: `lib/api.ts` 참조
