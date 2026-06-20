### Task 5 Report: shadcn/ui Init + Base Components

**Status: COMPLETE**

#### Step 1: Initialize shadcn/ui
- Ran `npx shadcn@latest init --defaults --force` in `frontend/`
- Style: base-nova (New York equivalent)
- Base color: Neutral
- CSS variables: Yes
- Created: `components.json`, `components/ui/button.tsx`, `lib/utils.ts`

#### Step 2: Restore OLED Tokens
shadcn init overwrote several OLED variables in `globals.css` with oklch light-mode defaults:
- `--background`: restored from white to `#020617`
- `--foreground`: restored from near-black to `#F8FAFC`
- `--primary`: restored from near-black to `#FB923C` (orange)
- `--destructive`: restored from oklch to `#DC2626`

shadcn CSS variables were mapped to OLED theme values:
- `--card` / `--popover` / `--secondary` / `--muted` / `--accent` mapped to OLED surface layers
- `--border` / `--input` mapped to `--border-default` (`#272F42`)
- `--ring` mapped to `--primary` (`#FB923C`)
- Chart and sidebar variables mapped to OLED semantic colors

Kept all shadcn directives: `@import "tw-animate-css"`, `@import "shadcn/tailwind.css"`, `@custom-variant dark`, `@theme inline`, and `@layer base`.

Both `:root` and `.dark` use identical OLED dark theme values (the app is always dark).

#### Step 3: Install Base Components
Installed 18 components (17 new, 1 skipped as identical):
button, card, input, label, separator, badge, sonner, table, tabs, dropdown-menu, dialog, select, textarea, scroll-area, popover, tooltip, command, input-group

Note: Used `sonner` instead of deprecated `toast`.

#### Step 4: ThemeProvider
Created `components/ui/theme-provider.tsx` — a client component that sets `document.documentElement.lang` from locale prop, enabling the `[lang="zh"]` CSS selector for red/green direction swap.

#### Verification
- Next.js build: CSS compiles successfully
- TypeScript: 1 pre-existing error in `lib/api-client.ts` (from Tasks 1-4, not related to shadcn setup)
- All 18 components present in `components/ui/`

#### Files Changed
- `frontend/app/globals.css` — updated (OLED tokens restored + shadcn integration)
- `frontend/components.json` — created (shadcn config)
- `frontend/lib/utils.ts` — created (cn utility)
- `frontend/components/ui/*.tsx` — 18 component files created
- `frontend/components/ui/theme-provider.tsx` — created

## Fix Report (2026-06-20)

**Commit:** `c0c4bd4` — `fix(frontend): remove dead radius CSS, restore format utilities`

### Issue 1: Dead radius declarations in `:root`
Lines `--radius-sm: 4px; --radius-md: 6px; --radius-lg: 8px; --radius-xl: 12px;` in the `:root` block of `globals.css` were dead code. The `@theme inline` block (lines 154-157) defines the same properties via `calc(var(--radius) * X)`, which wins the cascade. Removed the 4 lines; `--radius: 0.5rem` is preserved as the seed value for shadcn's computed radii.

### Issue 2: Lost format utilities in `lib/utils.ts`
shadcn init overwrote `lib/utils.ts`, discarding 6 utility functions from Task 3: `formatPrice`, `formatPercent`, `formatVolume`, `formatPnL`, `formatDateTime`, `colorForChange`. Merged by keeping shadcn's `cn()` (which uses `clsx` + `tailwind-merge` — same as the original) and appending all 6 restore functions. No code changes made to the function signatures.

**Files modified:**
- `frontend/app/globals.css` — removed 4 dead `--radius-*` lines from `:root`
- `frontend/lib/utils.ts` — restored 6 format/color utility functions after `cn()`
