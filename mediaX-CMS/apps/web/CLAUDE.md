# mediaX-CMS/apps/web/ — Next.js 16 프론트엔드

## 실행
```bash
# 루트(mediaX-CMS/)에서
nvm use 22   # Node 22 필수 (v14에서는 실행 안 됨)
npm run dev  # turbo dev → http://localhost:3000 (또는 3002)

# 앱 단독 실행
cd apps/web && npm run dev
```

## 디렉토리 구조
```
apps/web/
├── app/
│   ├── layout.tsx              # 루트 레이아웃 (ThemeProvider)
│   ├── page.tsx                # / → /programming/contents 리다이렉트
│   └── (main)/                 # 메인 레이아웃 그룹 (사이드바 + 헤더)
│       ├── layout.tsx          # SidebarProvider + AppSidebar + SidebarInset
│       └── programming/
│           └── metadata/
│               ├── page.tsx        # 메타 대시보드
│               ├── queue/page.tsx  # 검수 큐
│               └── create/page.tsx # 실시간 메타 생성
├── components/layout/
│   ├── sidebar.tsx             # AppSidebar (docsNav 기반 동적 렌더링)
│   └── header.tsx              # 브레드크럼 + 다크모드 토글
├── config/
│   ├── docs.ts                 # 전체 네비게이션 트리 (NavSection[])
│   └── site-config.ts          # 앱 메타 설정
├── lib/
│   ├── nav.ts                  # getBreadcrumbs, getActiveNav, getPagerLinks
│   └── api.ts                  # FastAPI 백엔드 클라이언트 + 타입
└── public/
    └── kt-alpha-logo.svg
```

## API 연결
`lib/api.ts`의 `BASE` URL:
- 기본: `http://localhost:8000`
- 환경변수: `NEXT_PUBLIC_API_URL`

모든 페이지는 **Mock 데이터 폴백** 포함 — 백엔드 없이도 UI 확인 가능.

## 알려진 주의사항
- Tailwind v4: CSS 변수 참조 클래스(`w-[--sidebar-width]`) 동적 적용 안 됨 → 인라인 style 사용
- 사이드바 너비: `sidebar.tsx`의 `SIDEBAR_WIDTH`, `SIDEBAR_WIDTH_ICON` 상수로 관리
- 포트 충돌 시 자동으로 3002 등 다음 포트 사용
