# OLED Trading Terminal — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **⚠️ Font Strategy Update (2026-06-07):** Google Fonts CDN is blocked in China. Task 1.1 has been updated to use `@fontsource/fira-sans` + `@fontsource/fira-code` npm packages for self-hosted fonts. Font files (woff2) are bundled by Vite — zero external requests at runtime. See commit `eef640f`.

**Goal:** Redesign AStockPursue frontend as an OLED dark trading terminal with Data-Dense layout, orange brand accent, and Fira font family.

**Architecture:** Six-phase bottom-up approach. Phase 1 rebuilds the design token layer (CSS variables, fonts, chart theme) so all pages inherit the new look. Phase 2 rewrites the layout shell. Phase 3 adds new data-display components. Phase 4 rebases charts. Phase 5 redesigns each page. Phase 6 polishes interactions.

**Tech Stack:** React 18, TypeScript, Tailwind CSS 4, ECharts, Monaco Editor, Zustand, Lucide React, Vite

**Spec:** `docs/superpowers/specs/2026-06-07-oled-trading-terminal-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `frontend/index.html` | Modify | Google Fonts: Fira Sans + Fira Code |
| `frontend/src/index.css` | Rewrite | CSS variables (OLED tokens), component classes |
| `frontend/tailwind.config.ts` | Modify | Font family, spacing scale |
| `frontend/src/lib/chart-theme.ts` | Rewrite | ECharts OLED dark theme |
| `frontend/src/hooks/useDarkMode.ts` | Modify | Always-dark mode |
| `frontend/src/lib/formatters.ts` | Modify | Add price/percent/volume formatters |
| `frontend/src/hooks/useCountUp.ts` | Create | Count-up animation hook |
| `frontend/src/components/layout/Layout.tsx` | Rewrite | New sidebar + header |
| `frontend/src/components/layout/BottomTabBar.tsx` | Create | Mobile bottom tab bar |
| `frontend/src/components/layout/Breadcrumb.tsx` | Create | Breadcrumb navigation |
| `frontend/src/components/common/KpiCard.tsx` | Create | KPI metric card component |
| `frontend/src/components/charts/CandlestickChart.tsx` | Modify | Dark theme, compact layout |
| `frontend/src/components/charts/EquityChart.tsx` | Modify | Dark theme, compact layout |
| `frontend/src/pages/Dashboard.tsx` | Modify | Apply OLED layout pattern |
| `frontend/src/pages/Trading.tsx` | Modify | Apply OLED layout pattern |
| Various page files | Modify | Apply OLED layout pattern |

---

## Phase 1: Token System Rebuild

### Task 1.1: Switch to Fira fonts in index.html

**Files:**
- Modify: `frontend/index.html:8-10`

- [ ] **Step 1: Replace Google Fonts with optimized loading strategy**

Replace the entire font-related section in `<head>` of `frontend/index.html`. The old code has DM Sans + JetBrains Mono `<link>` plus two `<link rel="preconnect">` lines. Replace them all with:

```html
<!-- DNS prefetch for Google Fonts (fastest initial connection) -->
<link rel="dns-prefetch" href="https://fonts.googleapis.com">
<link rel="dns-prefetch" href="https://fonts.gstatic.com" crossorigin>

<!-- Preconnect for TLS + TCP (warmer than dns-prefetch, less overhead than full preload) -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>

<!-- Preload critical font weights to eliminate FOIT/CLS on first paint -->
<!-- Fira Sans Regular (400) — body text, labels   | Fira Sans Semibold (600) — headings, nav -->
<!-- Fira Code Regular (400) — table data           | Fira Code Medium (500) — KPI values, prices -->
<link rel="preload"
      href="https://fonts.googleapis.com/css2?family=Fira+Sans:wght@400;600&family=Fira+Code:wght@400;500&display=swap"
      as="style"
      crossorigin="anonymous">
<link rel="stylesheet"
      href="https://fonts.googleapis.com/css2?family=Fira+Sans:wght@400;600&family=Fira+Code:wght@400;500&display=swap"
      media="print"
      onload="this.media='all';this.onload=null">

<!-- Fallback: if JS is disabled, load normally -->
<noscript>
  <link rel="stylesheet"
        href="https://fonts.googleapis.com/css2?family=Fira+Sans:wght@400;600&family=Fira+Code:wght@400;500&display=swap">
</noscript>

<!-- Full weight set (lazy-loaded, non-blocking) — for pages that need bold/extended weights -->
<link rel="stylesheet"
      href="https://fonts.googleapis.com/css2?family=Fira+Sans:wght@300;500;700&family=Fira+Code:wght@600;700&display=swap"
      media="print"
      onload="this.media='all';this.onload=null">
```

**Why this strategy:**

| Layer | What | Why |
|-------|------|-----|
| `dns-prefetch` | DNS 解析提前 | 比 preconnect 更轻量，最早触发 |
| `preconnect` | TLS + TCP 握手 | 在 preload 之前完成连接建立 |
| `preload` (critical 4 weights) | Fira Sans 400/600 + Fira Code 400/500 | 阻塞渲染关键字体，消除 FOIT |
| `media="print" onload` | 异步加载非关键 CSS | 不阻塞 `render-blocking`，加载后立即生效 |
| `display=swap` | 文本立即用 fallback 渲染 | 字体加载完成后无缝切换，永不空白 |
| `<noscript>` | JS 禁用时回退 | 保证无 JS 环境也能加载字体 |
| Full weight set (lazy) | Bold/extended 字重 | 非首屏必须，延后加载不阻塞 LCP |

**Critical weights rationale:**
- Fira Sans 400: 正文、标签、描述（使用量最大）
- Fira Sans 600: 导航、板块标题、卡片标题
- Fira Code 400: 表格数据、辅助数字、时间戳
- Fira Code 500: KPI 值、价格、涨跌幅（交易终端的核心）

- [ ] **Step 2: Verify font loading performance**

Run: `cd frontend && npx vite --port 5899`

Open Chrome DevTools → Network tab, throttle to "Slow 3G":
1. Confirm text renders immediately (no blank page while fonts load)
2. Confirm fonts load asynchronously without blocking LCP
3. Check Console for any CORS or preload warnings

Open Lighthouse → Performance:
- LCP should not be blocked by font loading
- "Ensure text remains visible during webfont load" audit should pass
- CLS should be < 0.1

- [ ] **Step 3: Commit**

```bash
git add frontend/index.html
git commit -m "feat(oled): switch fonts to Fira family with optimized loading strategy (preload critical weights, async non-critical, display:swap)"
```

---

### Task 1.2: Update Tailwind font config

**Files:**
- Modify: `frontend/tailwind.config.ts:34-37`

- [ ] **Step 1: Replace font families**

In `frontend/tailwind.config.ts`, replace lines 34-37:

```typescript
fontFamily: {
  // Fallback stack ordered by metric compatibility with Fira Sans:
  // -apple-system (San Francisco) has similar x-height and width
  // Segoe UI matches well on Windows
  // Fallback emoji for color emoji support
  sans: [
    "Fira Sans",
    "-apple-system",
    "BlinkMacSystemFont",
    "Segoe UI",
    "Helvetica Neue",
    "Arial",
    "sans-serif",
    "Apple Color Emoji",
    "Segoe UI Emoji",
  ],
  // Fallback stack ordered by metric compatibility with Fira Code:
  // ui-monospace picks SF Mono on macOS/iOS, Cascadia Code on Windows Terminal
  // Menlo/Consolas are good mid-width fallbacks
  mono: [
    "Fira Code",
    "ui-monospace",
    "SF Mono",
    "Cascadia Code",
    "Menlo",
    "Consolas",
    "DejaVu Sans Mono",
    "monospace",
  ],
},
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: No new errors from this change.

- [ ] **Step 3: Commit**

```bash
git add frontend/tailwind.config.ts
git commit -m "feat(oled): switch Tailwind font families to Fira Sans/Fira Code"
```

---

### Task 1.3: Rewrite CSS design tokens (OLED dark)

**Files:**
- Modify: `frontend/src/index.css` (entire file)

- [ ] **Step 1: Replace the `:root` block with OLED dark-only tokens**

Write the entire `frontend/src/index.css`. The key change: collapse `:root` and `.dark` into a single set of OLED dark tokens (no light mode). Keep the `html[lang="zh"]` override for Chinese market colors. Keep all component utility classes but adjust their values for the new spacing/color tokens.

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    /* ── OLED Surface hierarchy ──────────────────────────────────── */
    --background: 228 50% 2%;       /* #020617 */
    --foreground: 210 40% 96%;      /* #F8FAFC */
    --card: 228 45% 6%;             /* #0F172A */
    --card-foreground: 210 40% 96%;
    --surface-1: 228 40% 5%;       /* #0A0F1D */
    --surface-3: 228 35% 11%;      /* #1A1E2F */

    /* ── Brand accent (orange, preserved) ────────────────────────── */
    --primary: 29 93% 58%;          /* #FB923C */
    --primary-foreground: 0 0% 100%;

    /* ── Muted / secondary ──────────────────────────────────────── */
    --muted: 228 30% 14%;           /* #272F42 */
    --muted-foreground: 210 15% 55%; /* #94A3B8 */
    --destructive: 0 84% 60%;
    --destructive-foreground: 0 0% 100%;
    --border: 228 25% 18%;          /* #1E293B */
    --radius: 0.4rem;               /* tighter than before */

    /* ── Semantic colors (dark-adjusted) ─────────────────────────── */
    --success: 142 71% 45%;         /* #22C55E */
    --danger: 0 84% 60%;            /* #EF4444 */
    --warning: 38 92% 50%;          /* #F59E0B */
    --info: 200 85% 52%;            /* #3B82F6 */

    /* ── Accent palette ──────────────────────────────────────────── */
    --accent-cyan: 190 85% 48%;
    --accent-emerald: 142 65% 45%;
    --accent-rose: 350 75% 48%;
    --accent-violet: 260 65% 55%;
    --accent-amber: 38 92% 50%;

    /* ── Directional colors (Western default: green-up / red-down) ── */
    --up: 142 71% 45%;
    --down: 0 84% 60%;

    /* ── Border tiers ────────────────────────────────────────────── */
    --border-subtle: 228 25% 14%;
    --border-strong: 228 25% 24%;

    /* ── Elevation (subtle in OLED dark — borders do the work) ───── */
    --shadow-sm: none;
    --shadow-md: 0 2px 8px 0 rgb(0 0 0 / 0.3);
    --shadow-lg: 0 8px 24px 0 rgb(0 0 0 / 0.5);
    --shadow-glow: 0 0 16px -2px hsl(29 93% 58% / 0.15);

    /* ── Chart tokens ────────────────────────────────────────────── */
    --chart-grid: 228 25% 14%;
    --chart-text: 210 15% 55%;
    --chart-axis: 228 25% 20%;
    --chart-compare-a: #60a5fa;
    --chart-compare-b: #fbbf24;

    /* ── Sidebar accent ──────────────────────────────────────────── */
    --sidebar-accent: 29 93% 58%;
  }

  /* Chinese market convention: red-up/red-rise, green-down/green-fall (红涨绿跌) */
  html[lang="zh"] {
    --up: 0 84% 60%;
    --down: 142 71% 45%;
  }

  * { @apply border-border; }
  body { @apply bg-background text-foreground antialiased; }

  /* ── Typography scale (compact) ────────────────────────────────── */
  h1 { @apply text-xl font-bold tracking-[-0.02em]; }
  h2 { @apply text-base font-semibold tracking-[-0.01em]; }
  h3 { @apply text-sm font-medium; }
  .display { @apply text-2xl font-bold tracking-[-0.03em]; }
  .caption { @apply text-[11px] leading-4 text-muted-foreground; }
  .overline { @apply text-[10px] font-semibold uppercase tracking-[0.05em] text-muted-foreground; }

  /* ── Prose table enhancements ──────────────────────────────────── */
  .prose table { border-collapse: collapse; width: 100%; }
  .prose th, .prose td { border: 1px solid hsl(var(--border)); }
  .prose tbody tr:nth-child(even) { background: hsl(var(--muted) / 0.3); }

  /* ── Smooth scrollbar (OLED dark) ──────────────────────────────── */
  ::-webkit-scrollbar { width: 5px; height: 5px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: hsl(var(--border)); border-radius: 3px; }
  ::-webkit-scrollbar-thumb:hover { background: hsl(var(--muted-foreground)); }
}

@layer components {
  /* ── Button system (compact) ───────────────────────────────────── */
  .btn {
    @apply inline-flex items-center justify-center gap-1.5 rounded-md text-xs font-medium
           transition-all duration-150 ease-out
           focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 focus-visible:ring-offset-1 focus-visible:ring-offset-background
           disabled:pointer-events-none disabled:opacity-40
           select-none
           active:scale-[0.97];
  }
  .btn-sm { @apply btn h-8 px-3 text-[11px] gap-1; }
  .btn-md { @apply btn h-9 px-4 text-xs gap-1.5; }
  .btn-primary {
    @apply bg-primary text-primary-foreground
           hover:brightness-110
           active:brightness-95;
  }
  .btn-secondary {
    @apply bg-muted/80 text-foreground border border-border/50
           hover:bg-muted hover:border-border;
  }
  .btn-ghost {
    @apply text-muted-foreground hover:bg-muted/60 hover:text-foreground;
  }
  .btn-outline {
    @apply border border-border/60 bg-card text-foreground hover:bg-muted/50 hover:border-primary/30;
  }
  .btn-danger { @apply bg-danger/12 text-danger hover:bg-danger/20; }
  .btn-success { @apply bg-success/12 text-success hover:bg-success/20; }
  .btn-warning { @apply bg-warning/12 text-warning hover:bg-warning/20; }

  /* ── Focus ring ────────────────────────────────────────────────── */
  .focus-ring {
    @apply focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40
           focus-visible:ring-offset-1 focus-visible:ring-offset-background;
  }

  /* ── Page header (compact) ─────────────────────────────────────── */
  .page-header {
    @apply flex items-center justify-between px-4 py-2 shrink-0 min-h-[40px] border-b border-border-subtle;
  }
  .page-header-title {
    @apply flex items-center gap-2;
  }
  .page-header-title h1 {
    @apply text-sm font-semibold tracking-[-0.01em];
  }
  .page-header-title .icon {
    @apply h-4 w-4 text-primary;
  }
  .page-header-desc {
    @apply text-[11px] text-muted-foreground mt-0.5;
  }
  .page-header-actions {
    @apply flex items-center gap-1 flex-wrap;
  }

  /* ── Card system ───────────────────────────────────────────────── */
  .card {
    @apply bg-card border border-border-subtle rounded-lg transition-all duration-150;
  }
  .card-hover {
    @apply card hover:border-primary/20 hover:bg-surface-3;
  }
  .card-header {
    @apply flex items-center justify-between px-3 py-2 border-b border-border-subtle bg-muted/20 rounded-t-lg;
  }
  .card-body { @apply p-3; }
  .card-metric {
    @apply card p-3 flex flex-col gap-1 cursor-default;
  }

  /* ── Section card (page-level panels) ──────────────────────────── */
  .section-card {
    @apply bg-card border border-border-subtle rounded-lg overflow-hidden flex flex-col;
  }

  /* ── Glass surface (OLED — minimal blur) ───────────────────────── */
  .surface-glass {
    @apply bg-background/90 backdrop-blur-md border border-border/40;
  }

  /* ── Mobile responsive ─────────────────────────────────────────── */
  @media (max-width: 767px) {
    .mobile-bottom-nav {
      @apply fixed bottom-0 left-0 right-0 z-40 flex items-center justify-around
             bg-card border-t border-border px-1 py-1.5 safe-area-bottom;
    }
    .mobile-bottom-nav a,
    .mobile-bottom-nav button {
      @apply flex flex-col items-center gap-0.5 text-[10px] text-muted-foreground
             px-2 py-1 rounded-md transition-colors;
    }
    .mobile-bottom-nav a.active,
    .mobile-bottom-nav button.active {
      @apply text-primary;
    }
    .mobile-bottom-nav svg { @apply h-5 w-5; }

    .section-card { @apply rounded-lg mx-2; }
    .table-responsive { @apply overflow-x-auto -mx-2 px-2; }
    .responsive-stack { @apply flex-col; }
    .desktop-only { @apply hidden; }

    input[type="text"],
    input[type="number"],
    input[type="search"],
    textarea,
    select {
      font-size: 16px !important;
    }

    .has-bottom-nav { padding-bottom: 56px; }
  }

  @media (min-width: 768px) {
    .mobile-only { @apply hidden; }
  }

  .safe-area-bottom {
    padding-bottom: env(safe-area-inset-bottom, 0px);
  }

  /* ── Tab system ────────────────────────────────────────────────── */
  .tab-bar {
    @apply flex shrink-0 bg-card/50 rounded-t-lg overflow-hidden;
  }
  .tab-item {
    @apply flex items-center justify-center gap-1.5 px-3 py-2 text-[11px] font-medium
           transition-all duration-150 border-b-2 border-transparent
           text-muted-foreground hover:text-foreground hover:bg-muted/50;
  }
  .tab-item.active {
    @apply text-primary border-primary bg-primary/[0.08];
  }

  /* ── Sidebar navigation ────────────────────────────────────────── */
  .sidebar-nav-item {
    @apply flex items-center rounded-r-md text-xs font-medium transition-all duration-150 border-l-2
           text-muted-foreground hover:bg-muted/60 hover:text-foreground border-l-transparent;
  }
  .sidebar-nav-item.active {
    @apply bg-primary/[0.08] text-primary border-l-primary;
  }

  /* ── Empty state ───────────────────────────────────────────────── */
  .empty-state {
    @apply flex flex-col items-center justify-center py-12 px-4 text-center;
  }
  .empty-state-icon {
    @apply h-8 w-8 text-muted-foreground/20 mb-3;
  }
  .empty-state-text {
    @apply text-xs text-muted-foreground;
  }
  .empty-state-hint {
    @apply text-[11px] text-muted-foreground/40 mt-1;
  }

  /* ── Message/info bar ──────────────────────────────────────────── */
  .message-bar {
    @apply px-3 py-1.5 text-xs border-b shrink-0;
  }
  .message-bar.success { @apply bg-success/10 text-success border-success/20; }
  .message-bar.error { @apply bg-danger/10 text-danger border-danger/20; }
  .message-bar.warning { @apply bg-warning/10 text-warning border-warning/20; }

  /* ── Input system ──────────────────────────────────────────────── */
  .input {
    @apply w-full rounded-md border border-border/70 bg-surface-1 px-3 py-1.5 text-sm
           outline-none transition-all duration-150 font-mono
           placeholder:text-muted-foreground/30
           focus:border-primary/60 focus:ring-2 focus:ring-primary/15
           disabled:cursor-not-allowed disabled:opacity-40;
    color-scheme: dark;
  }

  /* ── Data table (financial data, compact) ──────────────────────── */
  .data-table {
    @apply w-full text-xs border-collapse;
  }
  .data-table th {
    @apply text-[11px] font-medium text-muted-foreground text-left px-3 py-1.5
           bg-muted/20 border-b border-border/50 sticky top-0 z-10;
  }
  .data-table td {
    @apply px-3 py-1.5 border-b border-border/20 text-xs tabular-nums font-mono;
  }
  .data-table tr:hover td {
    @apply bg-primary/[0.04];
  }
  .data-table .numeric {
    @apply text-right font-mono;
  }

  /* ── Skeleton shimmer ──────────────────────────────────────────── */
  .skeleton-shimmer {
    @apply relative overflow-hidden bg-muted/30 rounded-md;
    background-size: 200% 100%;
    background-image: linear-gradient(
      90deg,
      transparent 0%,
      hsl(var(--muted-foreground) / 0.06) 50%,
      transparent 100%
    );
    animation: shimmer 2s infinite linear;
  }

  /* ── Page enter animations ─────────────────────────────────────── */
  @keyframes fade-in-up {
    from { opacity: 0; transform: translateY(6px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  .page-enter {
    animation: fade-in-up 0.25s ease-out;
  }
  .page-enter-stagger > * {
    opacity: 0;
    animation: fade-in-up 0.25s ease-out forwards;
  }
  .page-enter-stagger > *:nth-child(1) { animation-delay: 0ms; }
  .page-enter-stagger > *:nth-child(2) { animation-delay: 50ms; }
  .page-enter-stagger > *:nth-child(3) { animation-delay: 100ms; }
  .page-enter-stagger > *:nth-child(4) { animation-delay: 150ms; }
  .page-enter-stagger > *:nth-child(5) { animation-delay: 200ms; }
  .page-enter-stagger > *:nth-child(6) { animation-delay: 250ms; }
}
```

- [ ] **Step 2: Verify CSS compiles**

Run: `cd frontend && npx vite build --mode development 2>&1 | tail -5`
Expected: Build succeeds, no CSS errors.

- [ ] **Step 3: Visual smoke test**

Run: `cd frontend && npx vite --port 5899`
Open in browser. Verify: dark background, orange accents, new fonts. All pages should render (even if layout needs work — that's Phase 2).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/index.css
git commit -m "feat(oled): rewrite CSS tokens for OLED dark theme with orange accent"
```

---

### Task 1.4: Rewrite chart theme for OLED dark

**Files:**
- Modify: `frontend/src/lib/chart-theme.ts` (entire file)

- [ ] **Step 1: Rewrite chart-theme.ts with OLED dark values**

```typescript
function css(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function hslToHex(hsl: string): string {
  if (!hsl) return "";
  const [h, s, l] = hsl.split(/\s+/).map(parseFloat);
  if (isNaN(h)) return "";
  const a = (s / 100) * Math.min(l / 100, 1 - l / 100);
  const f = (n: number) => {
    const k = (n + h / 30) % 12;
    const color = l / 100 - a * Math.max(Math.min(k - 3, 9 - k, 1), -1);
    return Math.round(255 * color).toString(16).padStart(2, "0");
  };
  return `#${f(0)}${f(8)}${f(4)}`;
}

function isChinese(): boolean {
  if (localStorage.getItem("qa-lang") === "zh") return true;
  if (localStorage.getItem("qa-lang") === "en") return false;
  return (document.documentElement.lang || navigator.language || "").startsWith("zh");
}

let _cache: ReturnType<typeof buildTheme> | null = null;
let _cacheKey = "";

function buildTheme() {
  const cn = isChinese();

  // OLED dark chart colors (no light mode)
  const gridHex = hslToHex(css("--chart-grid")) || "#1E293B";
  const textHex = hslToHex(css("--chart-text")) || "#94A3B8";
  const axisHex = hslToHex(css("--chart-axis")) || "#272F42";
  const successHex = hslToHex(css("--success")) || "#22C55E";
  const dangerHex = hslToHex(css("--danger")) || "#EF4444";
  const infoHex = hslToHex(css("--info")) || "#3B82F6";
  const warningHex = hslToHex(css("--warning")) || "#F59E0B";
  const primaryHex = hslToHex(css("--primary")) || "#FB923C";
  const bgHex = "#020617";

  // Locale-aware candlestick colors
  const upHex = cn ? dangerHex : successHex;
  const downHex = cn ? successHex : dangerHex;

  return {
    // ECharts background
    backgroundColor: bgHex,

    // Grid & axes
    gridColor: gridHex,
    textColor: textHex,
    axisColor: axisHex,
    axisLabelColor: textHex,

    // Candlestick
    upColor: upHex,
    downColor: downHex,

    // MA lines
    maColors: [warningHex, "#8b5cf6", infoHex],

    // Bollinger band
    bollColor: "rgba(99,102,241,0.35)",

    // Volume bars
    volumeUp: upHex + "55",
    volumeDown: downHex + "55",

    // Crosshair & tooltip
    crosshairColor: "#334155",
    tooltipBg: "rgba(15,23,42,0.97)",
    tooltipBorder: "#334155",
    tooltipText: "#E2E8F0",
    tooltipSecondary: "#94A3B8",

    // Semantics
    infoColor: infoHex,
    warningColor: warningHex,
    primaryColor: primaryHex,
  };
}

export function getChartTheme() {
  const key = `${document.documentElement.lang || navigator.language}|${localStorage.getItem("qa-lang") || ""}`;
  if (_cache && _cacheKey === key) return _cache;
  _cache = buildTheme();
  _cacheKey = key;
  return _cache;
}
```

- [ ] **Step 2: Verify no import errors**

Run: `cd frontend && npx tsc --noEmit 2>&1 | grep -i "chart-theme" || echo "No chart-theme errors"`
Expected: No errors referencing chart-theme.ts.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/chart-theme.ts
git commit -m "feat(oled): rewrite chart theme for OLED dark with locale-aware candlestick colors"
```

---

### Task 1.5: Simplify useDarkMode to always-dark

**Files:**
- Modify: `frontend/src/hooks/useDarkMode.ts`

- [ ] **Step 1: Replace hook implementation**

```typescript
import { useEffect } from "react";

/**
 * OLED terminal is always dark. This hook exists for backward compatibility
 * — components that call useDarkMode() will always receive dark=true.
 * The toggle is a no-op (can be restored if light mode is re-added later).
 */
export function useDarkMode() {
  useEffect(() => {
    document.documentElement.classList.add("dark");
  }, []);

  return {
    dark: true as const,
    toggle: () => {
      // No-op: OLED terminal is always dark
    },
  };
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npx tsc --noEmit 2>&1 | grep -i "useDarkMode\|darkMode" || echo "No useDarkMode errors"`
Expected: No new type errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useDarkMode.ts
git commit -m "feat(oled): simplify useDarkMode to always-dark for OLED terminal"
```

---

## Phase 2: Layout & Navigation

### Task 2.1: Rewrite Layout shell

**Files:**
- Modify: `frontend/src/components/layout/Layout.tsx`

- [ ] **Step 1: Rewrite Layout with compact OLED sidebar + header**

Key changes from current Layout:
- Sidebar width: 220px (was ~260px), collapsed: 52px (was 56px)
- Header height: 48px, merged with top bar
- Remove dark mode toggle button
- Remove theme-related localStorage keys
- Sidebar nav items: 36px height, 12px font, 2px left border active indicator
- Bottom section: user area with simplified avatar
- Mobile: use BottomTabBar component (Task 2.2)

```typescript
import { useEffect, useMemo, useState } from "react";
import { Link, Outlet, useLocation, useSearchParams } from "react-router-dom";
import {
  BarChart3, Bot, Database, FolderOpen, LayoutDashboard, Menu,
  Search, Plus, Trash2, Pencil, MessageSquare,
  ChevronsLeft, ChevronsRight, Settings, LogOut, User, X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n";
import { api, type SessionItem } from "@/lib/api";
import { useAgentStore } from "@/stores/agent";
import { useAuthStore } from "@/stores/auth";
import { ConnectionBanner } from "@/components/layout/ConnectionBanner";
import { PostLoginSetup } from "@/components/layout/PostLoginSetup";
import { BottomTabBar } from "@/components/layout/BottomTabBar";

const MAIN_NAV_KEYS = [
  { to: "/", icon: LayoutDashboard, i18nKey: "dashboard" as const },
  { to: "/trading", icon: BarChart3, i18nKey: "trading" as const },
  { to: "/strategy-lab", icon: FolderOpen, i18nKey: "strategyLab" as const },
  { to: "/factor-mining", icon: Database, i18nKey: "factorMining" as const },
  { to: "/agent", icon: Bot, i18nKey: "agent" as const },
];

const SECONDARY_NAV_KEYS = [
  { to: "/data-sources", icon: Database, i18nKey: "dataSources" as const },
  { to: "/settings", icon: Settings, i18nKey: "settings" as const },
];

export function Layout() {
  const { pathname } = useLocation();
  const [searchParams] = useSearchParams();
  const { t, lang, setLang } = useI18n();
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(true);
  const sseStatus = useAgentStore(s => s.sseStatus);
  const user = useAuthStore(s => s.user);
  const logout = useAuthStore(s => s.logout);
  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem("sidebar-collapsed") === "true"
  );
  const [mobileOpen, setMobileOpen] = useState(false);

  const activeSessionId = searchParams.get("session");

  useEffect(() => {
    localStorage.setItem("sidebar-collapsed", String(collapsed));
  }, [collapsed]);

  const loadSessions = () => {
    api.listSessions()
      .then((list) => setSessions(Array.isArray(list) ? list : []))
      .catch(() => {})
      .finally(() => setSessionsLoading(false));
  };

  const isAgentPage = pathname === "/agent";
  useEffect(() => { loadSessions(); }, [isAgentPage, activeSessionId]);

  const [sessionFilter, setSessionFilter] = useState("");
  const filteredSessions = useMemo(() => {
    if (!sessionFilter.trim()) return sessions;
    const q = sessionFilter.toLowerCase();
    return sessions.filter(
      s => (s.title || s.session_id).toLowerCase().includes(q)
    );
  }, [sessions, sessionFilter]);

  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [renameTarget, setRenameTarget] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");

  const deleteSession = async (sid: string) => {
    try {
      await api.deleteSession(sid);
      setSessions((prev) => prev.filter((s) => s.session_id !== sid));
    } catch { /* ignore */ }
    setDeleteTarget(null);
  };

  const renameSession = async (sid: string) => {
    if (!renameValue.trim()) { setRenameTarget(null); return; }
    try {
      await api.renameSession(sid, renameValue.trim());
      setSessions((prev) =>
        prev.map((s) =>
          s.session_id === sid ? { ...s, title: renameValue.trim() } : s
        )
      );
    } catch { /* ignore */ }
    setRenameTarget(null);
  };

  // Determine active nav item
  const isActive = (to: string) => {
    if (to === "/") return pathname === "/" || pathname === "/dashboard";
    return pathname.startsWith(to);
  };

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <ConnectionBanner />
      <PostLoginSetup />

      {/* Desktop Sidebar */}
      <aside
        className={cn(
          "hidden md:flex flex-col bg-surface-1 border-r border-border-subtle transition-all duration-200 shrink-0",
          collapsed ? "w-[52px]" : "w-[220px]"
        )}
      >
        {/* Logo */}
        <div className={cn(
          "flex items-center h-12 border-b border-border-subtle shrink-0",
          collapsed ? "justify-center px-2" : "px-3 gap-2"
        )}>
          <div className="h-6 w-6 rounded bg-primary flex items-center justify-center shrink-0">
            <span className="text-[10px] font-bold text-white">A</span>
          </div>
          {!collapsed && (
            <span className="font-semibold text-sm tracking-tight">AStockPursue</span>
          )}
        </div>

        {/* Primary Nav */}
        <nav className={cn("py-1.5", collapsed ? "px-1.5" : "px-2")}>
          {MAIN_NAV_KEYS.map(({ to, icon: Icon, i18nKey }) => {
            const active = isActive(to);
            return (
              <Link
                key={to}
                to={to}
                className={cn(
                  "sidebar-nav-item",
                  collapsed ? "justify-center h-9 w-9 mx-auto rounded-md border-l-0" : "h-9 px-3 gap-2.5"
                )}
                title={collapsed ? t[i18nKey] : undefined}
              >
                <Icon className={cn("shrink-0", active ? "h-[18px] w-[18px]" : "h-4 w-4")} aria-hidden="true" />
                {!collapsed && <span>{t[i18nKey]}</span>}
              </Link>
            );
          })}
        </nav>

        {/* Secondary Nav */}
        <div className={cn("py-1.5 border-t border-border-subtle", collapsed ? "px-1.5" : "px-2")}>
          {SECONDARY_NAV_KEYS.map(({ to, icon: Icon, i18nKey }) => {
            const active = isActive(to);
            return (
              <Link
                key={to}
                to={to}
                className={cn(
                  "sidebar-nav-item",
                  collapsed ? "justify-center h-9 w-9 mx-auto rounded-md border-l-0" : "h-9 px-3 gap-2.5"
                )}
                title={collapsed ? t[i18nKey] : undefined}
              >
                <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                {!collapsed && <span>{t[i18nKey]}</span>}
              </Link>
            );
          })}
        </div>

        {/* Collapse toggle */}
        <div className="mt-auto p-1.5 border-t border-border-subtle">
          <button
            onClick={() => setCollapsed(c => !c)}
            className="w-full h-8 flex items-center justify-center rounded-md text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors"
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? <ChevronsRight className="h-4 w-4" /> : <ChevronsLeft className="h-4 w-4" />}
          </button>
        </div>

        {/* User area */}
        {user && !collapsed && (
          <div className="p-2 border-t border-border-subtle flex items-center gap-2">
            <div className="h-7 w-7 rounded-full bg-primary/20 flex items-center justify-center text-primary text-xs font-bold shrink-0">
              {(user.username || "U")[0].toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-xs font-medium truncate">{user.username}</div>
            </div>
            <button onClick={logout} className="p-1 text-muted-foreground hover:text-foreground rounded" title="Logout">
              <LogOut className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
        {user && collapsed && (
          <div className="p-1.5 border-t border-border-subtle flex justify-center">
            <button onClick={logout} className="p-1.5 text-muted-foreground hover:text-foreground rounded" title="Logout">
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        )}
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top header bar */}
        <header className="h-12 shrink-0 border-b border-border-subtle flex items-center px-4 gap-3 bg-surface-1/50">
          {/* Mobile menu button */}
          <button
            className="md:hidden p-1.5 -ml-1 text-muted-foreground hover:text-foreground rounded"
            onClick={() => setMobileOpen(true)}
          >
            <Menu className="h-5 w-5" />
          </button>

          {/* Breadcrumb area (dynamic, populated by page headers) */}
          <div className="flex-1 flex items-center gap-2 text-xs text-muted-foreground">
            {/* Page title goes here via outlet context or page-header */}
          </div>

          {/* Right actions */}
          <div className="flex items-center gap-1">
            {/* Lang toggle */}
            <button
              onClick={() => setLang(lang === "zh" ? "en" : "zh")}
              className="px-2 py-1 text-[11px] text-muted-foreground hover:text-foreground rounded transition-colors"
            >
              {lang === "zh" ? "EN" : "中"}
            </button>

            {/* SSE status indicator */}
            {sseStatus && (
              <span
                className={cn(
                  "h-2 w-2 rounded-full",
                  sseStatus === "connected" ? "bg-success" :
                  sseStatus === "connecting" ? "bg-warning animate-pulse" :
                  "bg-danger"
                )}
                title={`SSE: ${sseStatus}`}
              />
            )}
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-auto">
          <Outlet />
        </main>

        {/* Mobile bottom tab bar */}
        <BottomTabBar />
      </div>

      {/* Mobile sidebar overlay */}
      {mobileOpen && (
        <div className="md:hidden fixed inset-0 z-50 flex">
          <div
            className="absolute inset-0 bg-black/60"
            onClick={() => setMobileOpen(false)}
          />
          <aside className="relative w-64 bg-surface-1 border-r border-border-subtle flex flex-col h-full animate-slide-in-left">
            {/* Mobile sidebar content — simplified version of desktop sidebar */}
            <div className="flex items-center justify-between h-12 px-3 border-b border-border-subtle">
              <div className="flex items-center gap-2">
                <div className="h-6 w-6 rounded bg-primary flex items-center justify-center">
                  <span className="text-[10px] font-bold text-white">A</span>
                </div>
                <span className="font-semibold text-sm">AStockPursue</span>
              </div>
              <button onClick={() => setMobileOpen(false)} className="p-1 text-muted-foreground hover:text-foreground">
                <X className="h-5 w-5" />
              </button>
            </div>
            <nav className="flex-1 py-2 px-2 space-y-0.5">
              {[...MAIN_NAV_KEYS, ...SECONDARY_NAV_KEYS].map(({ to, icon: Icon, i18nKey }) => (
                <Link
                  key={to}
                  to={to}
                  onClick={() => setMobileOpen(false)}
                  className={cn(
                    "sidebar-nav-item h-10 px-3 gap-2.5 rounded-r-md"
                  )}
                >
                  <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                  <span>{t[i18nKey]}</span>
                </Link>
              ))}
            </nav>
            {user && (
              <div className="p-3 border-t border-border-subtle flex items-center gap-2">
                <div className="h-7 w-7 rounded-full bg-primary/20 flex items-center justify-center text-primary text-xs font-bold">
                  {(user.username || "U")[0].toUpperCase()}
                </div>
                <span className="text-xs">{user.username}</span>
                <button onClick={logout} className="ml-auto p-1 text-muted-foreground hover:text-foreground">
                  <LogOut className="h-4 w-4" />
                </button>
              </div>
            )}
          </aside>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npx tsc --noEmit 2>&1 | head -30`
Expected: May have errors about missing BottomTabBar (created in Task 2.2) and missing i18n keys (`trading`, `strategyLab`, `factorMining`). The BottomTabBar error will be resolved in the next task. Check that i18n keys exist or note them for later.

- [ ] **Step 3: Add missing i18n keys if needed**

Check if `trading`, `strategyLab`, `factorMining` keys exist in `frontend/src/lib/i18n.tsx`. If not, add them:

```typescript
// In the en object:
trading: "Trading",
strategyLab: "Strategy Lab",
factorMining: "Factor Mining",
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/layout/Layout.tsx frontend/src/lib/i18n.tsx
git commit -m "feat(oled): rewrite Layout with compact OLED sidebar and top header"
```

---

### Task 2.2: Create BottomTabBar component

**Files:**
- Create: `frontend/src/components/layout/BottomTabBar.tsx`

- [ ] **Step 1: Create BottomTabBar component**

```typescript
import { Link, useLocation } from "react-router-dom";
import { LayoutDashboard, BarChart3, FolderOpen, Bot, Menu } from "lucide-react";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n";

const MOBILE_NAV = [
  { to: "/", icon: LayoutDashboard, i18nKey: "dashboard" as const },
  { to: "/trading", icon: BarChart3, i18nKey: "trading" as const },
  { to: "/strategy-lab", icon: FolderOpen, i18nKey: "strategyLab" as const },
  { to: "/agent", icon: Bot, i18nKey: "agent" as const },
  { to: "/settings", icon: Menu, i18nKey: "settings" as const },
];

export function BottomTabBar() {
  const { pathname } = useLocation();
  const { t } = useI18n();

  const isActive = (to: string) => {
    if (to === "/") return pathname === "/" || pathname === "/dashboard";
    return pathname.startsWith(to);
  };

  return (
    <nav className="mobile-bottom-nav md:hidden">
      {MOBILE_NAV.map(({ to, icon: Icon, i18nKey }) => {
        const active = isActive(to);
        return (
          <Link
            key={to}
            to={to}
            className={cn(active && "active")}
          >
            <Icon className="h-5 w-5" aria-hidden="true" />
            <span>{t[i18nKey]}</span>
          </Link>
        );
      })}
    </nav>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npx tsc --noEmit 2>&1 | grep -i "BottomTabBar" || echo "No BottomTabBar errors"`
Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/layout/BottomTabBar.tsx
git commit -m "feat(oled): add BottomTabBar mobile navigation component"
```

---

### Task 2.3: Create Breadcrumb component

**Files:**
- Create: `frontend/src/components/layout/Breadcrumb.tsx`

- [ ] **Step 1: Create Breadcrumb component**

```typescript
import { Link } from "react-router-dom";
import { ChevronRight, Home } from "lucide-react";
import { cn } from "@/lib/utils";

export interface BreadcrumbItem {
  label: string;
  to?: string;
}

interface BreadcrumbProps {
  items: BreadcrumbItem[];
  className?: string;
}

export function Breadcrumb({ items, className }: BreadcrumbProps) {
  return (
    <nav aria-label="Breadcrumb" className={cn("flex items-center gap-1 text-xs", className)}>
      <Link
        to="/"
        className="text-muted-foreground hover:text-foreground transition-colors p-0.5"
      >
        <Home className="h-3.5 w-3.5" />
      </Link>
      {items.map((item, i) => (
        <span key={i} className="flex items-center gap-1">
          <ChevronRight className="h-3 w-3 text-border-strong" />
          {item.to ? (
            <Link
              to={item.to}
              className="text-muted-foreground hover:text-foreground transition-colors"
            >
              {item.label}
            </Link>
          ) : (
            <span className="text-foreground font-medium">{item.label}</span>
          )}
        </span>
      ))}
    </nav>
  );
}
```

- [ ] **Step 2: Type-check and commit**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep -i "Breadcrumb" || echo "No Breadcrumb errors"
git add frontend/src/components/layout/Breadcrumb.tsx
git commit -m "feat(oled): add Breadcrumb navigation component"
```

---

## Phase 3: Data Display Components

### Task 3.1: Add number formatting utilities

**Files:**
- Modify: `frontend/src/lib/formatters.ts` (append new exports)

- [ ] **Step 1: Append new formatting functions**

Add these functions to the end of `frontend/src/lib/formatters.ts`:

```typescript
/**
 * Format a price with currency symbol.
 * Uses Fira Code tabular-nums via the calling component's font-mono class.
 */
export function formatPrice(v: number, decimals = 2, currency = "¥"): string {
  const abs = Math.abs(v);
  const fixed = abs.toFixed(decimals);
  return `${v < 0 ? "-" : ""}${currency}${fixed}`;
}

/**
 * Format a percentage change with sign.
 * e.g., formatPercent(0.0347) → "+3.47%"
 */
export function formatPercent(v: number, decimals = 2): string {
  const sign = v > 0 ? "+" : "";
  return `${sign}${(v * 100).toFixed(decimals)}%`;
}

/**
 * Format volume with appropriate suffix (K, M, B).
 */
export function formatVolume(v: number): string {
  const abs = Math.abs(v);
  if (abs >= 1e9) return (v / 1e9).toFixed(2) + "B";
  if (abs >= 1e6) return (v / 1e6).toFixed(2) + "M";
  if (abs >= 1e4) return (v / 1e3).toFixed(0) + "K";
  return v.toLocaleString();
}

/**
 * Format a large number with abbreviated suffix (Chinese units: 万/亿).
 * Used for A-share volume and turnover displays.
 */
export function formatLargeNum(v: number): string {
  const abs = Math.abs(v);
  if (abs >= 1e8) return (v / 1e8).toFixed(2) + "亿";
  if (abs >= 1e4) return (v / 1e4).toFixed(2) + "万";
  return v.toLocaleString();
}

/**
 * Get the CSS color class for a directional value.
 * Respects Chinese market convention via html[lang="zh"] CSS vars.
 */
export function directionColor(v: number): "text-up" | "text-down" | "" {
  if (v > 0) return "text-up";
  if (v < 0) return "text-down";
  return "";
}

/**
 * Get the CSS color class for profit/loss sentiment.
 */
export function pnlColor(v: number): "text-up" | "text-down" | "text-muted-foreground" {
  if (v > 0) return "text-up";
  if (v < 0) return "text-down";
  return "text-muted-foreground";
}
```

Add the corresponding Tailwind utility classes for `text-up` and `text-down` if they don't exist. Check `tailwind.config.ts` — if not present, add under `extend.colors`:

Actually, since we're using CSS variables `--up` and `--down`, we need to add these as Tailwind colors. In `tailwind.config.ts`, verify these exist:

```typescript
// In the colors section of tailwind.config.ts:
up: "hsl(var(--up))",
down: "hsl(var(--down))",
```

These should already be present. Verify they are.

- [ ] **Step 2: Type-check**

Run: `cd frontend && npx tsc --noEmit 2>&1 | grep "formatters" || echo "No formatter errors"`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/formatters.ts
git commit -m "feat(oled): add price/percent/volume formatters for OLED terminal"
```

---

### Task 3.2: Create useCountUp hook

**Files:**
- Create: `frontend/src/hooks/useCountUp.ts`

- [ ] **Step 1: Create count-up animation hook**

```typescript
import { useEffect, useRef, useState } from "react";

interface UseCountUpOptions {
  /** Target value to animate to */
  to: number;
  /** Animation duration in ms (default: 200) */
  duration?: number;
  /** Start from this value (default: 0) */
  from?: number;
  /** Decimals to display (default: 0) */
  decimals?: number;
  /** Only animate when this is true */
  enabled?: boolean;
}

/**
 * Animate a number from `from` to `to` over `duration` ms.
 * Uses requestAnimationFrame for smooth 60fps counting.
 * Respects prefers-reduced-motion: instantly snaps to `to`.
 */
export function useCountUp({
  to,
  duration = 200,
  from = 0,
  decimals = 0,
  enabled = true,
}: UseCountUpOptions): number {
  const [value, setValue] = useState(from);
  const rafRef = useRef<number | null>(null);
  const startTimeRef = useRef<number | null>(null);
  const startValueRef = useRef(from);

  useEffect(() => {
    // Respect reduced motion preference
    const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!enabled || prefersReduced) {
      setValue(to);
      startValueRef.current = to;
      return;
    }

    startValueRef.current = value;
    startTimeRef.current = null;

    const animate = (timestamp: number) => {
      if (startTimeRef.current === null) {
        startTimeRef.current = timestamp;
      }

      const elapsed = timestamp - startTimeRef.current;
      const progress = Math.min(elapsed / duration, 1);
      // ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = startValueRef.current + (to - startValueRef.current) * eased;

      setValue(Number(current.toFixed(decimals)));

      if (progress < 1) {
        rafRef.current = requestAnimationFrame(animate);
      }
    };

    rafRef.current = requestAnimationFrame(animate);

    return () => {
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
      }
    };
  }, [to, duration, decimals, enabled]);

  return value;
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npx tsc --noEmit 2>&1 | grep "useCountUp" || echo "No useCountUp errors"`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useCountUp.ts
git commit -m "feat(oled): add useCountUp hook for animated number transitions"
```

---

### Task 3.3: Create KpiCard component

**Files:**
- Create: `frontend/src/components/common/KpiCard.tsx`

- [ ] **Step 1: Create KpiCard component**

```typescript
import { type ReactNode } from "react";
import { cn } from "@/lib/utils";
import { useCountUp } from "@/hooks/useCountUp";

interface KpiCardProps {
  label: string;
  value?: number;
  formattedValue?: string;
  change?: number;
  changeLabel?: string;
  sparkline?: ReactNode;
  className?: string;
  /** Use count-up animation for value */
  animate?: boolean;
  /** Number of decimal places for animated value */
  decimals?: number;
}

export function KpiCard({
  label,
  value,
  formattedValue,
  change,
  changeLabel,
  sparkline,
  className,
  animate = false,
  decimals = 0,
}: KpiCardProps) {
  const animated = useCountUp({
    to: value ?? 0,
    duration: 200,
    decimals,
    enabled: animate && value !== undefined,
  });

  const displayValue = animate && value !== undefined
    ? animated.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
    : formattedValue ?? (value !== undefined ? value.toLocaleString() : "—");

  const isPositive = change !== undefined && change > 0;
  const isNegative = change !== undefined && change < 0;

  return (
    <div className={cn(
      "card-metric bg-card border border-border-subtle rounded-lg p-3 flex flex-col gap-1 min-w-0",
      className
    )}>
      {/* Label */}
      <span className="overline text-[10px] font-semibold uppercase tracking-[0.05em] text-muted-foreground">
        {label}
      </span>

      {/* Value */}
      <span className="font-mono text-lg font-bold text-foreground tabular-nums tracking-tight">
        {displayValue}
      </span>

      {/* Change indicator */}
      {(change !== undefined || changeLabel) && (
        <div className="flex items-center gap-1.5">
          {change !== undefined && (
            <span className={cn(
              "font-mono text-[11px] tabular-nums font-medium",
              isPositive ? "text-up" : isNegative ? "text-down" : "text-muted-foreground"
            )}>
              {isPositive ? "↑" : isNegative ? "↓" : ""}
              {change > 0 ? "+" : ""}{change.toFixed(2)}%
            </span>
          )}
          {changeLabel && (
            <span className="text-[10px] text-muted-foreground">{changeLabel}</span>
          )}
        </div>
      )}

      {/* Optional sparkline */}
      {sparkline && (
        <div className="mt-1 -mx-1">
          {sparkline}
        </div>
      )}
    </div>
  );
}

/** Grid container for KPI cards — 4 columns on desktop, 2 on mobile */
export function KpiGrid({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn(
      "grid grid-cols-2 lg:grid-cols-4 gap-2",
      className
    )}>
      {children}
    </div>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npx tsc --noEmit 2>&1 | grep "KpiCard" || echo "No KpiCard errors"`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/common/KpiCard.tsx
git commit -m "feat(oled): add KpiCard component with count-up animation support"
```

---

## Phase 4: Chart Rebase

### Task 4.1: Apply OLED theme to CandlestickChart

**Files:**
- Modify: `frontend/src/components/charts/CandlestickChart.tsx`

- [ ] **Step 1: Apply OLED dark chart theme defaults**

The chart component already uses `getChartTheme()`. After Task 1.4, the theme returns OLED dark values automatically. Verify the chart uses the theme correctly, and update any hardcoded color values.

Read the current file first, then apply these changes:

1. Replace any hardcoded light-mode colors with theme values
2. Set `backgroundColor` from `getChartTheme().backgroundColor`
3. Reduce grid line opacity for dark background
4. Set default text style to Fira Code 11px

Key code changes (apply by reading the file and editing specific sections):

```typescript
// At the top of chart option construction:
const theme = getChartTheme();

// In ECharts option:
backgroundColor: theme.backgroundColor,

// Grid:
grid: {
  top: 8,
  right: 8,
  bottom: 24,
  left: 8,
},

// Axis labels:
xAxis: {
  ...existing,
  axisLabel: {
    color: theme.textColor,
    fontSize: 10,
    fontFamily: "Fira Code",
  },
},
yAxis: {
  ...existing,
  axisLabel: {
    color: theme.textColor,
    fontSize: 10,
    fontFamily: "Fira Code",
  },
},

// Crosshair:
tooltip: {
  trigger: "axis",
  axisPointer: {
    type: "cross",
    crossStyle: { color: theme.crosshairColor },
  },
  backgroundColor: theme.tooltipBg,
  borderColor: theme.tooltipBorder,
  textStyle: {
    color: theme.tooltipText,
    fontSize: 12,
    fontFamily: "Fira Code",
  },
},
```

- [ ] **Step 2: Verify chart renders**

Run: `cd frontend && npx vite --port 5899`
Navigate to Trading or Dashboard page where CandlestickChart is used. Verify: dark background, orange MA lines, proper Chinese/English candlestick colors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/charts/CandlestickChart.tsx
git commit -m "feat(oled): apply OLED dark theme to CandlestickChart"
```

---

### Task 4.2: Apply OLED theme to EquityChart

**Files:**
- Modify: `frontend/src/components/charts/EquityChart.tsx`

- [ ] **Step 1: Apply dark theme to equity curve chart**

Same pattern as CandlestickChart — use `getChartTheme()` and apply dark background, Fira Code font, reduced padding. Key changes:

```typescript
const theme = getChartTheme();

// Option overrides:
backgroundColor: theme.backgroundColor,
grid: { top: 8, right: 8, bottom: 24, left: 8 },
textStyle: { color: theme.textColor, fontFamily: "Fira Code", fontSize: 10 },
```

- [ ] **Step 2: Verify and commit**

```bash
cd frontend && npx vite --port 5899  # verify chart renders dark
git add frontend/src/components/charts/EquityChart.tsx
git commit -m "feat(oled): apply OLED dark theme to EquityChart"
```

---

## Phase 5: Page Redesigns

### Task 5.1: Dashboard page OLED layout

**Files:**
- Modify: `frontend/src/pages/Dashboard.tsx`

- [ ] **Step 1: Apply Data-Dense OLED layout to Dashboard**

Read the current Dashboard.tsx first, then restructure:

```typescript
import { KpiCard, KpiGrid } from "@/components/common/KpiCard";
import { Breadcrumb } from "@/components/layout/Breadcrumb";
import { formatPrice, formatPercent, pnlColor } from "@/lib/formatters";

// Layout pattern:
// ┌──────────────────────────────────────────┐
// │ Breadcrumb: Home > Dashboard             │ ← page-header
// ├──────────────────────────────────────────┤
// │ [KPI 1] [KPI 2] [KPI 3] [KPI 4]         │ ← KpiGrid (4 cols)
// ├──────────────────────┬───────────────────┤
// │ Main Chart (7 cols)  │ Watchlist (5 cols)│ ← grid grid-cols-12
// ├──────────────────────┴───────────────────┤
// │ Positions Table (12 cols)                │
// ├──────────────────────────────────────────┤
// │ Recent Signals (12 cols)                 │
// └──────────────────────────────────────────┘

export default function Dashboard() {
  return (
    <div className="page-enter p-3 space-y-3">
      <Breadcrumb items={[{ label: "Dashboard" }]} />

      <KpiGrid>
        <KpiCard label="Portfolio Value" value={1234567} animate decimals={0} formattedValue="¥1,234,567" />
        <KpiCard label="Daily P&L" value={28450} animate decimals={0} change={1.82} />
        <KpiCard label="Open Positions" value={8} formattedValue="8" changeLabel="3 long · 5 short" />
        <KpiCard label="Win Rate (30D)" value={64.7} decimals={1} change={3.2} />
      </KpiGrid>

      {/* ... rest of page content using existing Dashboard logic, wrapped in OLED cards */}
    </div>
  );
}
```

The exact implementation depends on the current Dashboard.tsx content. Read it and adapt.

- [ ] **Step 2: Visually verify and commit**

```bash
cd frontend && npx vite --port 5899
# Navigate to / — verify dark layout with KPI cards
git add frontend/src/pages/Dashboard.tsx
git commit -m "feat(oled): apply OLED Data-Dense layout to Dashboard"
```

---

### Task 5.2–5.6: Remaining pages (same pattern)

For each remaining page (`Trading.tsx`, `StrategyLab.tsx`, `FactorMining.tsx`, `Agent.tsx`, `Settings.tsx`, etc.), follow the same pattern:

1. Read the current file to understand its structure
2. Wrap content in OLED card layout (`p-3 space-y-3`)
3. Replace any light-mode specific styles with dark defaults
4. Apply `page-header` class to the title area
5. Add `Breadcrumb` component at top
6. Use `font-mono` on all numeric displays
7. Verify visually
8. Commit each page separately

**File list for Phase 5:**
- `frontend/src/pages/Dashboard.tsx` (5.1 — done above)
- `frontend/src/pages/Trading.tsx` (5.2)
- `frontend/src/pages/StrategyLab.tsx` (5.3)
- `frontend/src/pages/FactorMining.tsx` (5.4)
- `frontend/src/pages/Agent.tsx` (5.5)
- `frontend/src/pages/PaperTrading.tsx` (5.6)
- `frontend/src/pages/Screener.tsx` (5.7)
- `frontend/src/pages/Settings.tsx` (5.8)
- `frontend/src/pages/Projects.tsx` (5.9)
- `frontend/src/pages/Login.tsx` (5.10)
- `frontend/src/pages/AlphaZoo.tsx` (5.11)
- `frontend/src/pages/DataSourceStatus.tsx` (5.12)
- `frontend/src/pages/Attribution.tsx` (5.13)
- `frontend/src/pages/Scheduler.tsx` (5.14)
- `frontend/src/pages/Sentiment.tsx` (5.15)
- `frontend/src/pages/Options.tsx` (5.16)
- `frontend/src/pages/Marketplace.tsx` (5.17)
- `frontend/src/pages/IndicatorLab.tsx` (5.18)
- `frontend/src/pages/Docs.tsx` (5.19)
- `frontend/src/pages/RunDetail.tsx` (5.20)
- `frontend/src/pages/Compare.tsx` (5.21)
- `frontend/src/pages/Correlation.tsx` (5.22)
- `frontend/src/pages/Workflow.tsx` (5.23)
- `frontend/src/pages/admin/UserManagement.tsx` (5.24)
- `frontend/src/pages/NotFound.tsx` (5.25)

Each page task follows this pattern (shown for Trading as example):

- [ ] Read the current page file
- [ ] Wrap content in `page-enter p-3 space-y-3`
- [ ] Add Breadcrumb with page title
- [ ] Replace light-mode styles with dark OLED tokens
- [ ] Apply `font-mono` to numbers
- [ ] Type-check: `cd frontend && npx tsc --noEmit`
- [ ] Visual verify: `cd frontend && npx vite --port 5899`
- [ ] Commit: `git commit -m "feat(oled): apply OLED layout to <PageName>"`

---

## Phase 6: Interaction Polish

### Task 6.1: Add keyboard shortcut for navigation (Cmd+K)

**Files:**
- Create: `frontend/src/components/layout/CommandPalette.tsx`
- Modify: `frontend/src/components/layout/Layout.tsx` (add import and render)

- [ ] **Step 1: Create CommandPalette**

```typescript
import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Search } from "lucide-react";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n";

interface CommandItem {
  label: string;
  to: string;
  category: string;
}

const COMMANDS: CommandItem[] = [
  { label: "Dashboard", to: "/", category: "Pages" },
  { label: "Trading", to: "/trading", category: "Pages" },
  { label: "Strategy Lab", to: "/strategy-lab", category: "Pages" },
  { label: "Factor Mining", to: "/factor-mining", category: "Pages" },
  { label: "Paper Trading", to: "/paper-trading", category: "Pages" },
  { label: "Agent", to: "/agent", category: "Pages" },
  { label: "Screener", to: "/screener", category: "Pages" },
  { label: "Settings", to: "/settings", category: "Pages" },
  { label: "Data Sources", to: "/data-sources", category: "Pages" },
  { label: "Alpha Zoo", to: "/alpha-zoo", category: "Research" },
  { label: "Indicator Lab", to: "/indicator-lab", category: "Research" },
  { label: "Attribution", to: "/attribution", category: "Analysis" },
  { label: "Correlation", to: "/correlation", category: "Analysis" },
  { label: "Compare", to: "/compare", category: "Analysis" },
  { label: "Docs", to: "/docs", category: "Other" },
];

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const location = useLocation();

  const filtered = COMMANDS.filter(
    (c) =>
      c.label.toLowerCase().includes(query.toLowerCase()) ||
      c.category.toLowerCase().includes(query.toLowerCase())
  );

  // Reset when opening/closing
  useEffect(() => {
    if (open) {
      setQuery("");
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  // Close on route change
  useEffect(() => { setOpen(false); }, [location.pathname]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
      if (e.key === "Escape" && open) {
        setOpen(false);
      }
    },
    [open]
  );

  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  const execute = (item: CommandItem) => {
    navigate(item.to);
    setOpen(false);
  };

  const handleInputKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((i) => Math.min(i + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && filtered[selectedIndex]) {
      execute(filtered[selectedIndex]);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh]">
      <div className="absolute inset-0 bg-black/60" onClick={() => setOpen(false)} />
      <div className="relative w-full max-w-md bg-surface-3 border border-border rounded-xl shadow-lg overflow-hidden animate-scale-in">
        {/* Search input */}
        <div className="flex items-center gap-2 px-3 py-2 border-b border-border-subtle">
          <Search className="h-4 w-4 text-muted-foreground shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => { setQuery(e.target.value); setSelectedIndex(0); }}
            onKeyDown={handleInputKeyDown}
            placeholder="Search pages..."
            className="flex-1 bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground/40 font-mono"
          />
          <kbd className="text-[10px] text-muted-foreground bg-surface-1 px-1.5 py-0.5 rounded font-mono">
            ESC
          </kbd>
        </div>

        {/* Results */}
        <div className="max-h-64 overflow-y-auto p-1">
          {filtered.length === 0 && (
            <div className="px-3 py-6 text-center text-xs text-muted-foreground">
              No pages found
            </div>
          )}
          {filtered.map((item, i) => (
            <button
              key={item.to}
              onClick={() => execute(item)}
              className={cn(
                "w-full flex items-center gap-3 px-3 py-2 rounded-md text-left transition-colors text-sm",
                i === selectedIndex
                  ? "bg-primary/12 text-primary"
                  : "text-foreground hover:bg-muted/60"
              )}
            >
              <span className="flex-1">{item.label}</span>
              <span className="text-[10px] text-muted-foreground">{item.category}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Add to Layout**

In `Layout.tsx`, add import and render `<CommandPalette />` inside the main div, after `</main>`.

- [ ] **Step 3: Type-check, verify, commit**

```bash
cd frontend && npx tsc --noEmit
# Verify: press Cmd+K in browser, palette opens, arrow keys + enter navigate
git add frontend/src/components/layout/CommandPalette.tsx frontend/src/components/layout/Layout.tsx
git commit -m "feat(oled): add Cmd+K CommandPalette for keyboard navigation"
```

---

### Task 6.2: Accessibility audit

- [ ] **Step 1: Run Lighthouse accessibility audit**

Open Chrome DevTools → Lighthouse → Accessibility. Target score: ≥95.

- [ ] **Step 2: Fix any issues found**

Common OLED dark mode issues to check:
- Focus rings visible on all interactive elements
- Color contrast ≥4.5:1 for all text (use DevTools contrast checker)
- All icon-only buttons have `aria-label`
- Skip-to-content link present
- `prefers-reduced-motion` respected (check with OS setting enabled)

- [ ] **Step 3: Commit fixes**

```bash
git add -A
git commit -m "fix(oled): accessibility fixes from Lighthouse audit"
```

---

### Task 6.3: Final integration test

- [ ] **Step 1: Full build check**

```bash
cd frontend && npx tsc --noEmit && npx vite build
```
Expected: Zero TypeScript errors, successful production build.

- [ ] **Step 2: Run existing tests**

```bash
cd frontend && npx vitest run
```
Expected: All tests pass.

- [ ] **Step 3: Visual walkthrough**

Start the app and manually verify each page:
- [ ] Login — dark card on dark background
- [ ] Dashboard — KPI cards, chart, watchlist
- [ ] Trading — order panel, chart
- [ ] Strategy Lab — code editor + equity chart
- [ ] Factor Mining — evolution chart + candidates table
- [ ] Agent — chat sidebar + conversation
- [ ] Settings — form in dark theme
- [ ] Mobile — BottomTabBar visible, no horizontal scroll
- [ ] Cmd+K — command palette works
- [ ] Chinese locale — red-up/green-down candlesticks

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat(oled): complete OLED trading terminal redesign"
```

---

## Summary

| Phase | Tasks | Files | Effort |
|-------|-------|-------|--------|
| 1. Token System | 5 | `index.html`, `tailwind.config.ts`, `index.css`, `chart-theme.ts`, `useDarkMode.ts` | High |
| 2. Layout | 3 | `Layout.tsx`, `BottomTabBar.tsx`, `Breadcrumb.tsx` | High |
| 3. Data Display | 3 | `formatters.ts`, `useCountUp.ts`, `KpiCard.tsx` | Medium |
| 4. Charts | 2 | `CandlestickChart.tsx`, `EquityChart.tsx` | Medium |
| 5. Pages | 25 | All page files | High (volume) |
| 6. Polish | 3 | `CommandPalette.tsx`, a11y fixes | Low |

**Total: 41 tasks across 6 phases**
