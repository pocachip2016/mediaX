# apps/web/components/ — React 컴포넌트

## 구조
```
components/
├── layout/
│   ├── sidebar.tsx     # AppSidebar — 전체 사이드바 (docsNav 기반)
│   └── header.tsx      # 헤더 — 브레드크럼 + 다크모드 토글
└── theme-provider.tsx  # next-themes ThemeProvider 래퍼
```

## layout/sidebar.tsx
- `docsNav` (config/docs.ts)에서 네비게이션 자동 생성 — 하드코딩 없음
- `SECTION_ICONS`: base path → LucideIcon 매핑
- 로고: 축소 시 "MX" 배지, 확장 시 "MediaX" + KT alpha 로고
- `NavGroup`: Collapsible 섹션, 클릭으로 토글

## layout/header.tsx
- `getBreadcrumbs(pathname)` → SidebarTrigger 옆에 렌더링
- key: `${i}-${crumb.href}` (중복 href 방지)
- 다크모드: `useTheme()` + Moon/Sun 아이콘

## 새 레이아웃 컴포넌트 추가 시
`(main)/layout.tsx`의 `<SidebarInset>` 내부에 배치.
공유 UI 컴포넌트는 `packages/ui/src/components/`에 추가.
