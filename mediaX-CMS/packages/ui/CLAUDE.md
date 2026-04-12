# packages/ui/ — @workspace/ui 공유 컴포넌트 라이브러리

## 역할
`apps/web`과 향후 추가될 앱들이 공유하는 shadcn/ui 기반 컴포넌트 패키지.

## 구조

```
packages/ui/
├── src/
│   ├── components/   # shadcn/ui 컴포넌트 (button, badge, sidebar, input 등)
│   ├── hooks/        # use-mobile.ts
│   ├── lib/
│   │   └── utils.ts  # cn() 유틸 (clsx + tailwind-merge)
│   └── styles/
│       └── globals.css  # Tailwind v4 + OKLch CSS 변수 (라이트/다크)
├── components.json   # shadcn CLI 설정
└── package.json      # exports: ./components/*, ./hooks/*, ./lib/*, ./globals.css
```

## 컴포넌트 추가

```bash
cd packages/ui
npx shadcn@latest add <component>
```

`apps/web/components.json`이 아닌 **이 패키지**에 추가해야 한다.

## 주요 패턴

- **`cn()`**: 모든 className 조합에 사용 (`import { cn } from "@workspace/ui/lib/utils"`)
- **CVA**: 컴포넌트 variants는 `class-variance-authority` 사용
- **Tailwind v4**: CSS 변수는 OKLch 색상 공간 (`--background`, `--foreground` 등)
- `globals.css`는 `apps/web/app/layout.tsx`에서 `@workspace/ui/globals.css`로 import됨

## Path alias
`apps/web`에서: `@workspace/ui/components/<name>`, `@workspace/ui/lib/utils`, `@workspace/ui/globals.css`
