# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All commands should be run from the repo root unless otherwise noted.

```bash
# Development
npm run dev          # Start all apps (Turbopack)

# Build & type checking
npm run build        # Build all apps/packages
npm run typecheck    # TypeScript type checking across workspace

# Code quality
npm run lint         # ESLint across workspace
npm run format       # Prettier across workspace
```

To run a command scoped to a single package:
```bash
cd apps/web && npm run dev      # Run Next.js dev server only
cd packages/ui && npm run lint  # Lint only the UI package
```

There are no test commands configured yet.

## Architecture

This is a **Turbo monorepo** with npm workspaces:

```
apps/web/       — Next.js 15 application (App Router)
packages/ui/    — Shared shadcn/ui component library
packages/typescript-config/  — Shared tsconfig bases
packages/eslint-config/      — Shared ESLint configs
```

### Key Patterns

**Shared UI Package (`@workspace/ui`)**: Components live in `packages/ui/src/components/`. New shadcn/ui components should be added here, not in `apps/web/`. The package exports components, hooks, `globals.css`, and the PostCSS config via `package.json` exports.

**Styling**: Tailwind CSS v4 with CSS custom properties in OKLch color space. The `cn()` utility (`packages/ui/src/lib/utils.ts`) combines `clsx` + `tailwind-merge` and should be used for all className composition. Component variants use `class-variance-authority` (CVA).

**Path aliases**:
- `@/*` → `apps/web/*` (local web app files)
- `@workspace/ui/*` → `packages/ui/src/*` (shared library)

**Theme**: Dark/light mode via `next-themes`. The `ThemeProvider` wraps the app in `apps/web/components/theme-provider.tsx`. The `globals.css` defines separate `:root` and `.dark` variable blocks.

**TypeScript**: Strict mode with `noUncheckedIndexedAccess` enabled. All packages extend from `packages/typescript-config/`.

**ESLint**: Flat config format (v9+). Root `.eslintrc.js` handles ignores. Each package has its own `eslint.config.js` extending from `packages/eslint-config/`.

### Adding shadcn/ui Components

Components are added to `packages/ui`, not `apps/web`. Run from `packages/ui`:
```bash
npx shadcn@latest add <component>
```
After adding, ensure the component is re-exported from the package exports if needed.
