# Frontend Coinbase 机构风重设计 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 AStockPursue 前端从 OLED 暗黑 + 橙色主题，重构为 Coinbase 机构级纯白画布 + 蓝色 primary 金融服务风格

**Architecture:** 原子→分子→页面逐层推进。先改 CSS tokens 和字体，再改 19 个 shadcn/ui 基础组件，再改布局和 17 个金融组件，最后适配 27 个页面

**Tech Stack:** Next.js 15 (App Router), Tailwind CSS v4, shadcn/ui (Base UI), Inter + JetBrains Mono, next-intl

## Global Constraints

- 禁止 box-shadow 做层次 — 只用 surface 色块 + hairline border
- 单一品牌色 `#0052FF` — 不引入第二个 accent color
- display 标题用 400 weight，不用 700 bold
- 所有价格/数量/百分比用 JetBrains Mono `tabular-nums`
- 按钮圆角 ≤ 6px（`--radius: 0.375rem`）
- 中文本地化：红涨绿跌 (`[lang="zh"]` 翻转 up/down)
- 每次 commit 后 `cd frontend && npx next build` 通过

---

### Task 1: CSS Tokens — globals.css 完整重写

**Files:**
- Modify: `frontend/app/globals.css`

**Interfaces:**
- Produces: All CSS custom properties consumed by every component — `--primary`, `--background`, `--foreground`, `--surface-1/2/3`, `--up`, `--down`, `--radius`, `--border`, all shadcn mapped tokens, `--sidebar-width`, `--header-height`, `--grid-gap`, `--card-padding`, `--page-padding`, `--font-sans`, `--font-body`, `--font-mono`

- [ ] **Step 1: Write the new globals.css**

Replace the entire file content:

```css
/* frontend/app/globals.css */
@import "tailwindcss";
@import "tw-animate-css";
@import "shadcn/tailwind.css";

@custom-variant dark (&:is(.dark *));

/* ---- Coinbase Institutional Theme Tokens ---- */
:root {
  /* Surface layers — light canvas */
  --background: #FFFFFF;
  --foreground: #0A0B0D;
  --card: #FFFFFF;
  --card-foreground: #0A0B0D;
  --popover: #FFFFFF;
  --popover-foreground: #0A0B0D;
  --primary: #0052FF;
  --primary-foreground: #FFFFFF;
  --secondary: #EEF0F3;
  --secondary-foreground: #0A0B0D;
  --muted: #F7F7F7;
  --muted-foreground: #7C828A;
  --accent: #EEF0F3;
  --accent-foreground: #0A0B0D;
  --destructive: #CF202F;
  --destructive-foreground: #FFFFFF;

  /* Borders — hairline-driven */
  --border: #DEE1E6;
  --border-subtle: #EEF0F3;
  --border-default: #DEE1E6;
  --border-strong: #A8ACB3;
  --input: #DEE1E6;
  --ring: #0052FF;

  /* OLED surface aliases — remapped to light hierarchy */
  --surface-1: #F7F7F7;
  --surface-2: #EEF0F3;
  --surface-3: #DEE1E6;

  /* Brand */
  --primary-hover: #003ECC;
  --primary-muted: rgba(0, 82, 255, 0.10);

  /* Semantic — Coinbase precise values */
  --up: #05B169;
  --down: #CF202F;
  --warning: #F4B000;
  --info: #0052FF;

  /* Text */
  --foreground-secondary: #5B616E;
  --foreground-muted: #7C828A;

  /* Layout */
  --sidebar-width: 240px;
  --header-height: 56px;
  --grid-gap: 16px;
  --card-padding: 24px;
  --page-padding: 24px;

  /* Radius — tighter, Coinbase-like */
  --radius: 0.375rem;

  /* Chart */
  --chart-1: #0052FF;
  --chart-2: #05B169;
  --chart-3: #F4B000;
  --chart-4: #CF202F;
  --chart-5: #7C828A;

  /* Sidebar */
  --sidebar: #F7F7F7;
  --sidebar-foreground: #0A0B0D;
  --sidebar-primary: #0052FF;
  --sidebar-primary-foreground: #FFFFFF;
  --sidebar-accent: #EEF0F3;
  --sidebar-accent-foreground: #0A0B0D;
  --sidebar-border: #EEF0F3;
  --sidebar-ring: #0052FF;

  /* Font */
  --font-body: 'Inter', system-ui, -apple-system, sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
  --font-sans: 'Inter', system-ui, -apple-system, sans-serif;
}

/* zh locale — red up / green down (A-share convention) */
[lang="zh"] {
  --up: #CF202F;
  --down: #05B169;
}

/* Base reset */
html, body {
  background: var(--background);
  color: var(--foreground);
  font-family: var(--font-body);
  font-size: 16px;
  line-height: 1.5;
  margin: 0;
  padding: 0;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/* Scrollbar — light minimal */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--background); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--border-strong); }

/* Tabular numbers for data cells */
[data-tabular] { font-variant-numeric: tabular-nums; }

@theme inline {
  --font-heading: var(--font-sans);
  --font-sans: var(--font-sans);
  --color-sidebar-ring: var(--sidebar-ring);
  --color-sidebar-border: var(--sidebar-border);
  --color-sidebar-accent-foreground: var(--sidebar-accent-foreground);
  --color-sidebar-accent: var(--sidebar-accent);
  --color-sidebar-primary-foreground: var(--sidebar-primary-foreground);
  --color-sidebar-primary: var(--sidebar-primary);
  --color-sidebar-foreground: var(--sidebar-foreground);
  --color-sidebar: var(--sidebar);
  --color-chart-5: var(--chart-5);
  --color-chart-4: var(--chart-4);
  --color-chart-3: var(--chart-3);
  --color-chart-2: var(--chart-2);
  --color-chart-1: var(--chart-1);
  --color-ring: var(--ring);
  --color-input: var(--input);
  --color-border: var(--border);
  --color-destructive: var(--destructive);
  --color-accent-foreground: var(--accent-foreground);
  --color-accent: var(--accent);
  --color-muted-foreground: var(--muted-foreground);
  --color-muted: var(--muted);
  --color-secondary-foreground: var(--secondary-foreground);
  --color-secondary: var(--secondary);
  --color-primary-foreground: var(--primary-foreground);
  --color-primary: var(--primary);
  --color-popover-foreground: var(--popover-foreground);
  --color-popover: var(--popover);
  --color-card-foreground: var(--card-foreground);
  --color-card: var(--card);
  --color-foreground: var(--foreground);
  --color-background: var(--background);
  --radius-sm: calc(var(--radius) * 0.6);
  --radius-md: calc(var(--radius) * 0.8);
  --radius-lg: var(--radius);
  --radius-xl: calc(var(--radius) * 1.4);
  --radius-2xl: calc(var(--radius) * 1.8);
  --radius-3xl: calc(var(--radius) * 2.2);
  --radius-4xl: calc(var(--radius) * 2.6);
}

.dark {
  --background: #FFFFFF;
  --foreground: #0A0B0D;
  --card: #FFFFFF;
  --card-foreground: #0A0B0D;
  --popover: #FFFFFF;
  --popover-foreground: #0A0B0D;
  --primary: #0052FF;
  --primary-foreground: #FFFFFF;
  --secondary: #EEF0F3;
  --secondary-foreground: #0A0B0D;
  --muted: #F7F7F7;
  --muted-foreground: #7C828A;
  --accent: #EEF0F3;
  --accent-foreground: #0A0B0D;
  --destructive: #CF202F;
  --destructive-foreground: #FFFFFF;
  --border: #DEE1E6;
  --input: #DEE1E6;
  --ring: #0052FF;
  --sidebar: #F7F7F7;
  --sidebar-foreground: #0A0B0D;
  --sidebar-primary: #0052FF;
  --sidebar-primary-foreground: #FFFFFF;
  --sidebar-accent: #EEF0F3;
  --sidebar-accent-foreground: #0A0B0D;
  --sidebar-border: #EEF0F3;
  --sidebar-ring: #0052FF;
}

@layer base {
  * {
    @apply border-border outline-ring/50;
  }
  body {
    @apply bg-background text-foreground;
  }
  html {
    @apply font-sans;
  }
}
```

- [ ] **Step 2: Verify CSS compiles**

```bash
cd frontend && npx next build 2>&1 | tail -5
```
Expected: build succeeds, no CSS errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/globals.css
git commit -m "feat(frontend): rewrite CSS tokens for Coinbase institutional light theme"
```

---

### Task 2: Font Loading + HTML direction

**Files:**
- Modify: `frontend/app/layout.tsx`

**Interfaces:**
- Consumes: `--font-sans`, `--font-body`, `--font-mono` from Task 1
- Produces: Google Fonts link for Inter + JetBrains Mono; removes `className="dark"` from html

- [ ] **Step 1: Update layout.tsx font links**

Replace the `<head>` font link block (line 22-23):

```tsx
// Replace:
// <link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500&family=Fira+Sans:wght@400;600;700&display=swap" rel="stylesheet" />

// With:
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet" />
```

- [ ] **Step 2: Remove dark mode class from html tag**

Change line 19:

```tsx
// Before:
<html lang={locale} className="dark">

// After:
<html lang={locale}>
```

- [ ] **Step 3: Update Toaster style for light theme**

Replace lines 30-38 (Toaster config):

```tsx
// Before:
<Toaster
  position="bottom-right"
  toastOptions={{
    style: {
      background: 'var(--surface-3)',
      color: 'var(--foreground)',
      border: '1px solid var(--border-default)',
      fontSize: '13px',
    },
  }}
/>

// After:
<Toaster
  position="bottom-right"
  toastOptions={{
    style: {
      background: '#FFFFFF',
      color: '#0A0B0D',
      border: '1px solid #DEE1E6',
      fontSize: '14px',
      fontFamily: 'Inter, system-ui, sans-serif',
    },
  }}
/>
```

- [ ] **Step 4: Verify build**

```bash
cd frontend && npx next build 2>&1 | tail -5
```
Expected: build passes with Inter/JetBrains Mono fonts loaded.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/layout.tsx
git commit -m "feat(frontend): switch fonts to Inter + JetBrains Mono, enable light mode"
```

---

### Task 3: Base Components A — Button, Card, Input

**Files:**
- Modify: `frontend/components/ui/button.tsx`
- Modify: `frontend/components/ui/card.tsx`
- Modify: `frontend/components/ui/input.tsx`

**Interfaces:**
- Consumes: CSS tokens from Task 1
- Produces: Coinbase-styled Button (h-10, 16px/600w, 6px radius), Card (1px border, no ring), Input (h-10, 6px radius)

- [ ] **Step 1: Update button.tsx — size defaults**

Change the `default` size in `buttonVariants` (line 23-24):

```tsx
// Before:
default:
  "h-8 gap-1.5 px-2.5 has-data-[icon=inline-end]:pr-2 has-data-[icon=inline-start]:pl-2",

// After:
default:
  "h-10 gap-2 px-6 has-data-[icon=inline-end]:pr-4 has-data-[icon=inline-start]:pl-4",
```

Change the `lg` size (line 27):

```tsx
// Before:
lg: "h-9 gap-1.5 px-2.5 has-data-[icon=inline-end]:pr-2 has-data-[icon=inline-start]:pl-2",

// After:
lg: "h-11 gap-2 px-8 has-data-[icon=inline-end]:pr-5 has-data-[icon=inline-start]:pl-5",
```

Change the `sm` size (line 26):

```tsx
// Before:
sm: "h-7 gap-1 rounded-[min(var(--radius-md),12px)] px-2.5 text-[0.8rem] in-data-[slot=button-group]:rounded-lg has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-1.5 [&_svg:not([class*='size-'])]:size-3.5",

// After:
sm: "h-8 gap-1.5 rounded-[min(var(--radius-md),12px)] px-4 text-sm in-data-[slot=button-group]:rounded-lg has-data-[icon=inline-end]:pr-2 has-data-[icon=inline-start]:pl-2 [&_svg:not([class*='size-'])]:size-3.5",
```

Add `text-[16px]` to the base cva className (line 7), change `text-sm` to `text-[16px]`:

```tsx
// Before (line 7):
"group/button inline-flex shrink-0 items-center justify-center rounded-lg border border-transparent bg-clip-padding text-sm font-medium ..."

// After:
"group/button inline-flex shrink-0 items-center justify-center rounded-[6px] border border-transparent bg-clip-padding text-[16px] font-semibold ..."
```

- [ ] **Step 2: Update card.tsx — replace ring with border**

Change line 15 (Card className):

```tsx
// Before:
"group/card flex flex-col gap-(--card-spacing) overflow-hidden rounded-xl bg-card py-(--card-spacing) text-sm text-card-foreground ring-1 ring-foreground/10 [--card-spacing:--spacing(4)] has-data-[slot=card-footer]:pb-0 has-[>img:first-child]:pt-0 data-[size=sm]:[--card-spacing:--spacing(3)] data-[size=sm]:has-data-[slot=card-footer]:pb-0 *:[img:first-child]:rounded-t-xl *:[img:last-child]:rounded-b-xl",

// After:
"group/card flex flex-col gap-(--card-spacing) overflow-hidden rounded-[6px] border border-border bg-card py-(--card-spacing) text-sm text-card-foreground [--card-spacing:--spacing(6)] has-data-[slot=card-footer]:pb-0 has-[>img:first-child]:pt-0 data-[size=sm]:[--card-spacing:--spacing(4)] data-[size=sm]:has-data-[slot=card-footer]:pb-0 *:[img:first-child]:rounded-t-[6px] *:[img:last-child]:rounded-b-[6px]",
```

- [ ] **Step 3: Update input.tsx — height and border-radius**

Change line 12 (Input className):

```tsx
// Before:
"h-8 w-full min-w-0 rounded-lg border border-input bg-transparent px-2.5 py-1 text-base transition-colors outline-none file:inline-flex file:h-6 file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:pointer-events-none disabled:cursor-not-allowed disabled:bg-input/50 disabled:opacity-50 aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20 md:text-sm dark:bg-input/30 dark:disabled:bg-input/80 dark:aria-invalid:border-destructive/50 dark:aria-invalid:ring-destructive/40",

// After:
"h-10 w-full min-w-0 rounded-[6px] border border-input bg-background px-4 py-2.5 text-[16px] transition-colors outline-none file:inline-flex file:h-7 file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/50 disabled:pointer-events-none disabled:cursor-not-allowed disabled:bg-muted disabled:opacity-50 aria-invalid:border-destructive aria-invalid:ring-2 aria-invalid:ring-destructive/20",
```

- [ ] **Step 4: Verify build + spot-check visual**

```bash
cd frontend && npx next build 2>&1 | tail -5
```
Expected: build passes.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/ui/button.tsx frontend/components/ui/card.tsx frontend/components/ui/input.tsx
git commit -m "feat(frontend): restyle Button/Card/Input for Coinbase institutional look"
```

---

### Task 4: Base Components B — Badge, Table, Tabs

**Files:**
- Modify: `frontend/components/ui/badge.tsx`
- Modify: `frontend/components/ui/table.tsx`
- Modify: `frontend/components/ui/tabs.tsx`

**Interfaces:**
- Consumes: CSS tokens from Task 1
- Produces: Semitransparent Badge, taller Table rows, underline Tabs

- [ ] **Step 1: Update badge.tsx — semitransparent variants**

Change the `default` and `destructive` variants (lines 12-15):

```tsx
// Before:
default: "bg-primary text-primary-foreground [a]:hover:bg-primary/80",
secondary:
  "bg-secondary text-secondary-foreground [a]:hover:bg-secondary/80",
destructive:
  "bg-destructive/10 text-destructive focus-visible:ring-destructive/20 dark:bg-destructive/20 dark:focus-visible:ring-destructive/40 [a]:hover:bg-destructive/20",

// After:
default: "bg-primary/10 text-primary border-primary/20 [a]:hover:bg-primary/20",
secondary:
  "bg-secondary text-secondary-foreground [a]:hover:bg-muted",
destructive:
  "bg-destructive/10 text-destructive border-destructive/20 focus-visible:ring-destructive/20 [a]:hover:bg-destructive/20",
```

Add success and warning variants to the cva:

```tsx
// Add after the "ghost" variant (before "link"):
success:
  "bg-[rgba(5,177,105,0.10)] text-[#05B169] border-[rgba(5,177,105,0.20)] [a]:hover:bg-[rgba(5,177,105,0.20)]",
warning:
  "bg-[rgba(244,176,0,0.10)] text-[#F4B000] border-[rgba(244,176,0,0.20)] [a]:hover:bg-[rgba(244,176,0,0.20)]",
```

Change the base badge style (line 8) to remove pill radius and adjust height:

```tsx
// Before:
"group/badge inline-flex h-5 w-fit shrink-0 items-center justify-center gap-1 overflow-hidden rounded-4xl border border-transparent px-2 py-0.5 text-xs font-medium ..."

// After:
"group/badge inline-flex h-6 w-fit shrink-0 items-center justify-center gap-1 overflow-hidden rounded-[4px] border px-2 py-0.5 text-xs font-medium ..."
```

- [ ] **Step 2: Update table.tsx — row height and hover**

Read the existing Table component first:

```bash
cat frontend/components/ui/table.tsx
```

Then update TableRow and TableCell to use taller rows:

The key change: TableRow `h-10` (40px) with hairline bottom border, hover `bg-[var(--surface-1)]`.

TableHead: `h-10`, `text-xs font-semibold text-[var(--muted-foreground)]`.

TableCell: `py-3 px-4 text-sm`.

Apply these class changes directly in the table component file. For brevity, the full updated table.tsx should look like:

```tsx
import * as React from "react"
import { cn } from "@/lib/utils"

function Table({ className, ...props }: React.ComponentProps<"table">) {
  return (
    <div data-slot="table-container" className="relative w-full overflow-x-auto">
      <table
        data-slot="table"
        className={cn("w-full caption-bottom text-sm", className)}
        {...props}
      />
    </div>
  )
}

function TableHeader({ className, ...props }: React.ComponentProps<"thead">) {
  return (
    <thead data-slot="table-header" className={cn("[&_tr]:border-b [&_tr]:border-[var(--border-subtle)]", className)} {...props} />
  )
}

function TableBody({ className, ...props }: React.ComponentProps<"tbody">) {
  return (
    <tbody data-slot="table-body" className={cn("[&_tr:last-child]:border-0", className)} {...props} />
  )
}

function TableRow({ className, ...props }: React.ComponentProps<"tr">) {
  return (
    <tr
      data-slot="table-row"
      className={cn(
        "h-10 border-b border-[var(--border-subtle)] transition-colors hover:bg-[var(--surface-1)] data-[state=selected]:bg-[var(--primary-muted)]",
        className
      )}
      {...props}
    />
  )
}

function TableHead({ className, ...props }: React.ComponentProps<"th">) {
  return (
    <th
      data-slot="table-head"
      className={cn(
        "h-10 px-4 text-left align-middle text-xs font-semibold text-[var(--muted-foreground)] [&:has([role=checkbox])]:pr-0",
        className
      )}
      {...props}
    />
  )
}

function TableCell({ className, ...props }: React.ComponentProps<"td">) {
  return (
    <td
      data-slot="table-cell"
      className={cn("px-4 py-3 align-middle text-sm [&:has([role=checkbox])]:pr-0", className)}
      {...props}
    />
  )
}

export { Table, TableHeader, TableBody, TableRow, TableHead, TableCell }
```

- [ ] **Step 3: Update tabs.tsx — underline style**

Read the existing tabs component, then update the trigger to use Coinbase underline style:

```tsx
// Key change for TabsTrigger:
// Active: text-[var(--foreground)] font-semibold + border-b-2 border-[var(--primary)]
// Inactive: text-[var(--muted-foreground)] font-normal + border-b-2 border-transparent
// Padding: px-4 py-2, text-sm
```

Apply the change in `tabs.tsx` — update the TabsTrigger className to:

```tsx
"inline-flex items-center justify-center whitespace-nowrap px-4 py-2 text-sm font-normal text-[var(--muted-foreground)] border-b-2 border-transparent transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 data-[state=active]:text-[var(--foreground)] data-[state=active]:font-semibold data-[state=active]:border-[var(--primary)]"
```

- [ ] **Step 4: Verify build**

```bash
cd frontend && npx next build 2>&1 | tail -5
```
Expected: build passes.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/ui/badge.tsx frontend/components/ui/table.tsx frontend/components/ui/tabs.tsx
git commit -m "feat(frontend): restyle Badge/Table/Tabs for Coinbase institutional look"
```

---

### Task 5: Base Components C — Dialog, Popover + remaining verification

**Files:**
- Modify: `frontend/components/ui/dialog.tsx`
- Modify: `frontend/components/ui/popover.tsx`

**Interfaces:**
- Consumes: CSS tokens from Task 1
- Produces: Shadow-free Dialog and Popover with hairline border

- [ ] **Step 1: Update dialog.tsx — remove shadow, add border**

Read the current dialog.tsx. Find the DialogContent className and update it to remove `shadow-*` classes and add `border border-border`:

The key change in DialogContent's className:
- Remove any `shadow-*` class
- Add `border border-[var(--border)]`
- Change `rounded-xl` to `rounded-[8px]`

```tsx
// In DialogContent className, find and replace:
// Remove: shadow-lg, shadow-xl, shadow-2xl, or similar
// Add: border border-[var(--border)]
// Change rounded: rounded-[8px]
```

- [ ] **Step 2: Update popover.tsx — remove shadow, add border**

Same treatment as DialogContent:

```tsx
// In PopoverContent className:
// Remove any shadow class
// Add: border border-[var(--border)]
// Change rounded: rounded-[6px]
```

- [ ] **Step 3: Verify all 19 base components build**

```bash
cd frontend && npx next build 2>&1 | tail -10
```
Expected: build passes, no warnings about missing shadow or ring classes.

- [ ] **Step 4: Commit**

```bash
git add frontend/components/ui/dialog.tsx frontend/components/ui/popover.tsx
git commit -m "feat(frontend): replace shadows with hairline borders in Dialog/Popover"
```

---

### Task 6: Layout Components — Sidebar, Header, SidebarLayout

**Files:**
- Modify: `frontend/components/layout/Sidebar.tsx`
- Modify: `frontend/components/layout/Header.tsx`
- Modify: `frontend/components/layout/SidebarLayout.tsx` (if exists; otherwise layout pattern in pages)

**Interfaces:**
- Consumes: CSS tokens from Task 1, Button from Task 3
- Produces: Coinbase-style Sidebar (240px, #F7F7F7, no right border, 36px item height), Header (56px, #FFF, hairline bottom border)

- [ ] **Step 1: Update Sidebar.tsx**

Read the current component. Key changes:

Logo area (lines 20-25): update to larger logo, Inter font:

```tsx
{/* Logo — replace the existing div block */}
<div className="flex items-center gap-3 px-4 h-[var(--header-height)] shrink-0">
  <div className="w-6 h-6 rounded-[4px] bg-[var(--primary)] flex items-center justify-center text-white font-bold text-xs">
    A
  </div>
  <span className="font-semibold text-[16px] text-[var(--foreground)]">AStockPursue</span>
</div>
```

Nav items (lines 37-49): update active/hover styles, remove left border bar, use Inter 14px:

```tsx
// Replace the Link className logic:
<Link
  key={item.href}
  href={item.href}
  className={cn(
    'flex items-center gap-3 px-4 h-9 text-[14px] transition-colors rounded-[6px] mx-2',
    active
      ? 'bg-[var(--primary-muted)] text-[var(--primary)] font-medium'
      : 'text-[var(--foreground-secondary)] hover:text-[var(--foreground)] hover:bg-[var(--surface-2)] font-normal'
  )}
>
  <item.icon className="w-[18px] h-[18px] shrink-0" />
  <span className="truncate">{t(`nav.${item.label}`)}</span>
</Link>
```

Section labels (lines 31-32): lighter style:

```tsx
// Group section label:
<div className={cn(gi > 0 && 'mt-4', 'px-4 py-1')}>
  <span className="text-[12px] font-semibold text-[var(--muted-foreground)]">
    {t(`nav.${group.key}`)}
  </span>
</div>
```

User footer (lines 57-61): no top border:

```tsx
{/* Remove border-t, keep subtle */}
<div className="p-3 shrink-0">
  <div className="text-[12px] text-[var(--muted-foreground)] truncate">
    user@account
  </div>
</div>
```

The aside container: remove `border-r`, keep bg:

```tsx
// Before (line 16):
className="fixed left-0 top-0 h-screen flex flex-col bg-[var(--surface-1)] border-r border-[var(--border-subtle)] z-40"
// After:
className="fixed left-0 top-0 h-screen flex flex-col bg-[var(--surface-1)] z-40"
```

- [ ] **Step 2: Update Header.tsx**

Key changes:

```tsx
// Header container — change height to header-height, remove border-subtle → use border
// line 22:
className="fixed top-0 right-0 flex items-center justify-between px-6 bg-[var(--background)] border-b border-[var(--border-subtle)] z-30"
style={{ height: 'var(--header-height)', left: 'var(--sidebar-width)' }}
```

Breadcrumb — update font:

```tsx
// line 26: change text-[12px] to text-[14px]
<div className="flex items-center gap-1 text-[14px] text-[var(--foreground-secondary)]">
```

Bell and avatar buttons — update size:

```tsx
// Notification bell — h-8 w-8
<Button variant="ghost" size="icon" className="h-8 w-8 relative">
  <Bell className="w-[18px] h-[18px]" />
  {/* Add blue dot indicator */}
  <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-[var(--primary)]" />
</Button>

// User avatar — 32px circle with name next to it
<DropdownMenu>
  <DropdownMenuTrigger>
    <Button variant="ghost" className="h-8 gap-2 px-2">
      <span className="w-8 h-8 rounded-full bg-[var(--surface-2)] flex items-center justify-center text-[14px] font-semibold text-[var(--foreground)]">
        U
      </span>
      <span className="text-[14px] text-[var(--foreground-secondary)] hidden sm:inline">User</span>
    </Button>
  </DropdownMenuTrigger>
  ...
</DropdownMenu>
```

- [ ] **Step 3: Verify Dashboard renders correctly**

```bash
cd frontend && npx next build 2>&1 | tail -5
```
Expected: build passes. Visual check: sidebar gray (#F7F7F7), header white with hairline bottom border.

- [ ] **Step 4: Commit**

```bash
git add frontend/components/layout/Sidebar.tsx frontend/components/layout/Header.tsx
git commit -m "feat(frontend): restyle Sidebar and Header for Coinbase institutional layout"
```

---

### Task 7: Financial A — KpiCard redesign + StatCallout (new)

**Files:**
- Modify: `frontend/components/financial/KpiCard.tsx`
- Create: `frontend/components/financial/StatCallout.tsx`

**Interfaces:**
- Produces: `KpiCard` — Coinbase white card with mono number, arrow trend indicator; `StatCallout` — large 44px 400w mono number for hero sections
- Props: `StatCalloutProps { label: string; value: string; change?: string; direction?: 'up' | 'down' }`

- [ ] **Step 1: Rewrite KpiCard.tsx**

```tsx
// frontend/components/financial/KpiCard.tsx
import { cn } from '@/lib/utils'

interface KpiCardProps {
  label: string
  value: string
  change?: string
  direction?: 'up' | 'down' | 'neutral'
}

export function KpiCard({ label, value, change, direction }: KpiCardProps) {
  return (
    <div className="bg-[var(--surface-1)] rounded-[6px] px-6 py-5">
      <div className="text-[12px] font-semibold text-[var(--foreground-secondary)] mb-2">
        {label}
      </div>
      <div className="text-[44px] font-[400] leading-[1.09] tracking-[-1px] font-mono tabular-nums text-[var(--foreground)]">
        {value}
      </div>
      {change && (
        <div className={cn(
          'flex items-center gap-1 mt-1.5 text-[14px] font-mono tabular-nums',
          direction === 'up' && 'text-[var(--up)]',
          direction === 'down' && 'text-[var(--down)]',
          (!direction || direction === 'neutral') && 'text-[var(--foreground-secondary)]'
        )}>
          <span>{direction === 'up' ? '▲' : direction === 'down' ? '▼' : ''}</span>
          <span>{change}</span>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Create StatCallout.tsx (new component for hero numbers)**

```tsx
// frontend/components/financial/StatCallout.tsx
import { cn } from '@/lib/utils'

interface StatCalloutProps {
  label: string
  value: string
  change?: string
  direction?: 'up' | 'down' | 'neutral'
  size?: 'lg' | 'md'
}

export function StatCallout({ label, value, change, direction, size = 'md' }: StatCalloutProps) {
  return (
    <div className="flex flex-col gap-1">
      <div className="text-[12px] font-semibold text-[var(--foreground-secondary)]">
        {label}
      </div>
      <div className={cn(
        'font-mono tabular-nums text-[var(--foreground)] tracking-[-1px]',
        size === 'lg' ? 'text-[52px] font-[300] leading-[1.0]' : 'text-[44px] font-[400] leading-[1.09]'
      )}>
        {value}
      </div>
      {change && (
        <div className={cn(
          'flex items-center gap-1 text-[14px] font-mono tabular-nums',
          direction === 'up' && 'text-[var(--up)]',
          direction === 'down' && 'text-[var(--down)]',
          (!direction || direction === 'neutral') && 'text-[var(--foreground-secondary)]'
        )}>
          <span>{direction === 'up' ? '▲' : direction === 'down' ? '▼' : ''}</span>
          <span>{change}</span>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Verify build**

```bash
cd frontend && npx next build 2>&1 | tail -5
```
Expected: build passes.

- [ ] **Step 4: Commit**

```bash
git add frontend/components/financial/KpiCard.tsx frontend/components/financial/StatCallout.tsx
git commit -m "feat(frontend): redesign KpiCard + add StatCallout for Coinbase hero numbers"
```

---

### Task 8: Financial B — PositionTable + StatusBadge (new) + MarketRow (new)

**Files:**
- Modify: `frontend/components/financial/PositionTable.tsx`
- Create: `frontend/components/financial/StatusBadge.tsx`
- Create: `frontend/components/financial/MarketRow.tsx`

**Interfaces:**
- Produces: `StatusBadge` — status:string → semitransparent badge; `MarketRow` — single scrollable market row with price + change

- [ ] **Step 1: Update PositionTable.tsx**

Update to use taller rows, mono numbers, arrow indicators:

```tsx
// frontend/components/financial/PositionTable.tsx
'use client'

import { useTranslations } from 'next-intl'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { usePositions } from '@/hooks'
import { formatPrice, formatPnL, formatPercent, cn } from '@/lib/utils'

export function PositionTable() {
  const t = useTranslations()
  const { data, error, isLoading } = usePositions()

  if (isLoading) return <div className="text-[14px] text-[var(--foreground-secondary)] p-6">Loading positions...</div>
  if (error) return <div className="text-[14px] text-[var(--destructive)] p-6">Failed to load positions</div>
  const positions = data?.positions || []

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>{t('portfolio.symbol')}</TableHead>
          <TableHead className="text-right">{t('portfolio.position')}</TableHead>
          <TableHead className="text-right">{t('portfolio.entryPrice')}</TableHead>
          <TableHead className="text-right">{t('portfolio.currentPrice')}</TableHead>
          <TableHead className="text-right">{t('portfolio.pnl')}</TableHead>
          <TableHead className="text-right">{t('portfolio.pnlPct')}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {positions.length === 0 ? (
          <TableRow>
            <TableCell colSpan={6} className="text-center text-[14px] text-[var(--foreground-secondary)] h-20">
              {t('common.noData')}
            </TableCell>
          </TableRow>
        ) : (
          positions.map((pos: any) => (
            <TableRow key={pos.symbol}>
              <TableCell className="font-mono font-medium">{pos.symbol}</TableCell>
              <TableCell className="font-mono text-right">{pos.size}</TableCell>
              <TableCell className="font-mono text-right">{formatPrice(pos.entry_price)}</TableCell>
              <TableCell className="font-mono text-right">{formatPrice(pos.current_price)}</TableCell>
              <TableCell className={cn('font-mono text-right tabular-nums', pos.pnl > 0 ? 'text-[var(--up)]' : 'text-[var(--down)]')}>
                {pos.pnl > 0 ? '▲ ' : '▼ '}{formatPnL(pos.pnl)}
              </TableCell>
              <TableCell className={cn('font-mono text-right tabular-nums', pos.pnl_pct > 0 ? 'text-[var(--up)]' : 'text-[var(--down)]')}>
                {pos.pnl_pct > 0 ? '▲ ' : '▼ '}{formatPercent(Math.abs(pos.pnl_pct || 0))}%
              </TableCell>
            </TableRow>
          ))
        )}
      </TableBody>
    </Table>
  )
}
```

- [ ] **Step 2: Create StatusBadge.tsx**

```tsx
// frontend/components/financial/StatusBadge.tsx
import { cn } from '@/lib/utils'

type StatusVariant = 'running' | 'filled' | 'success' | 'cancelled' | 'error' | 'paused' | 'pending' | 'stopped'

const statusStyles: Record<StatusVariant, string> = {
  running:    'bg-[rgba(0,82,255,0.10)] text-[#0052FF] border-[rgba(0,82,255,0.20)]',
  filled:     'bg-[rgba(5,177,105,0.10)] text-[#05B169] border-[rgba(5,177,105,0.20)]',
  success:    'bg-[rgba(5,177,105,0.10)] text-[#05B169] border-[rgba(5,177,105,0.20)]',
  cancelled:  'bg-[rgba(207,32,47,0.10)] text-[#CF202F] border-[rgba(207,32,47,0.20)]',
  error:      'bg-[rgba(207,32,47,0.10)] text-[#CF202F] border-[rgba(207,32,47,0.20)]',
  paused:     'bg-[rgba(244,176,0,0.10)] text-[#F4B000] border-[rgba(244,176,0,0.20)]',
  pending:    'bg-[rgba(124,130,138,0.10)] text-[#5B616E] border-[rgba(124,130,138,0.20)]',
  stopped:    'bg-[rgba(124,130,138,0.10)] text-[#5B616E] border-[rgba(124,130,138,0.20)]',
}

interface StatusBadgeProps {
  status: StatusVariant
  label?: string
  className?: string
}

export function StatusBadge({ status, label, className }: StatusBadgeProps) {
  return (
    <span className={cn(
      'inline-flex items-center h-6 px-2 rounded-[4px] border text-[12px] font-medium',
      statusStyles[status],
      className
    )}>
      {label || status}
    </span>
  )
}
```

- [ ] **Step 3: Create MarketRow.tsx**

```tsx
// frontend/components/financial/MarketRow.tsx
import { cn } from '@/lib/utils'
import { ChevronRight } from 'lucide-react'

interface MarketRowProps {
  symbol: string
  name: string
  price: number | string
  changePct: number
  onClick?: () => void
}

export function MarketRow({ symbol, name, price, changePct, onClick }: MarketRowProps) {
  const isUp = changePct >= 0
  return (
    <div
      onClick={onClick}
      className={cn(
        'flex items-center h-12 px-4 border-b border-[var(--border-subtle)] cursor-pointer transition-colors hover:bg-[var(--surface-1)]',
        'last:border-b-0'
      )}
    >
      <div className="flex-1 min-w-0">
        <div className="text-[14px] font-mono font-medium text-[var(--foreground)]">{symbol}</div>
        <div className="text-[12px] text-[var(--foreground-secondary)] truncate">{name}</div>
      </div>
      <div className="text-right min-w-[80px]">
        <div className="text-[14px] font-mono text-[var(--foreground)]">{price}</div>
      </div>
      <div className={cn(
        'text-right min-w-[90px] text-[14px] font-mono tabular-nums',
        isUp ? 'text-[var(--up)]' : 'text-[var(--down)]'
      )}>
        {isUp ? '▲ ' : '▼ '}{Math.abs(changePct).toFixed(2)}%
      </div>
      <ChevronRight className="w-4 h-4 text-[var(--foreground-muted)] ml-2 shrink-0" />
    </div>
  )
}
```

- [ ] **Step 4: Verify build**

```bash
cd frontend && npx next build 2>&1 | tail -5
```
Expected: build passes.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/financial/PositionTable.tsx frontend/components/financial/StatusBadge.tsx frontend/components/financial/MarketRow.tsx
git commit -m "feat(frontend): update PositionTable + add StatusBadge and MarketRow components"
```

---

### Task 9: Financial C — OrderForm + OrderBook + PriceTicker (new)

**Files:**
- Modify: `frontend/components/financial/OrderForm.tsx`
- Modify: `frontend/components/financial/OrderBook.tsx`
- Create: `frontend/components/financial/PriceTicker.tsx`

**Interfaces:**
- Produces: `PriceTicker` — symbol header bar with real-time price and 24h stats; redesigned OrderForm and OrderBook with proper light theme

- [ ] **Step 1: Create PriceTicker.tsx**

```tsx
// frontend/components/financial/PriceTicker.tsx
import { cn } from '@/lib/utils'

interface PriceTickerProps {
  symbol: string
  name?: string
  price: number
  change: number
  changePct: number
  high?: number
  low?: number
  className?: string
}

export function PriceTicker({ symbol, name, price, change, changePct, high, low, className }: PriceTickerProps) {
  const isUp = change >= 0
  return (
    <div className={cn(
      'flex items-center gap-6 px-6 py-4 bg-[var(--surface-1)] rounded-[6px]',
      className
    )}>
      <div className="flex items-baseline gap-2">
        <span className="text-[14px] font-mono font-semibold text-[var(--foreground)]">{symbol}</span>
        {name && <span className="text-[14px] text-[var(--foreground-secondary)]">{name}</span>}
      </div>
      <div className="text-[36px] font-[400] leading-[1.11] tracking-[-0.5px] font-mono tabular-nums text-[var(--foreground)]">
        {price.toFixed(2)}
      </div>
      <div className={cn(
        'flex items-center gap-1 text-[16px] font-mono tabular-nums',
        isUp ? 'text-[var(--up)]' : 'text-[var(--down)]'
      )}>
        <span>{isUp ? '▲' : '▼'}</span>
        <span>{isUp ? '+' : ''}{change.toFixed(2)}</span>
        <span>({isUp ? '+' : ''}{changePct.toFixed(2)}%)</span>
      </div>
      {(high !== undefined && low !== undefined) && (
        <div className="flex items-center gap-4 ml-auto text-[12px] text-[var(--foreground-secondary)]">
          <span>H: <span className="font-mono text-[var(--foreground)]">{high.toFixed(2)}</span></span>
          <span>L: <span className="font-mono text-[var(--foreground)]">{low.toFixed(2)}</span></span>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Update OrderForm.tsx — light theme restyle**

Read current file. Key changes:
- Card container: `bg-white border border-[var(--border)] rounded-[6px] p-5`
- Buy/Sell toggle: Coinbase-style tab buttons (green/red)
- Inputs: h-10, matching base component
- Submit button: large (h-11), green for buy, red for sell

```tsx
// Key class changes in OrderForm:
// Container:
<div className="bg-white border border-[var(--border)] rounded-[6px] p-5">

// Buy/Sell toggle:
<div className="flex mb-4">
  <button className="flex-1 h-10 rounded-l-[6px] text-[14px] font-semibold data-[active=true]:bg-[var(--up)] data-[active=true]:text-white data-[active=false]:bg-[var(--surface-1)] data-[active=false]:text-[var(--foreground-secondary)]">
    {t('trading.buy')}
  </button>
  <button className="flex-1 h-10 rounded-r-[6px] text-[14px] font-semibold data-[active=true]:bg-[var(--down)] data-[active=true]:text-white data-[active=false]:bg-[var(--surface-1)] data-[active=false]:text-[var(--foreground-secondary)]">
    {t('trading.sell')}
  </button>
</div>

// Submit button:
<button className="w-full h-11 rounded-[6px] text-[16px] font-semibold text-white bg-[var(--up)]">
  {t('trading.buy')} {symbol}
</button>
```

- [ ] **Step 3: Update OrderBook.tsx — higher density, proper depth bars**

```tsx
// Key changes in OrderBook:
// Row height 20px, 14px mono font
// Bid rows: green-tinted background bar proportional to cumulative volume
// Ask rows: red-tinted background bar
// Spread row: hairline divider with spread value

// Each row style:
<div className="flex items-center h-5 text-[14px] font-mono">
  <span className="w-1/3 text-[var(--up)]">{price}</span>
  <span className="w-1/3 text-right text-[var(--foreground-secondary)]">{qty}</span>
  <span className="w-1/3 text-right text-[var(--foreground-muted)]">{cumulative}</span>
</div>

// For depth bars, use a background div with width proportional to depth:
<div className="relative">
  <div className="absolute right-0 top-0 h-full bg-[var(--up)] opacity-[0.08]" style={{ width: `${depthPercent}%` }} />
  <div className="relative flex items-center h-5">
    {/* price, qty, cumulative as above */}
  </div>
</div>
```

- [ ] **Step 4: Verify build**

```bash
cd frontend && npx next build 2>&1 | tail -5
```
Expected: build passes.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/financial/PriceTicker.tsx frontend/components/financial/OrderForm.tsx frontend/components/financial/OrderBook.tsx
git commit -m "feat(frontend): add PriceTicker + restyle OrderForm and OrderBook for Coinbase look"
```

---

### Task 10: Financial D — Charts + remaining + DividerSection (new)

**Files:**
- Modify: `frontend/components/financial/EquityChart.tsx`
- Modify: `frontend/components/financial/CandlestickChart.tsx`
- Modify: `frontend/components/financial/DrawdownChart.tsx`
- Modify: `frontend/components/financial/CorrelationMatrix.tsx`
- Modify: `frontend/components/financial/TradeTimeline.tsx`
- Modify: `frontend/components/financial/ScreenerGrid.tsx`
- Modify: `frontend/components/financial/LogViewer.tsx`
- Modify: `frontend/components/financial/SymbolSearch.tsx`
- Create: `frontend/components/financial/DividerSection.tsx`

**Interfaces:**
- Produces: Chart components with white background, Coinbase semantic colors; `DividerSection` for page section headers

- [ ] **Step 1: Update chart components — pass Coinbase theme colors**

For each chart component (EquityChart, CandlestickChart, DrawdownChart, CorrelationMatrix):
- Container: `bg-white border border-[var(--border)] rounded-[6px]` instead of dark surface
- Grid lines: `#EEF0F3` instead of dark grids
- Up/down colors: use CSS variables `var(--up)` / `var(--down)`
- Tooltip: white background, 14px font

Example for CandlestickChart:

```tsx
// In the chart SVG/Recharts config:
// candlestick colors:
const upColor = '#05B169'
const downColor = '#CF202F'
const gridColor = '#EEF0F3'
```

Read each chart file and apply these color overrides. The structure stays the same — only color values change.

- [ ] **Step 2: Update remaining financial components**

**TradeTimeline** — row height 40px, 14px font, hairline divider:

```tsx
// Row style:
<div className="flex items-center h-10 px-4 border-b border-[var(--border-subtle)] text-[14px]">
```

**ScreenerGrid** — Table component restyle, same as PositionTable pattern.

**LogViewer** — White background card, mono font, 13px:

```tsx
<div className="bg-white border border-[var(--border)] rounded-[6px] p-4 font-mono text-[13px] text-[var(--foreground-secondary)]">
```

**SymbolSearch** — Input h-10, Coinbase style:

```tsx
<input className="h-10 w-full rounded-[6px] border border-[var(--border)] bg-white px-4 text-[14px] placeholder:text-[var(--muted-foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--ring)]" />
```

- [ ] **Step 3: Create DividerSection.tsx**

```tsx
// frontend/components/financial/DividerSection.tsx
interface DividerSectionProps {
  title: string
  className?: string
}

export function DividerSection({ title, className }: DividerSectionProps) {
  return (
    <div className={`bg-[var(--surface-1)] px-6 py-2 ${className || ''}`}>
      <span className="text-[12px] font-semibold text-[var(--foreground-secondary)]">
        {title}
      </span>
    </div>
  )
}
```

- [ ] **Step 4: Verify build**

```bash
cd frontend && npx next build 2>&1 | tail -5
```
Expected: build passes.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/financial/
git commit -m "feat(frontend): update chart colors + remaining financial components + add DividerSection"
```

---

### Task 11: Pages A — Dashboard + Trading

**Files:**
- Modify: `frontend/app/page.tsx` (Dashboard)
- Modify: `frontend/app/trading/page.tsx`

**Interfaces:**
- Consumes: StatCallout, KpiCard, PriceTicker, updated PositionTable, OrderBook, OrderForm from Tasks 7-10
- Produces: Coinbase-styled Dashboard and Trading pages

- [ ] **Step 1: Update Dashboard page**

Replace KpiCard usage with StatCallout where applicable, update styling:

```tsx
// frontend/app/page.tsx
'use client'

import { useTranslations } from 'next-intl'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { StatCallout } from '@/components/financial/StatCallout'
import { KpiCard } from '@/components/financial/KpiCard'
import { PositionTable } from '@/components/financial/PositionTable'
import { EquityChart } from '@/components/financial/EquityChart'
import { usePositions, useSystemStatus } from '@/hooks'
import { useWebSocket } from '@/hooks/useWebSocket'

export default function DashboardPage() {
  const t = useTranslations()
  useWebSocket()
  const { data: posData } = usePositions()
  const { data: sysData } = useSystemStatus()

  return (
    <SidebarLayout>
      <div className="space-y-4">
        <h1 className="text-[32px] font-[400] tracking-[-0.4px] text-[var(--foreground)]">
          {t('nav.dashboard')}
        </h1>

        {/* Hero KPI row — StatCallout for the main equity number */}
        <div className="grid grid-cols-4 gap-[var(--grid-gap)]">
          <StatCallout label={t('portfolio.totalEquity')} value="$100,000.00" change="+2.34%" direction="up" />
          <KpiCard label={t('portfolio.pnl')} value="+$2,340.00" direction="up" />
          <KpiCard label={t('portfolio.available')} value="$85,000.00" />
          <KpiCard label={t('portfolio.margin')} value="$15,000.00" change="15%" direction="neutral" />
        </div>

        {/* Equity Chart + Positions */}
        <div className="grid grid-cols-12 gap-[var(--grid-gap)]">
          <div className="col-span-8">
            <div className="bg-white border border-[var(--border)] rounded-[6px] p-[var(--card-padding)]">
              <h2 className="text-[18px] font-semibold text-[var(--foreground)] mb-4">{t('backtest.equityCurve')}</h2>
              <EquityChart data={[
                { time: '9:30', equity: 100000 },
                { time: '10:00', equity: 100500 },
                { time: '10:30', equity: 102340 }
              ]} />
            </div>
          </div>
          <div className="col-span-4">
            <div className="bg-white border border-[var(--border)] rounded-[6px] p-[var(--card-padding)]">
              <h2 className="text-[18px] font-semibold text-[var(--foreground)] mb-4">{t('nav.positions')}</h2>
              <PositionTable />
            </div>
          </div>
        </div>
      </div>
    </SidebarLayout>
  )
}
```

- [ ] **Step 2: Update Trading page**

Add PriceTicker at top, update card wrappers:

```tsx
// frontend/app/trading/page.tsx
// ... imports include PriceTicker from Task 9

return (
  <SidebarLayout>
    <div className="space-y-4">
      <h1 className="text-[32px] font-[400] tracking-[-0.4px] text-[var(--foreground)]">
        {t('nav.trading')}
      </h1>

      {/* PriceTicker bar — new */}
      <PriceTicker
        symbol={symbol}
        price={12.50}
        change={0.32}
        changePct={2.63}
        high={12.65}
        low={12.10}
      />

      {/* 12-column grid */}
      <div className="grid grid-cols-12 gap-[var(--grid-gap)]">
        <div className="col-span-3">
          <OrderForm />
        </div>
        <div className="col-span-6">
          <div className="bg-white border border-[var(--border)] rounded-[6px] p-[var(--card-padding)]">
            <h2 className="text-[18px] font-semibold text-[var(--foreground)] mb-4">{symbol}</h2>
            <CandlestickChart data={bars} />
          </div>
        </div>
        <div className="col-span-3">
          <div className="bg-white border border-[var(--border)] rounded-[6px] p-[var(--card-padding)]">
            <h2 className="text-[18px] font-semibold text-[var(--foreground)] mb-4">{t('market.depth')}</h2>
            <OrderBook bids={orderBook.bids} asks={orderBook.asks} />
          </div>
        </div>
      </div>

      {/* Positions */}
      <div className="bg-white border border-[var(--border)] rounded-[6px] p-[var(--card-padding)]">
        <h2 className="text-[18px] font-semibold text-[var(--foreground)] mb-4">{t('nav.positions')}</h2>
        <PositionTable />
      </div>
    </div>
  </SidebarLayout>
)
```

- [ ] **Step 3: Verify build**

```bash
cd frontend && npx next build 2>&1 | tail -10
```
Expected: build passes, no type errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/page.tsx frontend/app/trading/page.tsx
git commit -m "feat(frontend): adapt Dashboard and Trading pages for Coinbase theme"
```

---

### Task 12: Pages B — Backtest + PaperTrading + Orders/Positions

**Files:**
- Modify: `frontend/app/backtest/page.tsx`
- Modify: `frontend/app/backtest/[id]/page.tsx`
- Modify: `frontend/app/backtest/new/page.tsx`
- Modify: `frontend/app/paper-trading/page.tsx`
- Modify: `frontend/app/paper-trading/[id]/page.tsx`
- Modify: `frontend/app/trading/orders/page.tsx`
- Modify: `frontend/app/trading/positions/page.tsx`

**Interfaces:**
- Consumes: StatCallout, StatusBadge, updated Table, Button from Tasks 3-10
- Produces: Coinbase-styled Backtest list/detail/create, PaperTrading list/detail, Orders, Positions

- [ ] **Step 1: Update Backtest pages**

Backtest list (`backtest/page.tsx`):
- Page title: `text-[32px] font-[400] tracking-[-0.4px]`
- Table: use updated Table component (Task 4), Return column with mono + color + ▲▼
- "New Backtest" button: use primary button style
- Card wrapper: `bg-white border border-[var(--border)] rounded-[6px] p-6`

Backtest detail (`backtest/[id]/page.tsx`):
- Replace KpiCard with StatCallout for the 5 KPI numbers
- Charts in white border cards

Backtest create (`backtest/new/page.tsx`):
- Inputs: h-10, matching Task 3 Input style
- Labels: 14px font-semibold
- Submit button: h-10 primary

Apply these patterns to the actual files — change the className strings on containers, headings, and inputs. The structural JSX stays intact.

- [ ] **Step 2: Update PaperTrading pages**

PaperTrading list (`paper-trading/page.tsx`):
- Status column: use `<StatusBadge status={...} />` 
- Table with updated row styles

PaperTrading detail (`paper-trading/[id]/page.tsx`):
- KPI row: use StatCallout
- Start/Stop buttons: use Button with primary/outline variants
- Charts in white border cards

- [ ] **Step 3: Update Orders and Positions pages**

Orders (`trading/orders/page.tsx`):
- Side column: StatusBadge
- Price/Filled columns: mono, tabular-nums

Positions (`trading/positions/page.tsx`):
- Already uses PositionTable from Task 8 — should auto-adapt
- Card wrapper: `bg-white border border-[var(--border)] rounded-[6px] p-6`

- [ ] **Step 4: Verify build**

```bash
cd frontend && npx next build 2>&1 | tail -10
```
Expected: build passes.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/backtest/ frontend/app/paper-trading/ frontend/app/trading/orders/ frontend/app/trading/positions/
git commit -m "feat(frontend): adapt Backtest/PaperTrading/Orders/Positions pages for Coinbase theme"
```

---

### Task 13: Pages C — Remaining pages verification

**Files:**
- Scan: `frontend/app/analysis/`, `frontend/app/market/`, `frontend/app/broker/`, `frontend/app/screener/`, `frontend/app/scheduler/`, `frontend/app/settings/`, `frontend/app/system/`, `frontend/app/agent/`, `frontend/app/factors/`, `frontend/app/workflow/`, `frontend/app/login/`, `frontend/app/register/`

**Interfaces:**
- Consumes: All CSS tokens and updated components from Tasks 1-10
- Produces: Build-verified, visually consistent remaining pages

- [ ] **Step 1: Scan all remaining pages for hardcoded dark values**

```bash
grep -rn "surface-1\|surface-2\|surface-3\|#020617\|#0A0F1D\|#0F172A\|#1A1E2F\|#F8FAFC\|#94A3B8" frontend/app/ --include="*.tsx" 2>/dev/null
```

For each match, verify the element renders correctly in light mode. If a component uses `bg-[var(--surface-2)]` in a card context, it should be `bg-white border border-[var(--border)]`. If it's a page section, `bg-[var(--surface-1)]` is correct (gray background area).

- [ ] **Step 2: Fix any hardcoded dark-mode assumptions**

Common patterns to update:
- `text-[var(--foreground-secondary)]` with `#F8FAFC` fallback → remove hardcoded fallback
- `className="dark"` or `dark:` prefixes → remove (we're light mode now)
- Inline `style={{ color: '#F8FAFC' }}` → use `var(--foreground)`

- [ ] **Step 3: Analysis pages — add DividerSection**

For analysis pages (`analysis/correlation`, `analysis/attribution`, `analysis/stress-test`):
- Add `<DividerSection title="..." />` between chart sections
- Charts in white border cards

- [ ] **Step 4: Verify full build**

```bash
cd frontend && npx next build 2>&1 | tail -15
```
Expected: build passes with zero errors and zero warnings.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/
git commit -m "feat(frontend): verify and fix all remaining pages for Coinbase light theme"
```

---

### Task 14: i18n keys + final verification

**Files:**
- Modify: `frontend/lib/i18n.tsx` (or messages files)
- No new pages created

**Interfaces:**
- Produces: Translation keys for new component labels (StatusBadge, PriceTicker, StatCallout, DividerSection)

- [ ] **Step 1: Add new i18n keys**

Check the i18n structure (typically `frontend/messages/en.json` and `frontend/messages/zh.json`):

```json
// en.json additions:
{
  "status.running": "Running",
  "status.filled": "Filled",
  "status.cancelled": "Cancelled",
  "status.paused": "Paused",
  "status.pending": "Pending",
  "status.stopped": "Stopped",
  "status.error": "Error",
  "trading.buy": "Buy",
  "trading.sell": "Sell",
  "market.high": "H",
  "market.low": "L",
  "market.spread": "Spread"
}

// zh.json additions:
{
  "status.running": "运行中",
  "status.filled": "已成交",
  "status.cancelled": "已取消",
  "status.paused": "已暂停",
  "status.pending": "等待中",
  "status.stopped": "已停止",
  "status.error": "错误",
  "trading.buy": "买入",
  "trading.sell": "卖出",
  "market.high": "高",
  "market.low": "低",
  "market.spread": "价差"
}
```

- [ ] **Step 2: Run full build + type check**

```bash
cd frontend && npx next build 2>&1
```
Expected: clean build, no errors.

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
```
Expected: zero type errors.

- [ ] **Step 3: Final commit**

```bash
git add frontend/lib/i18n.tsx frontend/messages/ 2>/dev/null
git commit -m "feat(frontend): add i18n keys for new Coinbase-theme components"
```

---

## Completion Checklist

After all 14 tasks:
- [ ] `npx next build` passes clean
- [ ] `npx tsc --noEmit` passes clean
- [ ] No hardcoded dark colors remain in any `.tsx` file
- [ ] No `box-shadow` in component styles (only `border` for separation)
- [ ] No `font-bold` on display headings (max `font-semibold`)
- [ ] All number values use `font-mono tabular-nums`
- [ ] zh locale: red up / green down working
- [ ] `CHANGELOG.md` updated with all changes
