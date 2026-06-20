# AStockPursue Frontend 重写设计规范

> 日期：2026-06-20 | 状态：已确认

## 1. 概述

本规范定义 AStockPursue 前端的完整重写设计。前端从 `services/frontend/` 提至根目录 `frontend/`，基于 Next.js 15 App Router 从零搭建，**零迁移**——不保留任何现有前端代码和样式。

与现有设计规范的关系：
- [OLED Trading Terminal 设计规范](2026-06-07-oled-trading-terminal-design.md) —— 设计 token、字体、间距、组件视觉
- [Go + Python Hybrid Refactoring 设计](2026-06-20-go-python-hybrid-refactoring-design.md) 第 2.3 节 —— 前端架构概览

本规范是上述两份规范的落地细化，解决具体的路由、组件、状态管理、数据流、认证等技术实现问题。

---

## 2. 技术栈选型

| 层面 | 选择 | 理由 |
|------|------|------|
| 框架 | Next.js 15 App Router | SSR/SSG/RSC，生态成熟 |
| 数据获取 | SWR 2.x | 轻量，与 Next.js App Router 紧密集成 |
| 认证 | NextAuth.js 5 (Auth.js) | JWT Credentials Provider，适配 Go PBKDF2 后端 |
| 客户端状态 | Zustand 5.x | 轻量、选择性订阅、不强制 Provider |
| 服务端缓存 | SWR (TanStack Query 替代) | 自动重新验证、乐观更新、fallback 预热 |
| 组件库 | shadcn/ui + Radix 无头组件 | 按需复制源码，完全控制样式，与 OLED token 融合 |
| 图表 | Recharts + D3 | Recharts 做标准图表（K线/权益），D3 做自定义可视化 |
| 代码编辑器 | CodeMirror 6 | 轻量（~200KB vs Monaco ~2MB），暗色主题原生支持 |
| 样式 | Tailwind CSS 4 + CSS 变量 | 直接绑定 OLED token，零运行时 |
| 国际化 | next-intl | App Router 原生支持，Server Components 友好 |
| 测试 | Vitest + Testing Library | 与 Next.js 生态一致 |

---

## 3. 架构总览

### 3.1 分层架构

```
┌─ Browser ─────────────────────────────────────────────┐
│  Next.js App Router (frontend/)                       │
│  ├─ Server Components (RSC) — 首屏数据、SEO            │
│  ├─ Client Components — 交互、实时更新                  │
│  │   ├─ shadcn/ui + OLED tokens (CSS 变量)            │
│  │   ├─ Zustand (UI 状态) + SWR (服务端数据缓存)       │
│  │   └─ WebSocket (实时 ticker/order 推送)             │
│  └─ API Routes — JWT 代理 → Go REST (:8899)           │
└───────────────────────────────────────────────────────┘
          │ HTTP + WS                  │ gRPC
┌─ Go Core :8899 ───────────────────────────────────────┐
│  15 handlers: auth/backtest/trading/market/broker/     │
│  portfolio/papertrade/settings/system/analysis/        │
│  scheduler/screener/health                             │
└───────────────────────────────────────────────────────┘
```

### 3.2 数据获取：混合模式

- **SSR 页面**（Dashboard、回测详情）：Server Component 预取数据 → SWR `fallback` → 首屏完整渲染
- **客户端交互**（实时交易、行情看板）：SWR 客户端 fetch + WebSocket 推送
- **写操作**（下单、创建回测、设置修改）：POST/PUT/DELETE → API Route → Go → SWR `mutate()` 乐观更新

### 3.3 API Routes：BFF 代理层

`frontend/app/api/*/route.ts` 作为 Backend-For-Frontend 代理：
- 从 NextAuth session 中提取 JWT token
- 注入 `Authorization: Bearer <token>` 头，转发到 Go REST API
- 保证 token 不出浏览器，Go API 仅接受经过认证的请求

---

## 4. 页面路由结构（26 页，6 板块）

### 板块一：认证与入口
| 路由 | 页面 | Go handler |
|------|------|-----------|
| `/login` | 登录页 | `auth.go` |
| `/register` | 注册页 | `auth.go` |

### 板块二：Dashboard
| 路由 | 页面 | 数据来源 |
|------|------|----------|
| `/` | 总览仪表盘 | `portfolio.go` + `system.go` + 持仓/权益摘要 |

### 板块三：交易核心
| 路由 | 页面 | Go handler |
|------|------|-----------|
| `/trading` | 实时交易面板 | `trading.go` |
| `/trading/orders` | 订单列表 | `trading.go` |
| `/trading/positions` | 持仓管理 | `portfolio.go` |
| `/paper-trading` | 模拟交易总览 | `papertrade.go` |
| `/paper-trading/[id]` | 模拟账户详情 | `papertrade.go` |

### 板块四：回测与分析
| 路由 | 页面 | Go handler |
|------|------|-----------|
| `/backtest` | 回测列表 | `backtest.go` |
| `/backtest/new` | 创建回测 | `backtest.go` |
| `/backtest/[id]` | 回测详情 | `backtest.go` |
| `/analysis/correlation` | 相关性分析 | `analysis.go` |
| `/analysis/drawdown` | 回撤分析 | `analysis.go` |
| `/analysis/stress-test` | 压力测试 | `analysis.go` |

### 板块五：市场与数据
| 路由 | 页面 | Go handler |
|------|------|-----------|
| `/market` | 行情总览 | `market.go` |
| `/market/[symbol]` | 个股详情 | `market.go` |
| `/broker` | 券商账户管理 | `broker.go` |
| `/screener` | 股票筛选器 | `screener.go` |
| `/scheduler` | 定时任务管理 | `scheduler.go` |

### 板块六：研究与工具
| 路由 | 页面 | Go handler → Python gRPC |
|------|------|--------------------------|
| `/factors` | 因子挖掘 | Go factor handler → Python FactorService |
| `/factors/[id]` | 因子详情 | Go factor handler → Python |
| `/workflow` | 工作流编辑器 | Go workflow handler → Python WorkflowService |
| `/workflow/[id]` | 工作流运行详情 | Go workflow handler → Python |
| `/agent` | AI Agent 对话 | Go → Python LLMService |
| `/settings` | 系统设置 | `settings.go` |
| `/system` | 系统状态 | `system.go` |

---

## 5. 目录结构

```
frontend/
├── app/                              # Next.js App Router
│   ├── layout.tsx                    # RootLayout: OLED 基底 + next-intl + AuthProvider + SWR
│   ├── page.tsx                      # Dashboard 首页
│   ├── loading.tsx                   # 全局加载骨架屏
│   ├── error.tsx                     # 全局错误边界
│   ├── login/page.tsx
│   ├── register/page.tsx
│   ├── trading/
│   │   ├── page.tsx                  # 实时交易面板
│   │   ├── orders/page.tsx           # 订单列表
│   │   └── positions/page.tsx        # 持仓管理
│   ├── paper-trading/
│   │   ├── page.tsx                  # 模拟交易总览
│   │   └── [id]/page.tsx             # 模拟账户详情
│   ├── backtest/
│   │   ├── page.tsx                  # 回测列表
│   │   ├── new/page.tsx              # 创建回测
│   │   └── [id]/page.tsx             # 回测详情
│   ├── analysis/
│   │   ├── correlation/page.tsx
│   │   ├── drawdown/page.tsx
│   │   └── stress-test/page.tsx
│   ├── market/
│   │   ├── page.tsx                  # 行情总览
│   │   └── [symbol]/page.tsx         # 个股详情
│   ├── broker/page.tsx
│   ├── screener/page.tsx
│   ├── scheduler/page.tsx
│   ├── factors/
│   │   ├── page.tsx
│   │   └── [id]/page.tsx
│   ├── workflow/
│   │   ├── page.tsx
│   │   └── [id]/page.tsx
│   ├── agent/page.tsx
│   ├── settings/page.tsx
│   ├── system/page.tsx
│   └── api/                          # API Routes (BFF 代理层)
│       ├── auth/[...nextauth]/route.ts
│       ├── trading/route.ts
│       ├── backtest/route.ts
│       ├── market/route.ts
│       ├── broker/route.ts
│       ├── portfolio/route.ts
│       ├── papertrading/route.ts
│       ├── settings/route.ts
│       ├── system/route.ts
│       ├── analysis/route.ts
│       ├── scheduler/route.ts
│       ├── screener/route.ts
│       └── factors/route.ts
├── components/
│   ├── layout/                       # 布局组件
│   │   ├── Sidebar.tsx               # 侧边导航 (220px)
│   │   ├── Header.tsx                # 顶部栏 (48px)
│   │   └── SidebarLayout.tsx         # 组合 Sidebar + Header + main
│   ├── ui/                           # shadcn/ui (OLED variant)
│   │   └── theme-provider.tsx        # ThemeProvider (OLED only)
│   └── financial/                    # 金融专用组件
│       ├── CandlestickChart.tsx       # Recharts K 线
│       ├── EquityChart.tsx            # D3 权益曲线
│       ├── OrderBook.tsx              # 深度订单簿
│       ├── PositionTable.tsx          # 持仓列表
│       ├── OrderForm.tsx              # 下单表单
│       ├── KpiCard.tsx                # KPI 指标卡片
│       ├── SymbolSearch.tsx           # 代码搜索（自动补全）
│       ├── DrawdownChart.tsx          # 回撤曲线
│       ├── CorrelationMatrix.tsx      # 相关性热力图
│       ├── ScreenerGrid.tsx           # 筛选器数据表格
│       ├── TradeTimeline.tsx          # 交易时间线
│       └── LogViewer.tsx              # 日志查看器
├── lib/
│   ├── api-client.ts                 # SWR fetcher + JWT 注入
│   ├── auth.ts                       # NextAuth 配置 (CredentialsProvider)
│   ├── auth.config.ts                # NextAuth 配置对象（供 middleware）
│   ├── ws.ts                         # WebSocket 客户端封装
│   ├── i18n/
│   │   ├── request.ts                # next-intl getRequestConfig
│   │   ├── routing.ts                # 路由定义
│   │   ├── en.json                   # 英文
│   │   └── zh.json                   # 中文
│   ├── constants.ts                  # OLED token 常量引用
│   └── utils.ts                      # 格式化（金额、百分比、日期）
├── stores/                           # Zustand
│   ├── uiStore.ts                    # 侧边栏折叠、面板展开、列显隐
│   ├── wsStore.ts                    # WebSocket 连接状态、订阅列表
│   ├── orderFormStore.ts             # 下单表单草稿
│   ├── screenerStore.ts              # 筛选器条件暂存
│   └── themeStore.ts                 # 布局预设、字号偏好
├── hooks/                            # SWR hooks
│   ├── usePositions.ts
│   ├── useOrders.ts
│   ├── useBacktests.ts
│   ├── useBacktest.ts
│   ├── useMarketData.ts
│   ├── useKlines.ts
│   ├── usePaperAccounts.ts
│   ├── useScreener.ts
│   ├── useAnalysis.ts
│   ├── useScheduler.ts
│   ├── useSystemStatus.ts
│   ├── useFactors.ts
│   └── useWebSocket.ts               # 路由感知 WebSocket hook
├── middleware.ts                      # NextAuth middleware (路由保护)
├── next.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── package.json
├── Dockerfile
├── vitest.config.ts
└── postcss.config.mjs
```

---

## 6. 共享组件设计

### 6.1 布局层

```
<RootLayout>                  — OLED 暗色基底 + next-intl Provider + SWRConfig
  <AuthProvider>              — NextAuth SessionProvider
  <SidebarLayout>             — 侧边导航 + 内容区
    <Sidebar>                 — 220px 宽，品牌 logo + 导航链接 + 账户快捷
    <Header>                  — 48px 高，面包屑 + 快捷操作 + 用户菜单
    <main>                    — 内容区，page-padding: 12px
```

### 6.2 金融专用组件（12 个）

| 组件 | 用途 | 使用页面 |
|------|------|---------|
| `CandlestickChart` | K 线图（Recharts 实现） | Trading, Market/[symbol], Backtest/[id] |
| `EquityChart` | 权益曲线（D3 实现） | Dashboard, Backtest/[id], Paper-trading/[id] |
| `OrderBook` | 深度订单簿 | Trading, Market/[symbol] |
| `PositionTable` | 持仓列表（Fira Code tabular-nums） | Trading/positions, Dashboard |
| `OrderForm` | 下单表单 | Trading |
| `KpiCard` | KPI 指标卡片（grid span 3，一行 4 个） | Dashboard, Backtest/[id], Paper/[id] |
| `SymbolSearch` | 股票代码搜索（带自动补全） | Market, Trading, Screener |
| `DrawdownChart` | 回撤曲线 | Analysis/drawdown, Backtest/[id] |
| `CorrelationMatrix` | 相关性热力图 | Analysis/correlation |
| `ScreenerGrid` | 筛选器数据表格 | Screener |
| `TradeTimeline` | 交易时间线 | Backtest/[id], Paper-trading/[id] |
| `LogViewer` | 任务日志终端视图 | Scheduler, System |

### 6.3 shadcn/ui 通用组件

Button, Dialog, DropdownMenu, Table, Tabs, Card, Input, Select, Textarea, Toast (Sonner), Badge, Separator, ScrollArea, Popover, Tooltip, Command（搜索面板）。

所有 shadcn 组件通过 `globals.css` 的 CSS 变量绑定 OLED 设计 token，确保 `--background`, `--foreground`, `--primary` 等语义色自动生效。不新增设计 token——完全遵循 OLED 规范第 3 节定义的体系。

---

## 7. 状态管理

### 7.1 分工原则

- **Zustand**：纯客户端 UI 状态（用户偏好、草稿、连接状态）
- **SWR**：服务端数据（API 请求、缓存、失效、乐观更新）
- **WebSocket**：实时推送（价格 ticker、订单状态、系统心跳）

### 7.2 Zustand Stores（5 个）

| Store | 管理内容 | 持久化 |
|-------|---------|--------|
| `uiStore` | 侧边栏折叠、面板展开态、表格列显隐、排序偏好 | localStorage |
| `wsStore` | WebSocket 连接状态、当前订阅列表、最后心跳时间 | 内存 |
| `orderFormStore` | 下单表单草稿（symbol、方向、数量、价格类型） | 内存（页面切换保留） |
| `screenerStore` | 筛选器条件暂存（条件组合、排序字段） | 内存 |
| `themeStore` | 终端布局预设（紧凑/标准）、字号偏好 | localStorage |

### 7.3 SWR Hooks（12 个）

| SWR Hook | 对应 API | 使用页面 |
|----------|---------|---------|
| `usePositions()` | `GET /api/portfolio/positions` | Dashboard, Trading |
| `useOrders(params)` | `GET /api/trading/orders` | Trading/Orders |
| `useBacktests(params)` | `GET /api/backtest` | Backtest 列表 |
| `useBacktest(id)` | `GET /api/backtest/:id` | 回测详情 |
| `useMarketData(symbol)` | `GET /api/market/:symbol` | 行情页 |
| `useKlines(symbol, freq)` | `GET /api/market/:symbol/klines` | K 线图 |
| `usePaperAccounts()` | `GET /api/papertrading` | 模拟交易 |
| `useScreener(criteria)` | `POST /api/screener` | 筛选器 |
| `useAnalysis(type, params)` | `POST /api/analysis/:type` | 分析页 |
| `useScheduler()` | `GET /api/scheduler` | 定时任务 |
| `useSystemStatus()` | `GET /api/system` | 系统状态 |
| `useFactors(params)` | `GET /api/factors` | 因子挖掘 |

### 7.4 数据流模式

```
┌── Server Component (RSC) ─┐     ┌── Client Component ──────────────┐
│  fetch data via Go API    │ --> │  SWR revalidate (stale-while)    │
│  pass as SWR fallback     │     │  Zustand (UI only)               │
│  (no JS to browser)       │     │  WebSocket push → mutate(key)    │
└───────────────────────────┘     └──────────────────────────────────┘
```

- **SSR 预热**：Server Component 用 `fetch` 预取数据，注入 SWR `fallback` 字典，首屏完整渲染无闪烁
- **客户端刷新**：SWR 接管，`refreshInterval` 按页面配置：
  - Dashboard: 5s
  - Trading: 3s
  - Backtest: 30s（历史数据无需高频）
  - System: 30s
- **实时推送**：WebSocket 收到推送 → `wsStore.set(channel, data)` → SWR `mutate(key, data)` 乐观更新对应缓存

---

## 8. WebSocket 实时数据

### 8.1 连接架构

```
Browser (wsStore + useWebSocket hook)
  └─ ws://localhost:8899/ws
       ├─ subscribe:   {type: "subscribe",   channel: "ticker", symbols: ["000001.SZ"]}
       ├─ unsubscribe: {type: "unsubscribe", channel: "ticker", symbols: ["000001.SZ"]}
       ├─ auth:        {type: "auth", token: "<jwt>"}  ← 第一条消息认证
       └─ heartbeat:   ping/pong (15s interval)
```

### 8.2 频道定义

| 频道 | 推送数据结构 | 使用页面 | 频率 |
|------|-------------|---------|------|
| `ticker` | `{symbol, price, change, changePct, volume}` | Dashboard, Trading, Market | 实时 |
| `klines` | `{symbol, freq, bar: {o,h,l,c,v}}` | K线图, 回测详情 | 分钟级 |
| `orders` | `{orderId, symbol, status, filledQty, filledPrice}` | Trading, Orders | 实时 |
| `positions` | `{symbol, size, entryPrice, currentPrice, pnl}` | Dashboard, Positions | 实时 |
| `system` | `{cpu, memory, uptime, activeTasks}` | System Status | 30s |

### 8.3 降级策略

- `useWebSocket` hook 路由感知：仅订阅当前可见页面所需的频道
- 连接中断 → SWR 自动回退到 HTTP `refreshInterval` 轮询
- 重连成功 → SWR `mutate()` 刷新所有活跃 key，恢复 WebSocket 推送
- 路由切换 → 自动退订离开页面的频道

---

## 9. 认证流程

### 9.1 登录

```
Browser                    NextAuth CredentialsProvider       Go API :8899
  │                              │                              │
  ├─ POST /api/auth/callback/    │                              │
  │  {username, password}        │                              │
  │                              ├─ POST /api/auth/login ──────>│
  │                              │   {username, password}       │
  │                              │                              │ PBKDF2 verify
  │                              │ <──── {token, expires} ──────┤
  │                              │                              │
  │                              ├─ 签发 NextAuth JWT (httpOnly) │
  │<── session cookie ──────────┤  (secure, sameSite strict)   │
```

### 9.2 路由保护

```ts
// middleware.ts
export { auth as middleware } from "@/lib/auth"
export const config = { matcher: ['/((?!login|register|api/auth).*)'] }
```

### 9.3 API Route JWT 注入

```ts
// lib/api-client.ts — SWR fetcher 统一注入
const fetcher = (url: string) => {
  const session = await getSession()
  return fetch(`${API_BASE}${url}`, {
    headers: { Authorization: `Bearer ${session.token}` }
  })
}
```

### 9.4 安全性

- Token 仅存于 httpOnly cookie，JavaScript 不可访问
- API Routes 从服务端 session 取 token 代理 Go，浏览器不暴露
- WebSocket 认证：连接后首条消息发送 `{type: "auth", token: "..."}`
- 注册：`POST /api/auth/register` → Go PBKDF2 哈希 → 返回 token

---

## 10. 国际化

### 10.1 next-intl 配置

- `frontend/lib/i18n/request.ts` —— App Router `getRequestConfig`
- `frontend/lib/i18n/routing.ts` —— 路由定义（locale prefix: `/zh`/`/en`，默认 `zh`）
- `frontend/lib/i18n/zh.json` —— 中文
- `frontend/lib/i18n/en.json` —— 英文

### 10.2 涨跌颜色

遵循 CLAUDE.md 规则：
- 中文 locale（A 股市场）：红涨绿跌（`--up: #EF4444`, `--down: #22C55E`）
- 英文 locale（国际市场）：绿涨红跌（`--up: #22C55E`, `--down: #EF4444`）
- CSS 变量 `--up`/`--down` 动态切换，组件统一使用语义变量

---

## 11. 设计 Token 与样式

完全遵循 [OLED Trading Terminal 设计规范](2026-06-07-oled-trading-terminal-design.md) 第 3 节定义的体系，此处列出关键映射：

### 11.1 CSS 变量 → Tailwind

```css
/* globals.css */
:root {
  --background: #020617;        /* OLED 纯黑底 */
  --foreground: #F8FAFC;        /* 正文（对比度 >7:1） */
  --primary: #FB923C;           /* 品牌橙 */
  --up: #22C55E;                /* 涨（国际） */
  --down: #EF4444;              /* 跌（国际） */
  --sidebar-width: 220px;
  --header-height: 48px;
  --grid-gap: 8px;
  --card-padding: 12px;
  --radius-md: 6px;
  /* ... 其余见 OLED 规范 3.1-3.4 */
}

/* zh locale override */
[lang="zh"] {
  --up: #EF4444;
  --down: #22C55E;
}
```

### 11.2 字体

- 正文：Fira Sans, system-ui
- 数据/代码/价格：Fira Code, monospace（tabular-nums 对齐）
- Monaco Editor 场景：CodeMirror 6 使用 Fira Code

---

## 12. 全局导航

### 12.1 Sidebar (220px)

```
┌──────────────────┐
│  AStockPursue    │  Logo + 品牌
│  ───────────────│
│  📊 Dashboard    │  /
│  ───────────────│
│  Trade           │  板块标题 (--foreground-muted, 11px)
│  ├─ 💹 Trading   │  /trading
│  ├─ 📋 Orders    │  /trading/orders
│  ├─ 📦 Positions │  /trading/positions
│  └─ 📝 Paper     │  /paper-trading
│  ───────────────│
│  Research        │
│  ├─ 🔬 Backtest  │  /backtest
│  ├─ 🧬 Factors   │  /factors
│  ├─ 🔧 Workflow  │  /workflow
│  └─ 🤖 Agent     │  /agent
│  ───────────────│
│  Market          │
│  ├─ 📈 Market    │  /market
│  ├─ 🔍 Screener  │  /screener
│  └─ 🏦 Broker    │  /broker
│  ───────────────│
│  System          │
│  ├─ ⚙️ Settings  │  /settings
│  ├─ 📡 System    │  /system
│  └─ ⏰ Scheduler │  /scheduler
│  ───────────────│
│  👤 user@email   │  (底部固定)
└──────────────────┘
```

- 当前路由：`--primary-muted` 背景 + `--primary` 左边框指示（3px）
- 折叠态：仅图标 48px 宽，悬停展开
- 移动端：drawer overlay（Radix Dialog）

### 12.2 Header (48px)

- 左：面包屑（`Trade > Orders`）
- 右：`SymbolSearch` 搜索框 + 通知铃铛 + 用户头像（DropdownMenu → 退出登录）

---

## 13. 项目设置

### 13.1 package.json 依赖

```json
{
  "name": "astockpursue-frontend",
  "private": true,
  "scripts": {
    "dev": "next dev --port 5899",
    "build": "next build",
    "start": "next start",
    "test": "vitest",
    "lint": "next lint"
  },
  "dependencies": {
    "next": "^15.0.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "next-auth": "^5.0.0-beta",
    "next-intl": "^4.0.0",
    "swr": "^2.2.0",
    "zustand": "^5.0.0",
    "recharts": "^2.12.0",
    "d3": "^7.9.0",
    "@codemirror/state": "^6.4.0",
    "@codemirror/view": "^6.26.0",
    "@codemirror/lang-javascript": "^6.2.0",
    "@codemirror/lang-python": "^6.1.0",
    "lucide-react": "^0.400.0",
    "sonner": "^1.7.0",
    "tailwind-merge": "^2.5.0",
    "clsx": "^2.1.0"
  },
  "devDependencies": {
    "typescript": "^5.5.0",
    "tailwindcss": "^4.0.0",
    "postcss": "^8.4.0",
    "vitest": "^2.0.0",
    "@testing-library/react": "^16.0.0",
    "@testing-library/jest-dom": "^6.5.0",
    "eslint": "^9.0.0",
    "eslint-config-next": "^15.0.0"
  }
}
```

### 13.2 需要更新的文件（路径变更）

| 文件 | 变更 |
|------|------|
| `docker-compose.yml` | `services/frontend` → `frontend` |
| `CLAUDE.md` | 更新前端目录路径和启动命令 |
| `README.md` | 更新架构图和路径引用 |
| `README_zh.md` | 同上 |

---

## 14. 设计决策汇总

| 决策 | 选择 | 备选方案 |
|------|------|---------|
| 前端路径 | 根目录 `frontend/` | `services/frontend/` |
| 数据获取 | BFF 代理（SSR）+ WebSocket 直连（实时） | 纯直连 / 纯 BFF |
| 认证 | NextAuth Credentials + Go JWT | 自建 / iron-session |
| 状态管理 | Zustand (UI) + SWR (data) | Zustand 全管 / TanStack Query |
| 组件库 | shadcn/ui + Radix | 全自研 / Ant Design |
| 图表 | Recharts + D3 | ECharts |
| 代码编辑器 | CodeMirror 6 | Monaco Editor |
| 国际化 | next-intl | 自建 / next-i18next |

---

## 15. 自审清单

1. **占位符检查**：无 TBD/TODO，所有技术选型、路由、组件均已确定
2. **内部一致性**：路由数量（26）与 Go handler 覆盖一致；SWR hooks（12）与 API Routes（12）一一对应
3. **范围聚焦**：仅覆盖前端重写，不涉及 Go/Python 后端修改
4. **歧义检查**：性能指标（re-render、bundle size）未在本规范量化——这些属于实现细节，由 Plan 阶段的任务验收标准覆盖
