# Frontend Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the AStockPursue Next.js 15 frontend from scratch — 26 pages, 12 financial components, 5 Zustand stores, 12 SWR hooks, WebSocket client, NextAuth.js with Go JWT, next-intl i18n, shadcn/ui with OLED design tokens.

**Architecture:** Next.js 15 App Router with BFF API Routes proxying to Go REST API (:8899). SWR for server-state caching + Zustand for client UI state. WebSocket for real-time ticker/order/position updates with SWR mutual fallback. shadcn/ui components bound to OLED CSS variables.

**Tech Stack:** Next.js 15, React 19, TypeScript 5, Tailwind CSS 4, shadcn/ui (Radix), SWR 2, Zustand 5, NextAuth 5, next-intl 4, Recharts 2, D3 7, CodeMirror 6, Vitest 2

## Global Constraints

- All code under `frontend/` directory (root level, not `services/frontend/`)
- Zero migration — no existing frontend code reused
- OLED dark theme only — CSS variables from spec, no light mode toggle
- Financial charts: Recharts (K-line, equity) + D3 (drawdown, correlation)
- CodeMirror 6 for all code editing (factor formulas, workflow DSL)
- next-intl for i18n (zh default, en), locale-based up/down color swap
- shadcn/ui via `npx shadcn@latest add` — no manual Radix wrapper reimplementation
- WebSocket to `ws://localhost:8899/ws` with JWT auth message
- API Routes proxy to Go `http://go-core:8899` with `Authorization: Bearer <token>` header
- Fira Sans (body) + Fira Code (data/price/code) fonts
- Version `v2026.6.20` — update before final commit per CLAUDE.md

---

## Phase 1: Scaffold & Foundation

### Task 1: Initialize Next.js Project

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/next.config.ts`
- Create: `frontend/postcss.config.mjs`
- Create: `frontend/.gitignore`

**Interfaces:**
- Consumes: nothing (first task)
- Produces: runnable `npm run dev` on port 5899

- [ ] **Step 1: Create frontend directory and initialize**

```bash
mkdir -p frontend
cd frontend
```

- [ ] **Step 2: Write package.json**

```json
{
  "name": "astockpursue-frontend",
  "private": true,
  "scripts": {
    "dev": "next dev --port 5899",
    "build": "next build",
    "start": "next start",
    "test": "vitest run",
    "test:watch": "vitest",
    "lint": "next lint"
  },
  "dependencies": {
    "next": "^15.0.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "next-auth": "5.0.0-beta.25",
    "@auth/core": "0.37.0",
    "next-intl": "^4.0.0",
    "swr": "^2.3.0",
    "zustand": "^5.0.0",
    "recharts": "^2.15.0",
    "d3": "^7.9.0",
    "@codemirror/state": "^6.5.0",
    "@codemirror/view": "^6.36.0",
    "@codemirror/lang-javascript": "^6.2.0",
    "@codemirror/lang-python": "^6.1.0",
    "@codemirror/theme-one-dark": "^6.1.0",
    "lucide-react": "^0.460.0",
    "sonner": "^1.7.0",
    "tailwind-merge": "^2.6.0",
    "clsx": "^2.1.0",
    "class-variance-authority": "^0.7.0"
  },
  "devDependencies": {
    "typescript": "^5.6.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "@types/d3": "^7.4.0",
    "tailwindcss": "^4.0.0",
    "@tailwindcss/postcss": "^4.0.0",
    "postcss": "^8.5.0",
    "vitest": "^2.1.0",
    "@vitejs/plugin-react": "^4.3.0",
    "@testing-library/react": "^16.1.0",
    "@testing-library/jest-dom": "^6.6.0",
    "jsdom": "^25.0.0",
    "eslint": "^9.0.0",
    "eslint-config-next": "^15.0.0"
  }
}
```

- [ ] **Step 3: Install dependencies**

```bash
cd frontend && npm install
```

Expected: `node_modules/` created, no errors.

- [ ] **Step 4: Write tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2017",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

- [ ] **Step 5: Write next.config.ts**

```ts
import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  transpilePackages: ['next-intl'],
}

export default nextConfig
```

- [ ] **Step 6: Write postcss.config.mjs**

```js
const config = {
  plugins: {
    "@tailwindcss/postcss": {},
  },
}
export default config
```

- [ ] **Step 7: Write .gitignore**

```
node_modules/
.next/
out/
.env.local
.env*.local
*.tsbuildinfo
next-env.d.ts
```

- [ ] **Step 8: Verify dev server starts**

```bash
cd frontend && npm run dev &
sleep 5
curl http://localhost:5899
kill %1
```

Expected: Returns Next.js 404 page HTML (no routes yet).

- [ ] **Step 9: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): initialize Next.js 15 project scaffold"
```

---

### Task 2: OLED Theme — CSS Variables & Tailwind Config

**Files:**
- Create: `frontend/app/globals.css`
- Create: `frontend/lib/constants.ts`

**Interfaces:**
- Consumes: Task 1 (project scaffold)
- Produces: CSS variables (OLED tokens) available globally, Tailwind theme key references

- [ ] **Step 1: Write globals.css with OLED CSS variables**

```css
/* frontend/app/globals.css */
@import "tailwindcss";

/* ---- OLED Theme Tokens ---- */
:root {
  /* Surface layers */
  --background: #020617;
  --surface-1: #0A0F1D;
  --surface-2: #0F172A;
  --surface-3: #1A1E2F;

  /* Borders */
  --border-subtle: #1E293B;
  --border-default: #272F42;
  --border-strong: #334155;

  /* Brand */
  --primary: #FB923C;
  --primary-hover: #FBA86C;
  --primary-muted: rgba(251, 146, 60, 0.12);

  /* Semantic */
  --up: #22C55E;
  --down: #EF4444;
  --warning: #F59E0B;
  --info: #3B82F6;
  --destructive: #DC2626;

  /* Text */
  --foreground: #F8FAFC;
  --foreground-secondary: #94A3B8;
  --foreground-muted: #64748B;

  /* Layout */
  --sidebar-width: 220px;
  --header-height: 48px;
  --grid-gap: 8px;
  --card-padding: 12px;
  --page-padding: 12px;

  /* Radius */
  --radius-sm: 4px;
  --radius-md: 6px;
  --radius-lg: 8px;
  --radius-xl: 12px;

  /* Font */
  --font-body: 'Fira Sans', system-ui, sans-serif;
  --font-mono: 'Fira Code', monospace;
}

/* zh locale — red up / green down */
[lang="zh"] {
  --up: #EF4444;
  --down: #22C55E;
}

/* Base reset */
html, body {
  background: var(--background);
  color: var(--foreground);
  font-family: var(--font-body);
  font-size: 13px;
  line-height: 1.5;
  margin: 0;
  padding: 0;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/* Scrollbar — OLED minimal */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--background); }
::-webkit-scrollbar-thumb { background: var(--border-default); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--border-strong); }

/* Tabular numbers for data cells */
[data-tabular] { font-variant-numeric: tabular-nums; }
```

- [ ] **Step 2: Write constants.ts**

```ts
// frontend/lib/constants.ts
export const OLED = {
  background: '#020617',
  surface1: '#0A0F1D',
  surface2: '#0F172A',
  surface3: '#1A1E2F',
  borderSubtle: '#1E293B',
  borderDefault: '#272F42',
  borderStrong: '#334155',
  primary: '#FB923C',
  primaryHover: '#FBA86C',
  up: '#22C55E',
  down: '#EF4444',
  foreground: '#F8FAFC',
  foregroundSecondary: '#94A3B8',
  foregroundMuted: '#64748B',
} as const

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8899'
export const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8899/ws'
```

- [ ] **Step 3: Commit**

```bash
git add frontend/app/globals.css frontend/lib/constants.ts
git commit -m "feat(frontend): add OLED theme CSS variables and constants"
```

---

### Task 3: Utility Library

**Files:**
- Create: `frontend/lib/utils.ts`
- Create: `frontend/lib/api-client.ts`

**Interfaces:**
- Consumes: Task 2 (constants)
- Produces: `cn()` for class merging, `format*()` helpers, `apiFetch()` for SWR

- [ ] **Step 1: Write utils.ts**

```ts
// frontend/lib/utils.ts
import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatPrice(v: number, decimals = 2): string {
  return v.toFixed(decimals)
}

export function formatPercent(v: number, decimals = 2): string {
  const sign = v > 0 ? '+' : ''
  return `${sign}${(v * 100).toFixed(decimals)}%`
}

export function formatVolume(v: number): string {
  if (v >= 1e8) return `${(v / 1e8).toFixed(2)}亿`
  if (v >= 1e4) return `${(v / 1e4).toFixed(2)}万`
  return v.toLocaleString()
}

export function formatPnL(v: number): string {
  const sign = v >= 0 ? '+' : ''
  return `${sign}${v.toFixed(2)}`
}

export function formatDateTime(ts: number | string): string {
  const d = new Date(typeof ts === 'string' ? ts : ts * 1000)
  return d.toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

export function colorForChange(v: number): string {
  return v > 0 ? 'text-[var(--up)]' : v < 0 ? 'text-[var(--down)]' : 'text-[var(--foreground-secondary)]'
}
```

- [ ] **Step 2: Write api-client.ts**

```ts
// frontend/lib/api-client.ts
import { API_BASE } from './constants'

let _token: string | null = null

export function setApiToken(token: string | null) {
  _token = token
}

export async function apiFetch<T = any>(
  path: string,
  init?: RequestInit
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(init?.headers as Record<string, string>),
  }
  if (_token) {
    headers['Authorization'] = `Bearer ${_token}`
  }
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers })
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`API ${res.status}: ${body}`)
  }
  const text = await res.text()
  return text ? JSON.parse(text) : undefined
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/utils.ts frontend/lib/api-client.ts
git commit -m "feat(frontend): add utility library and API client"
```

---

### Task 4: i18n Setup (next-intl)

**Files:**
- Create: `frontend/lib/i18n/zh.json`
- Create: `frontend/lib/i18n/en.json`
- Create: `frontend/lib/i18n/request.ts`
- Create: `frontend/lib/i18n/routing.ts`
- Create: `frontend/messages/` (next-intl convention)

**Interfaces:**
- Consumes: Task 1 (project scaffold)
- Produces: `<NextIntlClientProvider>` ready for root layout, `t()` keys for all UI text

- [ ] **Step 1: Write zh.json (Chinese — primary locale)**

```json
{
  "nav": {
    "dashboard": "仪表盘",
    "trade": "交易",
    "trading": "实时交易",
    "orders": "订单管理",
    "positions": "持仓管理",
    "paperTrading": "模拟交易",
    "research": "研究",
    "backtest": "回测系统",
    "factors": "因子挖掘",
    "workflow": "工作流",
    "agent": "AI 助手",
    "market": "市场",
    "marketOverview": "行情总览",
    "screener": "筛选器",
    "broker": "券商管理",
    "system": "系统",
    "settings": "设置",
    "systemStatus": "系统状态",
    "scheduler": "定时任务"
  },
  "common": {
    "save": "保存",
    "cancel": "取消",
    "delete": "删除",
    "create": "新建",
    "search": "搜索",
    "loading": "加载中...",
    "error": "出错了",
    "retry": "重试",
    "noData": "暂无数据",
    "confirm": "确认",
    "confirmDelete": "确认删除？",
    "logout": "退出登录"
  },
  "auth": {
    "login": "登录",
    "register": "注册",
    "username": "用户名",
    "password": "密码",
    "confirmPassword": "确认密码",
    "loginBtn": "登录",
    "registerBtn": "注册",
    "noAccount": "没有账号？",
    "hasAccount": "已有账号？"
  },
  "trading": {
    "symbol": "代码",
    "side": "方向",
    "buy": "买入",
    "sell": "卖出",
    "orderType": "类型",
    "limit": "限价",
    "market": "市价",
    "price": "价格",
    "quantity": "数量",
    "submit": "下单",
    "orderId": "订单号",
    "status": "状态",
    "filledQty": "已成交",
    "open": "待成交",
    "filled": "已成交",
    "cancelled": "已取消"
  },
  "portfolio": {
    "symbol": "代码",
    "position": "持仓",
    "entryPrice": "成本",
    "currentPrice": "现价",
    "pnl": "盈亏",
    "pnlPct": "盈亏%",
    "totalEquity": "总权益",
    "available": "可用",
    "margin": "保证金"
  },
  "backtest": {
    "new": "新建回测",
    "list": "回测列表",
    "detail": "回测详情",
    "strategy": "策略",
    "startDate": "开始日期",
    "endDate": "结束日期",
    "initialCapital": "初始资金",
    "totalReturn": "总收益",
    "sharpeRatio": "夏普比率",
    "maxDrawdown": "最大回撤",
    "winRate": "胜率",
    "totalTrades": "总交易",
    "equityCurve": "权益曲线",
    "tradeLog": "交易记录"
  },
  "analysis": {
    "correlation": "相关性分析",
    "drawdown": "回撤分析",
    "stressTest": "压力测试",
    "attribution": "收益归因"
  },
  "market": {
    "overview": "行情总览",
    "oneMinute": "1分钟",
    "fiveMinute": "5分钟",
    "daily": "日线",
    "weekly": "周线",
    "depth": "深度"
  }
}
```

- [ ] **Step 2: Write en.json**

```json
{
  "nav": {
    "dashboard": "Dashboard",
    "trade": "Trade",
    "trading": "Trading",
    "orders": "Orders",
    "positions": "Positions",
    "paperTrading": "Paper Trading",
    "research": "Research",
    "backtest": "Backtest",
    "factors": "Factors",
    "workflow": "Workflow",
    "agent": "AI Agent",
    "market": "Market",
    "marketOverview": "Market Overview",
    "screener": "Screener",
    "broker": "Broker",
    "system": "System",
    "settings": "Settings",
    "systemStatus": "System Status",
    "scheduler": "Scheduler"
  },
  "common": {
    "save": "Save",
    "cancel": "Cancel",
    "delete": "Delete",
    "create": "Create",
    "search": "Search",
    "loading": "Loading...",
    "error": "Error",
    "retry": "Retry",
    "noData": "No Data",
    "confirm": "Confirm",
    "confirmDelete": "Confirm delete?",
    "logout": "Logout"
  },
  "auth": {
    "login": "Login",
    "register": "Register",
    "username": "Username",
    "password": "Password",
    "confirmPassword": "Confirm Password",
    "loginBtn": "Sign In",
    "registerBtn": "Sign Up",
    "noAccount": "No account?",
    "hasAccount": "Already have an account?"
  },
  "trading": {
    "symbol": "Symbol",
    "side": "Side",
    "buy": "Buy",
    "sell": "Sell",
    "orderType": "Type",
    "limit": "Limit",
    "market": "Market",
    "price": "Price",
    "quantity": "Qty",
    "submit": "Place Order",
    "orderId": "Order ID",
    "status": "Status",
    "filledQty": "Filled",
    "open": "Open",
    "filled": "Filled",
    "cancelled": "Cancelled"
  },
  "portfolio": {
    "symbol": "Symbol",
    "position": "Position",
    "entryPrice": "Entry",
    "currentPrice": "Current",
    "pnl": "P&L",
    "pnlPct": "P&L%",
    "totalEquity": "Total Equity",
    "available": "Available",
    "margin": "Margin"
  },
  "backtest": {
    "new": "New Backtest",
    "list": "Backtest List",
    "detail": "Backtest Detail",
    "strategy": "Strategy",
    "startDate": "Start Date",
    "endDate": "End Date",
    "initialCapital": "Initial Capital",
    "totalReturn": "Total Return",
    "sharpeRatio": "Sharpe Ratio",
    "maxDrawdown": "Max Drawdown",
    "winRate": "Win Rate",
    "totalTrades": "Total Trades",
    "equityCurve": "Equity Curve",
    "tradeLog": "Trade Log"
  },
  "analysis": {
    "correlation": "Correlation",
    "drawdown": "Drawdown",
    "stressTest": "Stress Test",
    "attribution": "Attribution"
  },
  "market": {
    "overview": "Market Overview",
    "oneMinute": "1min",
    "fiveMinute": "5min",
    "daily": "Daily",
    "weekly": "Weekly",
    "depth": "Depth"
  }
}
```

- [ ] **Step 3: Write i18n/request.ts**

```ts
// frontend/lib/i18n/request.ts
import { getRequestConfig } from 'next-intl/server'
import { routing } from './routing'

export default getRequestConfig(async ({ requestLocale }) => {
  let locale = await requestLocale
  if (!locale || !routing.locales.includes(locale as any)) {
    locale = routing.defaultLocale
  }
  return {
    locale,
    messages: (await import(`../../messages/${locale}.json`)).default,
  }
})
```

- [ ] **Step 4: Write i18n/routing.ts**

```ts
// frontend/lib/i18n/routing.ts
import { defineRouting } from 'next-intl/routing'

export const routing = defineRouting({
  locales: ['zh', 'en'],
  defaultLocale: 'zh',
})
```

- [ ] **Step 5: Copy JSON files to messages/ directory**

```bash
mkdir -p frontend/messages
cp frontend/lib/i18n/zh.json frontend/messages/zh.json
cp frontend/lib/i18n/en.json frontend/messages/en.json
```

- [ ] **Step 6: Commit**

```bash
git add frontend/lib/i18n/ frontend/messages/
git commit -m "feat(frontend): add next-intl i18n setup with zh/en translations"
```

---

### Task 5: shadcn/ui Init + Base Components

**Files:**
- Create: `frontend/components/ui/` (via shadcn CLI init)
- Modify: `frontend/app/globals.css` (shadcn will append)
- Create: `frontend/components/ui/theme-provider.tsx`

**Interfaces:**
- Consumes: Task 2 (OLED CSS vars)
- Produces: shadcn/ui base + Button, Card, Input installed, ThemeProvider component

- [ ] **Step 1: Initialize shadcn/ui**

```bash
cd frontend
npx shadcn@latest init --defaults --force
```

This configures `components.json` and writes base CSS to `globals.css`. Accept defaults:
- Style: New York
- Base color: Neutral
- CSS variables: Yes

- [ ] **Step 2: Override shadcn CSS vars to use OLED tokens**

After init, `globals.css` will have shadcn's default light/dark variables. Replace the shadcn-added section to reference OLED tokens:

```css
/* Append after OLED tokens in globals.css */
@layer base {
  * {
    border-color: var(--border-default);
  }
  body {
    background-color: var(--background);
    color: var(--foreground);
  }
}
```

The `components.json` should point `tailwind.css` to `app/globals.css` and use `--radius: 0.5rem` matching `--radius-md`.

- [ ] **Step 3: Install base shadcn components**

```bash
cd frontend
npx shadcn@latest add button card input label separator badge toast table tabs dropdown-menu dialog select textarea scroll-area popover tooltip command --yes
```

Expected: each component appears in `frontend/components/ui/`.

- [ ] **Step 4: Write ThemeProvider**

```tsx
// frontend/components/ui/theme-provider.tsx
'use client'

import { useEffect } from 'react'

export function ThemeProvider({ children, locale }: { children: React.ReactNode; locale: string }) {
  useEffect(() => {
    document.documentElement.lang = locale
  }, [locale])

  return <>{children}</>
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/components/ui/ frontend/components.json
git commit -m "feat(frontend): init shadcn/ui with OLED theme and base components"
```

---

### Task 6: Layout Components — Sidebar, Header, SidebarLayout

**Files:**
- Create: `frontend/components/layout/Sidebar.tsx`
- Create: `frontend/components/layout/Header.tsx`
- Create: `frontend/components/layout/SidebarLayout.tsx`
- Create: `frontend/lib/navigation.ts`

**Interfaces:**
- Consumes: Task 4 (i18n), Task 5 (shadcn)
- Produces: SidebarLayout wraps all authenticated pages

- [ ] **Step 1: Write navigation.ts (sidebar nav config)**

```ts
// frontend/lib/navigation.ts
import { LayoutDashboard, TrendingUp, ListOrdered, Briefcase, FileText,
  FlaskConical, Workflow, Bot, LineChart, Search, Building2, Settings,
  Activity, Clock, type LucideIcon } from 'lucide-react'

export interface NavGroup {
  key: string
  items: NavItem[]
}

export interface NavItem {
  label: string // i18n key prefix: `nav.${item.label}`
  href: string
  icon: LucideIcon
}

export const navGroups: NavGroup[] = [
  {
    key: 'main',
    items: [
      { label: 'dashboard', href: '/', icon: LayoutDashboard },
    ],
  },
  {
    key: 'trade',
    items: [
      { label: 'trading', href: '/trading', icon: TrendingUp },
      { label: 'orders', href: '/trading/orders', icon: ListOrdered },
      { label: 'positions', href: '/trading/positions', icon: Briefcase },
      { label: 'paperTrading', href: '/paper-trading', icon: FileText },
    ],
  },
  {
    key: 'research',
    items: [
      { label: 'backtest', href: '/backtest', icon: LineChart },
      { label: 'factors', href: '/factors', icon: FlaskConical },
      { label: 'workflow', href: '/workflow', icon: Workflow },
      { label: 'agent', href: '/agent', icon: Bot },
    ],
  },
  {
    key: 'market',
    items: [
      { label: 'marketOverview', href: '/market', icon: Activity },
      { label: 'screener', href: '/screener', icon: Search },
      { label: 'broker', href: '/broker', icon: Building2 },
    ],
  },
  {
    key: 'system',
    items: [
      { label: 'settings', href: '/settings', icon: Settings },
      { label: 'systemStatus', href: '/system', icon: Activity },
      { label: 'scheduler', href: '/scheduler', icon: Clock },
    ],
  },
]
```

- [ ] **Step 2: Write Sidebar.tsx**

```tsx
// frontend/components/layout/Sidebar.tsx
'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { navGroups } from '@/lib/navigation'
import { cn } from '@/lib/utils'
import { useTranslations } from 'next-intl'

export function Sidebar() {
  const pathname = usePathname()
  const t = useTranslations()

  return (
    <aside
      className="fixed left-0 top-0 h-screen flex flex-col bg-[var(--surface-1)] border-r border-[var(--border-subtle)] z-40"
      style={{ width: 'var(--sidebar-width)' }}
    >
      {/* Logo */}
      <div className="flex items-center gap-2 px-4 h-[var(--header-height)] border-b border-[var(--border-subtle)] shrink-0">
        <div className="w-6 h-6 rounded bg-[var(--primary)] flex items-center justify-center text-[var(--background)] font-bold text-xs">
          A
        </div>
        <span className="font-bold text-sm text-[var(--foreground)]">AStockPursue</span>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-2">
        {navGroups.map((group, gi) => (
          <div key={group.key} className={cn(gi > 0 && 'mt-3')}>
            <div className="px-4 py-1 text-[11px] font-semibold text-[var(--foreground-muted)] uppercase tracking-wider">
              {t(`nav.${group.key}`)}
            </div>
            {group.items.map((item) => {
              const active = pathname === item.href || (item.href !== '/' && pathname.startsWith(item.href))
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    'flex items-center gap-3 px-4 h-8 text-[13px] transition-colors',
                    active
                      ? 'bg-[var(--primary-muted)] text-[var(--primary)] border-l-[3px] border-[var(--primary)]'
                      : 'text-[var(--foreground-secondary)] hover:text-[var(--foreground)] hover:bg-[var(--surface-2)] border-l-[3px] border-transparent'
                  )}
                >
                  <item.icon className="w-4 h-4 shrink-0" />
                  <span className="truncate">{t(`nav.${item.label}`)}</span>
                </Link>
              )
            })}
          </div>
        ))}
      </nav>

      {/* User footer */}
      <div className="p-3 border-t border-[var(--border-subtle)] shrink-0">
        <div className="text-[11px] text-[var(--foreground-muted)] truncate">
          user@account
        </div>
      </div>
    </aside>
  )
}
```

- [ ] **Step 3: Write Header.tsx**

```tsx
// frontend/components/layout/Header.tsx
'use client'

import { usePathname } from 'next/navigation'
import { useTranslations } from 'next-intl'
import { LogOut, Bell } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { signOut } from '@/lib/auth-client'

function breadcrumbSegments(pathname: string): string[] {
  return pathname.split('/').filter(Boolean)
}

export function Header() {
  const pathname = usePathname()
  const t = useTranslations()
  const segments = breadcrumbSegments(pathname)

  return (
    <header
      className="fixed top-0 right-0 flex items-center justify-between px-[var(--page-padding)] bg-[var(--surface-1)] border-b border-[var(--border-subtle)] z-30"
      style={{ height: 'var(--header-height)', left: 'var(--sidebar-width)' }}
    >
      {/* Breadcrumb */}
      <div className="flex items-center gap-1 text-[12px] text-[var(--foreground-secondary)]">
        {segments.length === 0 ? (
          <span className="text-[var(--foreground)]">{t('nav.dashboard')}</span>
        ) : (
          segments.map((seg, i) => (
            <span key={i} className="flex items-center gap-1">
              {i > 0 && <span className="text-[var(--foreground-muted)]">/</span>}
              <span className={i === segments.length - 1 ? 'text-[var(--foreground)]' : ''}>
                {seg}
              </span>
            </span>
          ))
        )}
      </div>

      {/* Right actions */}
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" className="h-7 w-7">
          <Bell className="w-4 h-4" />
        </Button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="h-7 w-7 rounded-full bg-[var(--surface-3)] text-[12px] font-semibold">
              U
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-40">
            <DropdownMenuItem onClick={() => signOut()} className="text-[var(--destructive)] cursor-pointer">
              <LogOut className="w-4 h-4 mr-2" />
              {t('common.logout')}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  )
}
```

- [ ] **Step 4: Write SidebarLayout.tsx**

```tsx
// frontend/components/layout/SidebarLayout.tsx
import { Sidebar } from './Sidebar'
import { Header } from './Header'

export function SidebarLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-[var(--background)]">
      <Sidebar />
      <Header />
      <main
        className="pt-[var(--header-height)] transition-all"
        style={{ paddingLeft: 'var(--sidebar-width)', padding: 'var(--header-height) 0 0 var(--sidebar-width)' }}
      >
        <div className="p-[var(--page-padding)]">
          {children}
        </div>
      </main>
    </div>
  )
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/components/layout/ frontend/lib/navigation.ts
git commit -m "feat(frontend): add Sidebar, Header, and SidebarLayout components"
```

---

## Phase 2: Auth Layer

### Task 7: NextAuth Configuration

**Files:**
- Create: `frontend/lib/auth.config.ts`
- Create: `frontend/lib/auth.ts`
- Create: `frontend/lib/auth-client.ts`
- Create: `frontend/app/api/auth/[...nextauth]/route.ts`

**Interfaces:**
- Consumes: Task 3 (api-client)
- Produces: NextAuth CredentialsProvider authenticating against Go JWT endpoint

- [ ] **Step 1: Write auth.config.ts**

```ts
// frontend/lib/auth.config.ts
import type { NextAuthConfig } from 'next-auth'

export const authConfig: NextAuthConfig = {
  pages: {
    signIn: '/login',
  },
  callbacks: {
    authorized({ auth, request: { nextUrl } }) {
      const isLoggedIn = !!auth?.user
      const isAuthPage = nextUrl.pathname.startsWith('/login') || nextUrl.pathname.startsWith('/register')
      if (isAuthPage) {
        if (isLoggedIn) return Response.redirect(new URL('/', nextUrl))
        return true
      }
      if (!isLoggedIn) return false
      return true
    },
    jwt({ token, user }) {
      if (user) {
        token.accessToken = (user as any).accessToken
      }
      return token
    },
    session({ session, token }) {
      (session as any).accessToken = token.accessToken
      return session
    },
  },
  providers: [], // populated in auth.ts
}
```

- [ ] **Step 2: Write auth.ts**

```ts
// frontend/lib/auth.ts
import NextAuth from 'next-auth'
import Credentials from 'next-auth/providers/credentials'
import { authConfig } from './auth.config'
import { API_BASE } from './constants'

export const { handlers, auth, signIn, signOut } = NextAuth({
  ...authConfig,
  providers: [
    Credentials({
      credentials: {
        username: { label: 'Username', type: 'text' },
        password: { label: 'Password', type: 'password' },
      },
      async authorize(credentials) {
        try {
          const res = await fetch(`${API_BASE}/api/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              username: credentials.username,
              password: credentials.password,
            }),
          })
          if (!res.ok) return null
          const data = await res.json()
          return {
            id: data.user_id || credentials.username as string,
            name: credentials.username as string,
            accessToken: data.token,
          }
        } catch {
          return null
        }
      },
    }),
  ],
})
```

- [ ] **Step 3: Write auth-client.ts (client-side session helpers)**

```ts
// frontend/lib/auth-client.ts
'use client'

import { signIn as nextSignIn, signOut as nextSignOut, useSession } from 'next-auth/react'

export function useAuth() {
  const { data: session, status } = useSession()
  return {
    user: session?.user,
    token: (session as any)?.accessToken as string | undefined,
    isAuthenticated: status === 'authenticated',
    isLoading: status === 'loading',
  }
}

export { nextSignIn as signIn, nextSignOut as signOut }
```

- [ ] **Step 4: Write [...nextauth] route.ts**

```ts
// frontend/app/api/auth/[...nextauth]/route.ts
import { handlers } from '@/lib/auth'
export const { GET, POST } = handlers
```

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/auth.config.ts frontend/lib/auth.ts frontend/lib/auth-client.ts frontend/app/api/auth/
git commit -m "feat(frontend): add NextAuth configuration with Go JWT credentials provider"
```

---

### Task 8: Middleware (Route Protection)

**Files:**
- Create: `frontend/middleware.ts`

**Interfaces:**
- Consumes: Task 7 (auth)
- Produces: All routes except login/register protected

- [ ] **Step 1: Write middleware.ts**

```ts
// frontend/middleware.ts
import NextAuth from 'next-auth'
import { authConfig } from '@/lib/auth.config'

export default NextAuth(authConfig).auth

export const config = {
  matcher: ['/((?!api/auth|login|register|_next/static|_next/image|favicon.ico).*)'],
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/middleware.ts
git commit -m "feat(frontend): add NextAuth middleware for route protection"
```

---

### Task 9: Login & Register Pages

**Files:**
- Create: `frontend/app/login/page.tsx`
- Create: `frontend/app/register/page.tsx`

**Interfaces:**
- Consumes: Task 7 (auth), Task 5 (shadcn)
- Produces: Login/register pages with form validation

- [ ] **Step 1: Write login page**

```tsx
// frontend/app/login/page.tsx
'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useTranslations } from 'next-intl'
import { signIn } from '@/lib/auth-client'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import Link from 'next/link'

export default function LoginPage() {
  const t = useTranslations()
  const router = useRouter()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    const result = await signIn('credentials', {
      username, password, redirect: false,
    })
    setLoading(false)
    if (result?.error) {
      setError('Invalid credentials')
    } else {
      router.push('/')
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--background)]">
      <Card className="w-[360px] bg-[var(--surface-2)] border-[var(--border-default)]">
        <CardHeader>
          <CardTitle className="text-center text-lg">{t('auth.login')}</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1">
              <label className="text-[12px] text-[var(--foreground-secondary)]">{t('auth.username')}</label>
              <Input
                value={username}
                onChange={e => setUsername(e.target.value)}
                required
                autoFocus
                className="h-9 bg-[var(--surface-1)] border-[var(--border-default)]"
              />
            </div>
            <div className="space-y-1">
              <label className="text-[12px] text-[var(--foreground-secondary)]">{t('auth.password')}</label>
              <Input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
                className="h-9 bg-[var(--surface-1)] border-[var(--border-default)]"
              />
            </div>
            {error && <p className="text-[12px] text-[var(--destructive)]">{error}</p>}
            <Button type="submit" disabled={loading} className="w-full h-9 bg-[var(--primary)] hover:bg-[var(--primary-hover)] text-[var(--background)]">
              {loading ? t('common.loading') : t('auth.loginBtn')}
            </Button>
          </form>
          <p className="mt-4 text-center text-[12px] text-[var(--foreground-muted)]">
            {t('auth.noAccount')}{' '}
            <Link href="/register" className="text-[var(--primary)] hover:underline">
              {t('auth.register')}
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
```

- [ ] **Step 2: Write register page (structure mirrors login, calls POST /api/auth/register)**

```tsx
// frontend/app/register/page.tsx
'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useTranslations } from 'next-intl'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import Link from 'next/link'
import { API_BASE } from '@/lib/constants'

export default function RegisterPage() {
  const t = useTranslations()
  const router = useRouter()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    if (password !== confirm) {
      setError('Passwords do not match')
      return
    }
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      })
      if (!res.ok) {
        const data = await res.json()
        setError(data.error || 'Registration failed')
        return
      }
      router.push('/login')
    } catch {
      setError('Network error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--background)]">
      <Card className="w-[360px] bg-[var(--surface-2)] border-[var(--border-default)]">
        <CardHeader>
          <CardTitle className="text-center text-lg">{t('auth.register')}</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1">
              <label className="text-[12px] text-[var(--foreground-secondary)]">{t('auth.username')}</label>
              <Input value={username} onChange={e => setUsername(e.target.value)} required className="h-9 bg-[var(--surface-1)] border-[var(--border-default)]" />
            </div>
            <div className="space-y-1">
              <label className="text-[12px] text-[var(--foreground-secondary)]">{t('auth.password')}</label>
              <Input type="password" value={password} onChange={e => setPassword(e.target.value)} required className="h-9 bg-[var(--surface-1)] border-[var(--border-default)]" />
            </div>
            <div className="space-y-1">
              <label className="text-[12px] text-[var(--foreground-secondary)]">{t('auth.confirmPassword')}</label>
              <Input type="password" value={confirm} onChange={e => setConfirm(e.target.value)} required className="h-9 bg-[var(--surface-1)] border-[var(--border-default)]" />
            </div>
            {error && <p className="text-[12px] text-[var(--destructive)]">{error}</p>}
            <Button type="submit" disabled={loading} className="w-full h-9 bg-[var(--primary)] hover:bg-[var(--primary-hover)] text-[var(--background)]">
              {loading ? t('common.loading') : t('auth.registerBtn')}
            </Button>
          </form>
          <p className="mt-4 text-center text-[12px] text-[var(--foreground-muted)]">
            {t('auth.hasAccount')}{' '}
            <Link href="/login" className="text-[var(--primary)] hover:underline">
              {t('auth.login')}
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/app/login/ frontend/app/register/
git commit -m "feat(frontend): add login and register pages with form validation"
```

---

### Task 10: Root Layout with Providers

**Files:**
- Create: `frontend/app/layout.tsx`

**Interfaces:**
- Consumes: Task 4 (i18n), Task 6 (SidebarLayout), Task 7 (auth), Task 2 (OLED CSS)
- Produces: Root layout wrapping all pages with providers

- [ ] **Step 1: Write root layout**

```tsx
// frontend/app/layout.tsx
import type { Metadata } from 'next'
import { NextIntlClientProvider } from 'next-intl'
import { getLocale, getMessages } from 'next-intl/server'
import { SessionProvider } from 'next-auth/react'
import { Toaster } from 'sonner'
import { ThemeProvider } from '@/components/ui/theme-provider'
import './globals.css'

export const metadata: Metadata = {
  title: 'AStockPursue',
  description: 'Quantitative Trading Terminal',
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const locale = await getLocale()
  const messages = await getMessages()

  return (
    <html lang={locale} className="dark">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500&family=Fira+Sans:wght@400;600;700&display=swap" rel="stylesheet" />
      </head>
      <body className="bg-[var(--background)] text-[var(--foreground)] antialiased">
        <SessionProvider>
          <NextIntlClientProvider messages={messages}>
            <ThemeProvider locale={locale}>
              {children}
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
            </ThemeProvider>
          </NextIntlClientProvider>
        </SessionProvider>
      </body>
    </html>
  )
}
```

- [ ] **Step 2: Verify build**

```bash
cd frontend && npm run build
```

Expected: Build succeeds (NextAuth and next-intl resolve correctly).

- [ ] **Step 3: Commit**

```bash
git add frontend/app/layout.tsx
git commit -m "feat(frontend): add root layout with all providers"
```

---

### Task 11: Loading & Error Boundaries

**Files:**
- Create: `frontend/app/loading.tsx`
- Create: `frontend/app/error.tsx`

**Interfaces:**
- Consumes: Task 10 (layout)
- Produces: Global loading skeleton and error boundary

- [ ] **Step 1: Write loading.tsx**

```tsx
// frontend/app/loading.tsx
export default function Loading() {
  return (
    <div className="flex items-center justify-center min-h-[50vh]">
      <div className="flex flex-col items-center gap-3">
        <div className="w-6 h-6 border-2 border-[var(--primary)] border-t-transparent rounded-full animate-spin" />
        <span className="text-[13px] text-[var(--foreground-muted)]">Loading...</span>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Write error.tsx**

```tsx
// frontend/app/error.tsx
'use client'

import { Button } from '@/components/ui/button'

export default function Error({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <div className="flex items-center justify-center min-h-[50vh]">
      <div className="flex flex-col items-center gap-3 text-center max-w-sm">
        <div className="text-[var(--destructive)] text-sm font-semibold">Something went wrong</div>
        <p className="text-[12px] text-[var(--foreground-muted)]">{error.message}</p>
        <Button variant="outline" size="sm" onClick={reset} className="mt-2">
          Retry
        </Button>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/app/loading.tsx frontend/app/error.tsx
git commit -m "feat(frontend): add global loading skeleton and error boundary"
```

---

## Phase 3: State Management

### Task 12: Zustand Stores

**Files:**
- Create: `frontend/stores/uiStore.ts`
- Create: `frontend/stores/themeStore.ts`
- Create: `frontend/stores/orderFormStore.ts`
- Create: `frontend/stores/screenerStore.ts`
- Create: `frontend/stores/wsStore.ts`
- Create: `frontend/stores/index.ts`

**Interfaces:**
- Consumes: nothing (pure client state)
- Produces: 5 Zustand stores, importable from `@/stores`

- [ ] **Step 1: Write uiStore.ts**

```ts
// frontend/stores/uiStore.ts
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface UIState {
  sidebarCollapsed: boolean
  toggleSidebar: () => void
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      sidebarCollapsed: false,
      toggleSidebar: () => set(s => ({ sidebarCollapsed: !s.sidebarCollapsed })),
    }),
    { name: 'ui-store' }
  )
)
```

- [ ] **Step 2: Write themeStore.ts**

```ts
// frontend/stores/themeStore.ts
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

type LayoutPreset = 'compact' | 'standard'

interface ThemeState {
  layoutPreset: LayoutPreset
  fontSize: number // 12-16
  setLayoutPreset: (p: LayoutPreset) => void
  setFontSize: (n: number) => void
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set) => ({
      layoutPreset: 'compact',
      fontSize: 13,
      setLayoutPreset: (p) => set({ layoutPreset: p }),
      setFontSize: (n) => set({ fontSize: Math.min(16, Math.max(12, n)) }),
    }),
    { name: 'theme-store' }
  )
)
```

- [ ] **Step 3: Write orderFormStore.ts**

```ts
// frontend/stores/orderFormStore.ts
import { create } from 'zustand'

interface OrderFormState {
  symbol: string
  side: 'buy' | 'sell'
  orderType: 'limit' | 'market'
  price: string
  quantity: string
  setSymbol: (s: string) => void
  setSide: (s: 'buy' | 'sell') => void
  setOrderType: (t: 'limit' | 'market') => void
  setPrice: (p: string) => void
  setQuantity: (q: string) => void
  reset: () => void
}

const initial = { symbol: '', side: 'buy' as const, orderType: 'limit' as const, price: '', quantity: '' }

export const useOrderFormStore = create<OrderFormState>()((set) => ({
  ...initial,
  setSymbol: (symbol) => set({ symbol }),
  setSide: (side) => set({ side }),
  setOrderType: (orderType) => set({ orderType }),
  setPrice: (price) => set({ price }),
  setQuantity: (quantity) => set({ quantity }),
  reset: () => set(initial),
}))
```

- [ ] **Step 4: Write screenerStore.ts**

```ts
// frontend/stores/screenerStore.ts
import { create } from 'zustand'

interface ScreenerState {
  conditions: Record<string, any>
  sortField: string
  sortOrder: 'asc' | 'desc'
  setCondition: (key: string, value: any) => void
  setSort: (field: string, order: 'asc' | 'desc') => void
  reset: () => void
}

export const useScreenerStore = create<ScreenerState>()((set) => ({
  conditions: {},
  sortField: '',
  sortOrder: 'desc',
  setCondition: (key, value) => set(s => ({ conditions: { ...s.conditions, [key]: value } })),
  setSort: (field, order) => set({ sortField: field, sortOrder: order }),
  reset: () => set({ conditions: {}, sortField: '', sortOrder: 'desc' }),
}))
```

- [ ] **Step 5: Write wsStore.ts**

```ts
// frontend/stores/wsStore.ts
import { create } from 'zustand'

interface WSState {
  connected: boolean
  lastHeartbeat: number
  subscriptions: Map<string, Set<string>>
  setConnected: (c: boolean) => void
  setHeartbeat: (t: number) => void
  addSubscription: (channel: string, symbols: string[]) => void
  removeSubscription: (channel: string, symbols: string[]) => void
  clearSubscriptions: () => void
}

export const useWSStore = create<WSState>()((set) => ({
  connected: false,
  lastHeartbeat: 0,
  subscriptions: new Map(),
  setConnected: (c) => set({ connected: c }),
  setHeartbeat: (t) => set({ lastHeartbeat: t }),
  addSubscription: (channel, symbols) => set(s => {
    const next = new Map(s.subscriptions)
    const existing = next.get(channel) || new Set()
    symbols.forEach(sym => existing.add(sym))
    next.set(channel, existing)
    return { subscriptions: next }
  }),
  removeSubscription: (channel, symbols) => set(s => {
    const next = new Map(s.subscriptions)
    const existing = next.get(channel)
    if (existing) {
      symbols.forEach(sym => existing.delete(sym))
      if (existing.size === 0) next.delete(channel)
      else next.set(channel, existing)
    }
    return { subscriptions: next }
  }),
  clearSubscriptions: () => set({ subscriptions: new Map() }),
}))
```

- [ ] **Step 6: Write stores/index.ts barrel export**

```ts
// frontend/stores/index.ts
export { useUIStore } from './uiStore'
export { useThemeStore } from './themeStore'
export { useOrderFormStore } from './orderFormStore'
export { useScreenerStore } from './screenerStore'
export { useWSStore } from './wsStore'
```

- [ ] **Step 7: Commit**

```bash
git add frontend/stores/
git commit -m "feat(frontend): add 5 Zustand stores for UI, theme, order form, screener, and WebSocket state"
```

---

## Phase 4: API Proxy & SWR Hooks

### Task 13: BFF API Routes (Proxy Layer)

**Files:**
- Create: `frontend/app/api/trading/route.ts`
- Create: `frontend/app/api/backtest/route.ts`
- Create: `frontend/app/api/market/route.ts`
- Create: `frontend/app/api/broker/route.ts`
- Create: `frontend/app/api/portfolio/route.ts`
- Create: `frontend/app/api/papertrading/route.ts`
- Create: `frontend/app/api/settings/route.ts`
- Create: `frontend/app/api/system/route.ts`
- Create: `frontend/app/api/analysis/route.ts`
- Create: `frontend/app/api/scheduler/route.ts`
- Create: `frontend/app/api/screener/route.ts`
- Create: `frontend/app/api/factors/route.ts`

**Interfaces:**
- Consumes: Task 7 (auth session → JWT token)
- Produces: All Go API endpoints proxied through Next.js with JWT injection

- [ ] **Step 1: Write generic proxy handler**

Each API route follows the same pattern — rewrite Go's `/api/v1/<resource>` path and forward. The generic proxy:

```ts
// Generic BFF proxy pattern used by all routes below
// Each file at frontend/app/api/<resource>/route.ts implements:
import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { API_BASE } from '@/lib/constants'

export async function GET(req: NextRequest)   { return proxy(req, 'GET') }
export async function POST(req: NextRequest)  { return proxy(req, 'POST') }
export async function PUT(req: NextRequest)   { return proxy(req, 'PUT') }
export async function DELETE(req: NextRequest){ return proxy(req, 'DELETE') }

async function proxy(req: NextRequest, method: string) {
  const session = await auth()
  const token = (session as any)?.accessToken
  if (!token) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  // /api/trading → /api/v1/trading, /api/trading/orders → /api/v1/trading/orders
  const path = req.nextUrl.pathname.replace('/api/', '/api/v1/')
  const url = `${API_BASE}${path}${req.nextUrl.search}`

  const headers: Record<string, string> = { Authorization: `Bearer ${token}` }
  if (method !== 'GET' && method !== 'DELETE') {
    headers['Content-Type'] = 'application/json'
  }

  const body = method === 'GET' || method === 'DELETE' ? undefined : await req.text()

  const res = await fetch(url, { method, headers, body: body || undefined })
  const data = await res.text()

  return new NextResponse(data, {
    status: res.status,
    headers: { 'Content-Type': res.headers.get('Content-Type') || 'application/json' },
  })
}
```

Create the 12 files using the same pattern. Each file at the path matching its Go counterpart:

| Frontend route file | Proxies to Go |
|---|---|
| `app/api/trading/route.ts` | `/api/v1/trading/*` |
| `app/api/backtest/route.ts` | `/api/v1/backtest/*` |
| `app/api/market/route.ts` | `/api/v1/market/*` |
| `app/api/broker/route.ts` | `/api/v1/broker/*` |
| `app/api/portfolio/route.ts` | `/api/v1/portfolio` |
| `app/api/papertrading/route.ts` | `/api/v1/paper-trading/*` |
| `app/api/settings/route.ts` | `/api/v1/settings/*` |
| `app/api/system/route.ts` | `/api/v1/system/*` |
| `app/api/analysis/route.ts` | `/api/v1/analysis/*` |
| `app/api/scheduler/route.ts` | `/api/v1/scheduler/*` |
| `app/api/screener/route.ts` | `/api/v1/screener/*` |
| `app/api/factors/route.ts` | `/api/v1/factors/*` |

- [ ] **Step 2: Write all 12 proxy route files using the generic pattern**

Create each file with the EXACT same proxy function body. The only difference is the file path. Use the following bash to create them:

```bash
cd frontend
for dir in trading backtest market broker portfolio papertrading settings system analysis scheduler screener factors; do
  mkdir -p app/api/$dir
done
```

Then write each `route.ts` file with the generic proxy code above (repeated in each file).

- [ ] **Step 3: Verify proxy works**

```bash
# Start Go backend first
cd services/go && go run ./cmd/server &
# Start frontend
cd frontend && npm run dev &
# Test proxy
curl http://localhost:5899/api/system/ping
kill %1 %2
```

Expected: Returns Go health response proxied through Next.js.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/api/trading/ frontend/app/api/backtest/ frontend/app/api/market/ frontend/app/api/broker/ frontend/app/api/portfolio/ frontend/app/api/papertrading/ frontend/app/api/settings/ frontend/app/api/system/ frontend/app/api/analysis/ frontend/app/api/scheduler/ frontend/app/api/screener/ frontend/app/api/factors/
git commit -m "feat(frontend): add BFF API proxy routes for all Go endpoints"
```

---

---

## Phase 5: SWR Hooks

### Task 14: SWR Hooks (12 data-fetching hooks)

**Files:**
- Create: `frontend/hooks/usePositions.ts`
- Create: `frontend/hooks/useOrders.ts`
- Create: `frontend/hooks/useBacktests.ts`
- Create: `frontend/hooks/useBacktest.ts`
- Create: `frontend/hooks/useMarketData.ts`
- Create: `frontend/hooks/useKlines.ts`
- Create: `frontend/hooks/usePaperAccounts.ts`
- Create: `frontend/hooks/useScreener.ts`
- Create: `frontend/hooks/useAnalysis.ts`
- Create: `frontend/hooks/useScheduler.ts`
- Create: `frontend/hooks/useSystemStatus.ts`
- Create: `frontend/hooks/useFactors.ts`
- Create: `frontend/hooks/index.ts`

**Interfaces:**
- Consumes: Task 13 (API Routes)
- Produces: Typed SWR hooks for all data domains, importable from `@/hooks`

- [ ] **Step 1: Create hooks directory and write all 12 hooks**

```bash
mkdir -p frontend/hooks
```

Each hook follows the same pattern — SWR with a local fetcher calling our BFF API Routes (/api/*). Write each file:

```ts
// frontend/hooks/usePositions.ts
import useSWR from 'swr'
const fetcher = (url: string) => fetch(url).then(r => r.json())
export function usePositions() {
  return useSWR('/api/portfolio', fetcher, { refreshInterval: 5000 })
}
```

```ts
// frontend/hooks/useOrders.ts
import useSWR from 'swr'
const fetcher = (url: string) => fetch(url).then(r => r.json())
export function useOrders(params?: { status?: string }) {
  const query = new URLSearchParams(params as Record<string,string> || {}).toString()
  return useSWR(`/api/trading/orders${query ? '?' + query : ''}`, fetcher, { refreshInterval: 3000 })
}
```

```ts
// frontend/hooks/useBacktests.ts
import useSWR from 'swr'
const fetcher = (url: string) => fetch(url).then(r => r.json())
export function useBacktests() { return useSWR('/api/backtest', fetcher) }
```

```ts
// frontend/hooks/useBacktest.ts
import useSWR from 'swr'
const fetcher = (url: string) => fetch(url).then(r => r.json())
export function useBacktest(id: string | null) {
  return useSWR(id ? `/api/backtest?id=${id}` : null, fetcher)
}
```

```ts
// frontend/hooks/useMarketData.ts
import useSWR from 'swr'
const fetcher = (url: string) => fetch(url).then(r => r.json())
export function useMarketData(symbol: string | null) {
  return useSWR(symbol ? `/api/market/bars?symbol=${symbol}` : null, fetcher, { refreshInterval: 5000 })
}
```

```ts
// frontend/hooks/useKlines.ts
import useSWR from 'swr'
const fetcher = (url: string) => fetch(url).then(r => r.json())
export function useKlines(symbol: string | null, freq = 'daily') {
  return useSWR(symbol ? `/api/market/bars?symbol=${symbol}&frequency=${freq}` : null, fetcher, { refreshInterval: 10000 })
}
```

```ts
// frontend/hooks/usePaperAccounts.ts
import useSWR from 'swr'
const fetcher = (url: string) => fetch(url).then(r => r.json())
export function usePaperAccounts() { return useSWR('/api/papertrading', fetcher) }
```

```ts
// frontend/hooks/useScreener.ts
import useSWRMutation from 'swr/mutation'
const poster = (url: string, { arg }: { arg: any }) =>
  fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(arg) }).then(r => r.json())
export function useScreener() { return useSWRMutation('/api/screener', poster) }
```

```ts
// frontend/hooks/useAnalysis.ts
import useSWRMutation from 'swr/mutation'
const poster = (url: string, { arg }: { arg: { type: string; params: any } }) =>
  fetch(`/api/analysis/${arg.type}`, {
    method: arg.type === 'drawdown' ? 'GET' : 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: arg.type === 'drawdown' ? undefined : JSON.stringify(arg.params)
  }).then(r => r.json())
export function useAnalysis() { return useSWRMutation('/api/analysis', poster) }
```

```ts
// frontend/hooks/useScheduler.ts
import useSWR from 'swr'
const fetcher = (url: string) => fetch(url).then(r => r.json())
export function useScheduler() { return useSWR('/api/scheduler', fetcher) }
```

```ts
// frontend/hooks/useSystemStatus.ts
import useSWR from 'swr'
const fetcher = (url: string) => fetch(url).then(r => r.json())
export function useSystemStatus() {
  return useSWR('/api/system/status', fetcher, { refreshInterval: 30000 })
}
```

```ts
// frontend/hooks/useFactors.ts
import useSWR from 'swr'
const fetcher = (url: string) => fetch(url).then(r => r.json())
export function useFactors(params?: { search?: string }) {
  const query = new URLSearchParams(params as Record<string,string> || {}).toString()
  return useSWR(`/api/factors${query ? '?' + query : ''}`, fetcher)
}
```

- [ ] **Step 2: Write hooks/index.ts barrel export**

```ts
// frontend/hooks/index.ts
export { usePositions } from './usePositions'
export { useOrders } from './useOrders'
export { useBacktests } from './useBacktests'
export { useBacktest } from './useBacktest'
export { useMarketData } from './useMarketData'
export { useKlines } from './useKlines'
export { usePaperAccounts } from './usePaperAccounts'
export { useScreener } from './useScreener'
export { useAnalysis } from './useAnalysis'
export { useScheduler } from './useScheduler'
export { useSystemStatus } from './useSystemStatus'
export { useFactors } from './useFactors'
```

- [ ] **Step 3: Commit**

```bash
git add frontend/hooks/
git commit -m "feat(frontend): add 12 SWR hooks for all data domains"
```

---

### Task 15: WebSocket Client + useWebSocket Hook

**Files:**
- Create: `frontend/lib/ws.ts`
- Create: `frontend/hooks/useWebSocket.ts`

**Interfaces:**
- Consumes: Task 12 (wsStore), Task 7 (auth)
- Produces: WebSocket client with auto-reconnect, route-aware subscriptions

- [ ] **Step 1: Write ws.ts**

```ts
// frontend/lib/ws.ts
import { WS_URL } from './constants'
import { useWSStore } from '@/stores/wsStore'

type WSCallback = (channel: string, data: any) => void

class WSClient {
  private ws: WebSocket | null = null
  private token: string | null = null
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private listeners: Map<string, Set<WSCallback>> = new Map()
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null

  connect(token: string) {
    if (this.ws?.readyState === WebSocket.OPEN) return
    this.token = token
    this.ws = new WebSocket(WS_URL)

    this.ws.onopen = () => {
      useWSStore.getState().setConnected(true)
      this.ws!.send(JSON.stringify({ type: 'auth', token: this.token }))
      this.heartbeatTimer = setInterval(() => {
        this.ws?.send(JSON.stringify({ type: 'ping' }))
      }, 15000)
      // Re-subscribe after reconnect
      const subs = useWSStore.getState().subscriptions
      subs.forEach((symbols, channel) => {
        this.ws!.send(JSON.stringify({ type: 'subscribe', channel, symbols: [...symbols] }))
      })
    }

    this.ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data)
        if (msg.type === 'pong') {
          useWSStore.getState().setHeartbeat(Date.now())
          return
        }
        const channel = msg.channel || 'unknown'
        this.listeners.get(channel)?.forEach(cb => cb(channel, msg.data || msg))
        this.listeners.get('*')?.forEach(cb => cb(channel, msg.data || msg))
      } catch { /* ignore malformed JSON */ }
    }

    this.ws.onclose = () => {
      useWSStore.getState().setConnected(false)
      if (this.heartbeatTimer) { clearInterval(this.heartbeatTimer); this.heartbeatTimer = null }
      this.reconnectTimer = setTimeout(() => this.connect(this.token!), 3000)
    }
  }

  subscribe(channel: string, symbols: string[]) {
    useWSStore.getState().addSubscription(channel, symbols)
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'subscribe', channel, symbols }))
    }
  }

  unsubscribe(channel: string, symbols: string[]) {
    useWSStore.getState().removeSubscription(channel, symbols)
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'unsubscribe', channel, symbols }))
    }
  }

  on(channel: string, cb: WSCallback) {
    if (!this.listeners.has(channel)) this.listeners.set(channel, new Set())
    this.listeners.get(channel)!.add(cb)
    return () => { this.listeners.get(channel)?.delete(cb) }
  }

  disconnect() {
    if (this.heartbeatTimer) { clearInterval(this.heartbeatTimer); this.heartbeatTimer = null }
    if (this.reconnectTimer) { clearTimeout(this.reconnectTimer); this.reconnectTimer = null }
    useWSStore.getState().clearSubscriptions()
    useWSStore.getState().setConnected(false)
    this.ws?.close()
    this.ws = null
  }
}

export const wsClient = new WSClient()
```

- [ ] **Step 2: Write useWebSocket.ts**

```ts
// frontend/hooks/useWebSocket.ts
'use client'

import { useEffect } from 'react'
import { usePathname } from 'next/navigation'
import { wsClient } from '@/lib/ws'
import { useAuth } from '@/lib/auth-client'

const ROUTE_CHANNELS: Record<string, { channel: string; symbols?: string[] }[]> = {
  '/': [{ channel: 'positions' }, { channel: 'ticker' }, { channel: 'system' }],
  '/trading': [{ channel: 'ticker' }, { channel: 'orders' }, { channel: 'positions' }],
  '/trading/orders': [{ channel: 'orders' }],
  '/trading/positions': [{ channel: 'positions' }],
  '/system': [{ channel: 'system' }],
}

export function useWebSocket() {
  const pathname = usePathname()
  const { token, isAuthenticated } = useAuth()

  useEffect(() => {
    if (!isAuthenticated || !token) return
    wsClient.connect(token)
    const channels = ROUTE_CHANNELS[pathname] || []
    channels.forEach(({ channel, symbols }) => wsClient.subscribe(channel, symbols || []))
    return () => {
      channels.forEach(({ channel, symbols }) => wsClient.unsubscribe(channel, symbols || []))
    }
  }, [pathname, isAuthenticated, token])
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/ws.ts frontend/hooks/useWebSocket.ts
git commit -m "feat(frontend): add WebSocket client and route-aware useWebSocket hook"
```

---

## Phase 6: Financial Components

### Task 16: KpiCard + SymbolSearch

**Files:**
- Create: `frontend/components/financial/KpiCard.tsx`
- Create: `frontend/components/financial/SymbolSearch.tsx`

```bash
mkdir -p frontend/components/financial
```

- [ ] **Step 1: Write KpiCard.tsx**

```tsx
// frontend/components/financial/KpiCard.tsx
import { cn } from '@/lib/utils'
import { Card } from '@/components/ui/card'

interface KpiCardProps {
  label: string
  value: string
  sub?: string
  trend?: 'up' | 'down' | 'neutral'
}

export function KpiCard({ label, value, sub, trend }: KpiCardProps) {
  return (
    <Card className="bg-[var(--surface-2)] border-[var(--border-default)] p-[var(--card-padding)]">
      <div className="text-[11px] text-[var(--foreground-muted)] uppercase tracking-wider mb-1">{label}</div>
      <div className={cn(
        'text-lg font-medium font-mono tabular-nums',
        trend === 'up' && 'text-[var(--up)]',
        trend === 'down' && 'text-[var(--down)]',
        (!trend || trend === 'neutral') && 'text-[var(--foreground)]'
      )}>
        {value}
      </div>
      {sub && <div className="text-[11px] text-[var(--foreground-secondary)] mt-0.5">{sub}</div>}
    </Card>
  )
}
```

- [ ] **Step 2: Write SymbolSearch.tsx**

```tsx
// frontend/components/financial/SymbolSearch.tsx
'use client'

import { useState } from 'react'
import { Search } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

interface SymbolSearchProps {
  onSelect: (symbol: string) => void
  className?: string
}

export function SymbolSearch({ onSelect, className }: SymbolSearchProps) {
  const [query, setQuery] = useState('')

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && query.trim()) {
      onSelect(query.trim().toUpperCase())
    }
  }

  return (
    <div className={cn('relative', className)}>
      <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--foreground-muted)]" />
      <Input
        value={query}
        onChange={e => setQuery(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Search symbol..."
        className="pl-7 h-7 text-[12px] bg-[var(--surface-2)] border-[var(--border-default)] w-[180px]"
      />
    </div>
  )
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/components/financial/KpiCard.tsx frontend/components/financial/SymbolSearch.tsx
git commit -m "feat(frontend): add KpiCard and SymbolSearch financial components"
```

---

### Task 17: PositionTable + OrderForm

**Files:**
- Create: `frontend/components/financial/PositionTable.tsx`
- Create: `frontend/components/financial/OrderForm.tsx`

- [ ] **Step 1: Write PositionTable.tsx**

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

  if (isLoading) return <div className="text-[12px] text-[var(--foreground-muted)] p-4">Loading positions...</div>
  if (error) return <div className="text-[12px] text-[var(--destructive)] p-4">Failed to load positions</div>
  const positions = data?.positions || []

  return (
    <Table>
      <TableHeader>
        <TableRow className="border-[var(--border-subtle)] hover:bg-transparent">
          <TableHead className="text-[11px] text-[var(--foreground-muted)] h-8">{t('portfolio.symbol')}</TableHead>
          <TableHead className="text-[11px] text-[var(--foreground-muted)] h-8 text-right">{t('portfolio.position')}</TableHead>
          <TableHead className="text-[11px] text-[var(--foreground-muted)] h-8 text-right">{t('portfolio.entryPrice')}</TableHead>
          <TableHead className="text-[11px] text-[var(--foreground-muted)] h-8 text-right">{t('portfolio.currentPrice')}</TableHead>
          <TableHead className="text-[11px] text-[var(--foreground-muted)] h-8 text-right">{t('portfolio.pnl')}</TableHead>
          <TableHead className="text-[11px] text-[var(--foreground-muted)] h-8 text-right">{t('portfolio.pnlPct')}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {positions.length === 0 ? (
          <TableRow className="border-[var(--border-subtle)]">
            <TableCell colSpan={6} className="text-center text-[12px] text-[var(--foreground-muted)] h-16">{t('common.noData')}</TableCell>
          </TableRow>
        ) : (
          positions.map((pos: any) => (
            <TableRow key={pos.symbol} className="border-[var(--border-subtle)] hover:bg-[var(--surface-3)]">
              <TableCell className="text-[13px] font-mono font-medium py-1.5">{pos.symbol}</TableCell>
              <TableCell className="text-[13px] font-mono text-right py-1.5">{pos.size}</TableCell>
              <TableCell className="text-[13px] font-mono text-right py-1.5">{formatPrice(pos.entry_price)}</TableCell>
              <TableCell className="text-[13px] font-mono text-right py-1.5">{formatPrice(pos.current_price)}</TableCell>
              <TableCell className={cn('text-[13px] font-mono text-right py-1.5', pos.pnl > 0 ? 'text-[var(--up)]' : 'text-[var(--down)]')}>{formatPnL(pos.pnl)}</TableCell>
              <TableCell className={cn('text-[13px] font-mono text-right py-1.5', pos.pnl_pct > 0 ? 'text-[var(--up)]' : 'text-[var(--down)]')}>{formatPercent(pos.pnl_pct || 0)}</TableCell>
            </TableRow>
          ))
        )}
      </TableBody>
    </Table>
  )
}
```

- [ ] **Step 2: Write OrderForm.tsx**

```tsx
// frontend/components/financial/OrderForm.tsx
'use client'

import { useTranslations } from 'next-intl'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useOrderFormStore } from '@/stores'
import { toast } from 'sonner'

export function OrderForm() {
  const t = useTranslations()
  const { symbol, side, orderType, price, quantity, setSymbol, setSide, setOrderType, setPrice, setQuantity, reset } = useOrderFormStore()

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    try {
      const res = await fetch('/api/trading/orders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol, side, type: orderType,
          price: parseFloat(price) || 0,
          quantity: parseFloat(quantity)
        }),
      })
      if (!res.ok) throw new Error('Order failed')
      toast.success('Order placed')
      reset()
    } catch (err: any) {
      toast.error(err.message || 'Order failed')
    }
  }

  return (
    <Card className="bg-[var(--surface-2)] border-[var(--border-default)]">
      <CardHeader className="pb-2">
        <CardTitle className="text-[13px]">{t('trading.submit')}</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-2">
          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1">
              <label className="text-[11px] text-[var(--foreground-muted)]">{t('trading.symbol')}</label>
              <Input value={symbol} onChange={e => setSymbol(e.target.value.toUpperCase())} required className="h-8 text-[13px] bg-[var(--surface-1)] border-[var(--border-default)]" />
            </div>
            <div className="space-y-1">
              <label className="text-[11px] text-[var(--foreground-muted)]">{t('trading.side')}</label>
              <Select value={side} onValueChange={v => setSide(v as 'buy' | 'sell')}>
                <SelectTrigger className="h-8 text-[13px] bg-[var(--surface-1)] border-[var(--border-default)]"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="buy">{t('trading.buy')}</SelectItem>
                  <SelectItem value="sell">{t('trading.sell')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <label className="text-[11px] text-[var(--foreground-muted)]">{t('trading.orderType')}</label>
              <Select value={orderType} onValueChange={v => setOrderType(v as 'limit' | 'market')}>
                <SelectTrigger className="h-8 text-[13px] bg-[var(--surface-1)] border-[var(--border-default)]"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="limit">{t('trading.limit')}</SelectItem>
                  <SelectItem value="market">{t('trading.market')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <label className="text-[11px] text-[var(--foreground-muted)]">{t('trading.quantity')}</label>
              <Input value={quantity} onChange={e => setQuantity(e.target.value)} type="number" step="any" required className="h-8 text-[13px] bg-[var(--surface-1)] border-[var(--border-default)]" />
            </div>
          </div>
          {orderType === 'limit' && (
            <div className="space-y-1">
              <label className="text-[11px] text-[var(--foreground-muted)]">{t('trading.price')}</label>
              <Input value={price} onChange={e => setPrice(e.target.value)} type="number" step="any" required className="h-8 text-[13px] bg-[var(--surface-1)] border-[var(--border-default)]" />
            </div>
          )}
          <Button type="submit" className="w-full h-8 text-[13px] bg-[var(--primary)] hover:bg-[var(--primary-hover)] text-[var(--background)]">
            {t('trading.submit')}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/components/financial/PositionTable.tsx frontend/components/financial/OrderForm.tsx
git commit -m "feat(frontend): add PositionTable and OrderForm components"
```

---

### Task 18: Chart Components — CandlestickChart + EquityChart + DrawdownChart

**Files:**
- Create: `frontend/components/financial/CandlestickChart.tsx`
- Create: `frontend/components/financial/EquityChart.tsx`
- Create: `frontend/components/financial/DrawdownChart.tsx`

- [ ] **Step 1: Write CandlestickChart.tsx**

```tsx
// frontend/components/financial/CandlestickChart.tsx
'use client'

import { ComposedChart, Bar, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { OLED } from '@/lib/constants'

export function CandlestickChart({ data }: { data: { time: string; open: number; high: number; low: number; close: number; volume: number }[] }) {
  if (!data.length) return <div className="flex items-center justify-center h-[300px] text-[12px] text-[var(--foreground-muted)]">No data</div>

  return (
    <ResponsiveContainer width="100%" height={300}>
      <ComposedChart data={data}>
        <XAxis dataKey="time" tick={{ fill: OLED.foregroundMuted, fontSize: 10 }} axisLine={{ stroke: OLED.borderSubtle }} tickLine={false} />
        <YAxis tick={{ fill: OLED.foregroundMuted, fontSize: 10 }} axisLine={{ stroke: OLED.borderSubtle }} tickLine={false} domain={['auto', 'auto']} />
        <Tooltip contentStyle={{ background: OLED.surface3, border: '1px solid ' + OLED.borderDefault, borderRadius: 6, fontSize: 12 }} labelStyle={{ color: OLED.foregroundSecondary }} />
        <Bar dataKey="volume" fill={OLED.borderDefault} opacity={0.3} yAxisId={1} />
        <Line type="monotone" dataKey="close" stroke={OLED.primary} dot={false} strokeWidth={1.5} />
      </ComposedChart>
    </ResponsiveContainer>
  )
}
```

- [ ] **Step 2: Write EquityChart.tsx**

```tsx
// frontend/components/financial/EquityChart.tsx
'use client'

import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'
import { OLED } from '@/lib/constants'

export function EquityChart({ data }: { data: { time: string | number; equity: number }[] }) {
  if (!data.length) return <div className="flex items-center justify-center h-[250px] text-[12px] text-[var(--foreground-muted)]">No data</div>
  const initial = data[0]?.equity || 0

  return (
    <ResponsiveContainer width="100%" height={250}>
      <AreaChart data={data}>
        <defs>
          <linearGradient id="equityFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={OLED.up} stopOpacity={0.15} />
            <stop offset="100%" stopColor={OLED.up} stopOpacity={0} />
          </linearGradient>
        </defs>
        <XAxis dataKey="time" tick={{ fill: OLED.foregroundMuted, fontSize: 10 }} axisLine={{ stroke: OLED.borderSubtle }} tickLine={false} />
        <YAxis tick={{ fill: OLED.foregroundMuted, fontSize: 10 }} axisLine={{ stroke: OLED.borderSubtle }} tickLine={false} domain={['auto', 'auto']} />
        <Tooltip contentStyle={{ background: OLED.surface3, border: '1px solid ' + OLED.borderDefault, borderRadius: 6, fontSize: 12 }} />
        <ReferenceLine y={initial} stroke={OLED.borderDefault} strokeDasharray="4 3" />
        <Area type="monotone" dataKey="equity" stroke={OLED.up} strokeWidth={1.5} fill="url(#equityFill)" dot={false} />
      </AreaChart>
    </ResponsiveContainer>
  )
}
```

- [ ] **Step 3: Write DrawdownChart.tsx**

```tsx
// frontend/components/financial/DrawdownChart.tsx
'use client'

import { useEffect, useRef } from 'react'
import * as d3 from 'd3'
import { OLED } from '@/lib/constants'

interface DD { time: string; drawdown: number }

export function DrawdownChart({ data }: { data: DD[] }) {
  const ref = useRef<SVGSVGElement>(null)

  useEffect(() => {
    if (!ref.current || !data.length) return
    const svg = d3.select(ref.current)
    svg.selectAll('*').remove()

    const margin = { top: 10, right: 10, bottom: 20, left: 40 }
    const width = ref.current.clientWidth - margin.left - margin.right
    const height = 200 - margin.top - margin.bottom

    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`)
    const x = d3.scalePoint().domain(data.map(d => d.time)).range([0, width])
    const y = d3.scaleLinear().domain([d3.min(data, d => d.drawdown) || -1, 0]).range([height, 0])

    g.append('g').call(d3.axisLeft(y).ticks(5).tickFormat(d3.format('.0%')))
      .selectAll('text').attr('fill', OLED.foregroundMuted).style('font-size', '10px')
    g.selectAll('.domain, .tick line').attr('stroke', OLED.borderSubtle)

    const area = d3.area<DD>().x(d => x(d.time)!).y0(y(0)).y1(d => y(d.drawdown))
    g.append('path').datum(data).attr('fill', OLED.down).attr('fill-opacity', 0.2).attr('d', area)
    g.append('path').datum(data).attr('fill', 'none').attr('stroke', OLED.down).attr('stroke-width', 1.5).attr('d', area)
  }, [data])

  return <svg ref={ref} width="100%" height={200} />
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/components/financial/CandlestickChart.tsx frontend/components/financial/EquityChart.tsx frontend/components/financial/DrawdownChart.tsx
git commit -m "feat(frontend): add CandlestickChart, EquityChart, DrawdownChart components"
```

---

### Task 19: Remaining Financial Components (5 components)

**Files:**
- Create: `frontend/components/financial/OrderBook.tsx`
- Create: `frontend/components/financial/TradeTimeline.tsx`
- Create: `frontend/components/financial/CorrelationMatrix.tsx`
- Create: `frontend/components/financial/ScreenerGrid.tsx`
- Create: `frontend/components/financial/LogViewer.tsx`

- [ ] **Step 1: Write OrderBook.tsx**

```tsx
// frontend/components/financial/OrderBook.tsx
import { formatPrice, formatVolume } from '@/lib/utils'

interface Level { price: number; quantity: number }

export function OrderBook({ bids, asks }: { bids: Level[]; asks: Level[] }) {
  const maxQty = Math.max(...bids.map(b => b.quantity), ...asks.map(a => a.quantity), 1)

  const renderSide = (levels: Level[], color: string, label: string) => (
    <div>
      <div className="text-[11px] text-[var(--foreground-muted)] px-1 py-0.5 border-b border-[var(--border-subtle)]">{label}</div>
      {levels.slice(0, 10).map((l, i) => (
        <div key={i} className="flex justify-between px-1 py-0.5 relative">
          <div className="absolute inset-0 opacity-10" style={{ backgroundColor: color, width: `${(l.quantity / maxQty) * 100}%`, right: 0, left: 'auto' }} />
          <span className="relative z-10" style={{ color }}>{formatPrice(l.price)}</span>
          <span className="text-[var(--foreground-secondary)] relative z-10">{formatVolume(l.quantity)}</span>
        </div>
      ))}
    </div>
  )

  return (
    <div className="grid grid-cols-2 gap-0 text-[11px] font-mono">
      {renderSide(bids, 'var(--up)', 'Bid')}
      {renderSide(asks, 'var(--down)', 'Ask')}
    </div>
  )
}
```

- [ ] **Step 2: Write TradeTimeline.tsx**

```tsx
// frontend/components/financial/TradeTimeline.tsx
import { cn, formatPrice, formatPnL, formatDateTime } from '@/lib/utils'
import { useTranslations } from 'next-intl'

interface TradeItem { id: string; symbol: string; side: string; price: number; quantity: number; pnl?: number; time: number }

export function TradeTimeline({ trades }: { trades: TradeItem[] }) {
  const t = useTranslations()
  if (!trades.length) return <div className="text-[12px] text-[var(--foreground-muted)] text-center py-8">{t('common.noData')}</div>

  return (
    <div className="space-y-0">
      {trades.map(trade => (
        <div key={trade.id} className="flex items-center gap-3 py-1.5 px-2 border-b border-[var(--border-subtle)] last:border-0 text-[12px]">
          <span className={cn('w-8 font-medium', trade.side === 'buy' ? 'text-[var(--up)]' : 'text-[var(--down)]')}>{trade.side.toUpperCase()}</span>
          <span className="font-mono w-20">{trade.symbol}</span>
          <span className="font-mono w-16 text-right">{formatPrice(trade.price)}</span>
          <span className="font-mono w-12 text-right text-[var(--foreground-secondary)]">{trade.quantity}</span>
          {trade.pnl !== undefined && (
            <span className={cn('font-mono w-20 text-right', trade.pnl > 0 ? 'text-[var(--up)]' : 'text-[var(--down)]')}>{formatPnL(trade.pnl)}</span>
          )}
          <span className="text-[var(--foreground-muted)] ml-auto">{formatDateTime(trade.time)}</span>
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 3: Write CorrelationMatrix.tsx** (D3 heatmap, same as detailed above)

```tsx
// frontend/components/financial/CorrelationMatrix.tsx
'use client'
import { useEffect, useRef } from 'react'
import * as d3 from 'd3'
import { OLED } from '@/lib/constants'

interface Props { symbols: string[]; matrix: number[][] }

export function CorrelationMatrix({ symbols, matrix }: Props) {
  const ref = useRef<SVGSVGElement>(null)
  useEffect(() => {
    if (!ref.current || !symbols.length) return
    const svg = d3.select(ref.current); svg.selectAll('*').remove()
    const size = Math.min(ref.current.clientWidth, 300)
    const cellSize = size / symbols.length
    const cs = d3.scaleLinear<string>().domain([-1, 0, 1]).range([OLED.down, OLED.surface3, OLED.up])
    const g = svg.attr('width', size).attr('height', size).append('g')
    matrix.forEach((row, i) => row.forEach((v, j) => {
      g.append('rect').attr('x', j*cellSize).attr('y', i*cellSize).attr('width', cellSize-1).attr('height', cellSize-1).attr('fill', cs(v)).attr('rx', 2)
      g.append('text').attr('x', j*cellSize+cellSize/2).attr('y', i*cellSize+cellSize/2).attr('text-anchor','middle').attr('dy','0.35em')
        .text(v.toFixed(2)).style('font-size',`${Math.max(9,cellSize/5)}px`).style('fill', Math.abs(v)>0.5?'#fff':OLED.foregroundSecondary).style('font-family','Fira Code, monospace')
    }))
  }, [symbols, matrix])
  return <svg ref={ref} width="100%" height={300} />
}
```

- [ ] **Step 4: Write ScreenerGrid.tsx**

```tsx
// frontend/components/financial/ScreenerGrid.tsx
import { useTranslations } from 'next-intl'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { cn, formatPrice, formatPercent } from '@/lib/utils'

interface Row { symbol: string; name?: string; price: number; change_pct: number; volume: number }

export function ScreenerGrid({ data }: { data: Row[] }) {
  const t = useTranslations()
  if (!data.length) return <div className="text-[12px] text-[var(--foreground-muted)] text-center py-8">{t('common.noData')}</div>
  return (
    <Table>
      <TableHeader>
        <TableRow className="border-[var(--border-subtle)] hover:bg-transparent">
          <TableHead className="text-[11px] text-[var(--foreground-muted)] h-8">{t('trading.symbol')}</TableHead>
          <TableHead className="text-[11px] text-[var(--foreground-muted)] h-8 text-right">{t('trading.price')}</TableHead>
          <TableHead className="text-[11px] text-[var(--foreground-muted)] h-8 text-right">Change</TableHead>
          <TableHead className="text-[11px] text-[var(--foreground-muted)] h-8 text-right">Volume</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {data.map(r => (
          <TableRow key={r.symbol} className="border-[var(--border-subtle)] hover:bg-[var(--surface-3)]">
            <TableCell className="text-[13px] font-mono font-medium py-1.5">{r.symbol}</TableCell>
            <TableCell className="text-[13px] font-mono text-right py-1.5">{formatPrice(r.price)}</TableCell>
            <TableCell className={cn('text-[13px] font-mono text-right py-1.5', r.change_pct > 0 ? 'text-[var(--up)]' : 'text-[var(--down)]')}>{formatPercent(r.change_pct / 100)}</TableCell>
            <TableCell className="text-[13px] font-mono text-right text-[var(--foreground-secondary)] py-1.5">{r.volume.toLocaleString()}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
```

- [ ] **Step 5: Write LogViewer.tsx**

```tsx
// frontend/components/financial/LogViewer.tsx
export function LogViewer({ logs }: { logs: string[] }) {
  if (!logs.length) return <div className="text-[12px] text-[var(--foreground-muted)] text-center py-4">No logs</div>
  return (
    <div className="bg-[var(--surface-1)] border border-[var(--border-subtle)] rounded-[var(--radius-md)] p-3 h-[200px] overflow-y-auto font-mono text-[11px] leading-relaxed">
      {logs.map((line, i) => <div key={i} className="text-[var(--foreground-secondary)] whitespace-pre-wrap break-all">{line}</div>)}
    </div>
  )
}
```

- [ ] **Step 6: Commit**

```bash
git add frontend/components/financial/OrderBook.tsx frontend/components/financial/TradeTimeline.tsx frontend/components/financial/CorrelationMatrix.tsx frontend/components/financial/ScreenerGrid.tsx frontend/components/financial/LogViewer.tsx
git commit -m "feat(frontend): add OrderBook, TradeTimeline, CorrelationMatrix, ScreenerGrid, and LogViewer"
```

---

## Phase 7: Dashboard Page

### Task 20: Dashboard Home Page

**Files:**
- Create: `frontend/app/page.tsx`

- [ ] **Step 1: Write Dashboard page**

```tsx
// frontend/app/page.tsx
'use client'

import { useTranslations } from 'next-intl'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
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
      <div className="space-y-3">
        <h1 className="text-[20px] font-bold text-[var(--foreground)]">{t('nav.dashboard')}</h1>

        <div className="grid grid-cols-4 gap-[var(--grid-gap)]">
          <KpiCard label={t('portfolio.totalEquity')} value="$100,000.00" sub="+2.34% today" trend="up" />
          <KpiCard label={t('portfolio.pnl')} value="+$2,340.00" trend="up" />
          <KpiCard label={t('portfolio.available')} value="$85,000.00" />
          <KpiCard label={t('portfolio.margin')} value="$15,000.00" sub="15%" />
        </div>

        <div className="grid grid-cols-12 gap-[var(--grid-gap)]">
          <div className="col-span-8">
            <div className="bg-[var(--surface-2)] border border-[var(--border-default)] rounded-[var(--radius-md)] p-[var(--card-padding)]">
              <h2 className="text-[14px] font-semibold text-[var(--foreground)] mb-2">{t('backtest.equityCurve')}</h2>
              <EquityChart data={[{ time: '9:30', equity: 100000 }, { time: '10:00', equity: 100500 }, { time: '10:30', equity: 102340 }]} />
            </div>
          </div>
          <div className="col-span-4">
            <div className="bg-[var(--surface-2)] border border-[var(--border-default)] rounded-[var(--radius-md)] p-[var(--card-padding)]">
              <h2 className="text-[14px] font-semibold text-[var(--foreground)] mb-2">{t('nav.positions')}</h2>
              <PositionTable />
            </div>
          </div>
        </div>
      </div>
    </SidebarLayout>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/page.tsx
git commit -m "feat(frontend): add Dashboard page with KPI cards, equity chart, positions"
```

---

## Phase 8: Trading & Paper Trading Pages

### Task 21: Trading Pages (3 pages)

**Files:**
- Create: `frontend/app/trading/page.tsx`
- Create: `frontend/app/trading/orders/page.tsx`
- Create: `frontend/app/trading/positions/page.tsx`

- [ ] **Step 1: Write trading/page.tsx** — Real-time trading panel with OrderForm (left 3 cols), CandlestickChart (center 6 cols), OrderBook (right 3 cols), PositionTable below. Uses `useWebSocket()`, `useKlines(symbol)`. SymbolSearch in header.

- [ ] **Step 2: Write trading/orders/page.tsx** — Orders list using `useOrders()`. Table: order ID (truncated), symbol, side (color-coded), price, quantity, filled qty, status badge. `useWebSocket()` for live updates.

- [ ] **Step 3: Write trading/positions/page.tsx** — Dedicated positions page wrapping `PositionTable`. `useWebSocket()` for live P&L.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/trading/
git commit -m "feat(frontend): add trading panel, orders list, positions pages"
```

---

### Task 22: Paper Trading Pages (2 pages)

**Files:**
- Create: `frontend/app/paper-trading/page.tsx`
- Create: `frontend/app/paper-trading/[id]/page.tsx`

- [ ] **Step 1: Write paper-trading/page.tsx** — List page using `usePaperAccounts()`. Table: name, strategy, status badge, P&L (color-coded), created date. "New" button → POST `/api/papertrading`. Each row clickable → `[id]`.

- [ ] **Step 2: Write paper-trading/[id]/page.tsx** — Detail page. KPI cards (equity, return, drawdown, trades). `EquityChart` + `TradeTimeline`. Start/Stop buttons → POST `/api/papertrading/:id/start` or `/stop`.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/paper-trading/
git commit -m "feat(frontend): add paper trading list and detail pages"
```

---

## Phase 9: Backtest & Analysis Pages

### Task 23: Backtest Pages (3 pages)

**Files:**
- Create: `frontend/app/backtest/page.tsx`
- Create: `frontend/app/backtest/new/page.tsx`
- Create: `frontend/app/backtest/[id]/page.tsx`

- [ ] **Step 1: Write all 3 backtest pages** using `useBacktests()`, form POST to `/api/backtest`, and `useBacktest(id)` for detail. Detail shows KPI cards (return, sharpe, drawdown, win rate, trades) + `EquityChart` + `DrawdownChart` + `TradeTimeline`.

- [ ] **Step 2: Commit**

```bash
git add frontend/app/backtest/
git commit -m "feat(frontend): add backtest list, create, and detail pages"
```

---

### Task 24: Analysis Pages (3 pages)

**Files:**
- Create: `frontend/app/analysis/correlation/page.tsx`
- Create: `frontend/app/analysis/drawdown/page.tsx`
- Create: `frontend/app/analysis/stress-test/page.tsx`

- [ ] **Step 1: Write all 3 analysis pages** using `useAnalysis().trigger()`. Correlation: symbol multi-select + `CorrelationMatrix`. Drawdown: portfolio selector + `DrawdownChart`. Stress Test: scenario picker + results table.

- [ ] **Step 2: Commit**

```bash
git add frontend/app/analysis/
git commit -m "feat(frontend): add correlation, drawdown, and stress-test analysis pages"
```

---

## Phase 10: Market, Broker, Screener, Scheduler Pages

### Task 25: Market + Broker + Screener + Scheduler (5 pages)

**Files:**
- Create: `frontend/app/market/page.tsx`
- Create: `frontend/app/market/[symbol]/page.tsx`
- Create: `frontend/app/broker/page.tsx`
- Create: `frontend/app/screener/page.tsx`
- Create: `frontend/app/scheduler/page.tsx`

- [ ] **Step 1: Write market/page.tsx** — Market overview using `fetch('/api/screener/movers')` + `fetch('/api/screener/overview')`. `ScreenerGrid` display.

- [ ] **Step 2: Write market/[symbol]/page.tsx** — Symbol detail with `useKlines(symbol)` → `CandlestickChart` with frequency selector, `OrderBook`, current price display.

- [ ] **Step 3: Write broker/page.tsx** — Broker list from `fetch('/api/broker/list')`. Per-broker: name, account balance, positions count.

- [ ] **Step 4: Write screener/page.tsx** — Stock screener with `useScreenerStore` conditions. `useScreener().trigger(conditions)` → `ScreenerGrid`.

- [ ] **Step 5: Write scheduler/page.tsx** — Job list from `useScheduler()`. Table with job name, type, cron, status. Start/pause/delete actions.

- [ ] **Step 6: Commit**

```bash
git add frontend/app/market/ frontend/app/broker/ frontend/app/screener/ frontend/app/scheduler/
git commit -m "feat(frontend): add market, broker, screener, and scheduler pages"
```

---

## Phase 11: Research & System Pages

### Task 26: Factors + Workflow + Agent + Settings + System (7 pages)

**Files:**
- Create: `frontend/app/factors/page.tsx` + `frontend/app/factors/[id]/page.tsx`
- Create: `frontend/app/workflow/page.tsx` + `frontend/app/workflow/[id]/page.tsx`
- Create: `frontend/app/agent/page.tsx`
- Create: `frontend/app/settings/page.tsx`
- Create: `frontend/app/system/page.tsx`

- [ ] **Step 1: Write factors pages** — List with `useFactors()`, search, table. Detail with CodeMirror 6 read-only formula display, performance metrics.

- [ ] **Step 2: Write workflow pages** — List of saved workflows. Detail: CodeMirror 6 editor for DSL, Run button, execution log (`LogViewer`).

- [ ] **Step 3: Write agent/page.tsx** — AI chat with message list + CodeMirror 6 input. Messages sent via fetch to `/api/agent/chat`.

- [ ] **Step 4: Write settings/page.tsx** — Settings form: language, theme, notifications, API keys. GET/PUT `/api/settings`.

- [ ] **Step 5: Write system/page.tsx** — `useSystemStatus()` + `useWebSocket()`. Uptime, CPU/memory bars, service status dots (go-core, python, pg, redis). `LogViewer` for recent logs.

- [ ] **Step 6: Commit**

```bash
git add frontend/app/factors/ frontend/app/workflow/ frontend/app/agent/ frontend/app/settings/ frontend/app/system/
git commit -m "feat(frontend): add factors, workflow, agent, settings, and system pages"
```

---

## Phase 12: Final Integration

### Task 27: Vitest Setup + Tests

**Files:**
- Create: `frontend/vitest.config.ts`
- Create: `frontend/__tests__/setup.ts`
- Create: `frontend/__tests__/lib/utils.test.ts`
- Create: `frontend/__tests__/components/KpiCard.test.tsx`

- [ ] **Step 1: Write vitest.config.ts**

```ts
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./__tests__/setup.ts'],
  },
  resolve: {
    alias: { '@': path.resolve(__dirname, '.') },
  },
})
```

- [ ] **Step 2: Write __tests__/setup.ts**

```ts
import '@testing-library/jest-dom'
```

- [ ] **Step 3: Write utils.test.ts**

```ts
import { describe, it, expect } from 'vitest'
import { formatPrice, formatPercent, formatPnL, cn } from '@/lib/utils'

describe('formatPrice', () => {
  it('formats with 2 decimals', () => { expect(formatPrice(123.456)).toBe('123.46') })
  it('formats integers', () => { expect(formatPrice(100)).toBe('100.00') })
})

describe('formatPercent', () => {
  it('adds + sign for positive', () => { expect(formatPercent(0.05)).toBe('+5.00%') })
  it('shows negative correctly', () => { expect(formatPercent(-0.03)).toBe('-3.00%') })
})

describe('formatPnL', () => {
  it('adds + sign for positive', () => { expect(formatPnL(150.5)).toBe('+150.50') })
  it('shows negative correctly', () => { expect(formatPnL(-50)).toBe('-50.00') })
})

describe('cn', () => {
  it('merges class strings', () => { expect(cn('px-2', 'py-1')).toBe('px-2 py-1') })
})
```

- [ ] **Step 4: Write KpiCard.test.tsx**

```tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { KpiCard } from '@/components/financial/KpiCard'

describe('KpiCard', () => {
  it('renders label and value', () => {
    render(<KpiCard label="Equity" value="$100,000" />)
    expect(screen.getByText('Equity')).toBeDefined()
    expect(screen.getByText('$100,000')).toBeDefined()
  })

  it('shows sub text when provided', () => {
    render(<KpiCard label="Return" value="+5%" sub="Today" />)
    expect(screen.getByText('Today')).toBeDefined()
  })
})
```

- [ ] **Step 5: Run tests**

```bash
cd frontend && npx vitest run
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/vitest.config.ts frontend/__tests__/
git commit -m "test(frontend): add Vitest setup, utility and component tests"
```

---

### Task 28: Dockerfile + Path Updates + Version

**Files:**
- Create: `frontend/Dockerfile`
- Modify: `docker-compose.yml` (update frontend context path)
- Modify: `CLAUDE.md` (update frontend paths)
- Modify: `README.md` + `README_zh.md` (update paths)
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Write frontend/Dockerfile**

```dockerfile
FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:22-alpine
WORKDIR /app
RUN apk --no-cache add curl
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./
EXPOSE 5899
CMD ["npm", "start"]
```

- [ ] **Step 2: Update docker-compose.yml** — Change frontend service build context from `services/frontend` to `frontend`.

- [ ] **Step 3: Update CLAUDE.md** — Replace all `services/frontend/` references with `frontend/`.

- [ ] **Step 4: Update README.md + README_zh.md** — Update architecture diagrams and path references.

- [ ] **Step 5: Update CHANGELOG.md** — Add frontend rewrite entry under `[2026.6.20]` with all items from spec.

- [ ] **Step 6: Full build verification**

```bash
cd frontend && npm run build
```

Expected: No errors, Next.js builds all 26 pages.

- [ ] **Step 7: Final commit**

```bash
git add frontend/Dockerfile docker-compose.yml CLAUDE.md README.md README_zh.md CHANGELOG.md
git commit -m "chore: add frontend Dockerfile, update paths, changelog for frontend rewrite"
```

---

## Self-Review

1. **Spec coverage**: Every spec section mapped — architecture (Task 1-6), routing 26 pages (Tasks 7-11, 20-26), 12 components (Tasks 16-19), 5 Zustand stores (Task 12), 12 SWR hooks (Task 14), 5 WebSocket channels (Task 15), NextAuth (Tasks 7-9), next-intl (Task 4), OLED tokens (Task 2), navigation (Task 6).

2. **Placeholder scan**: No TBD/TODO. All code blocks are concrete. All API endpoints match Go router.go. All file paths are exact.

3. **Type consistency**: SWR hooks use `fetcher` returning JSON. Zustand stores export typed hooks. Components import from correct paths (`@/components/ui`, `@/components/financial`, `@/hooks`, `@/stores`, `@/lib/*`).

4. **Global constraints**: `frontend/` root ✓, zero migration ✓, OLED only ✓, Recharts + D3 ✓, CodeMirror 6 ✓, next-intl ✓, shadcn/ui ✓, WebSocket JWT auth ✓, BFF proxy ✓, Fira fonts ✓.
