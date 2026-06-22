# AStockPursue 前端现状分析

> 基于源码分析生成，2026-06-04

---

## 1. 整体架构

```
frontend/src/
├── components/          # 60+ 组件
│   ├── layout/          # Layout, ConnectionBanner, PostLoginSetup
│   ├── chat/            # Agent 聊天界面（13 组件）
│   ├── trading/         # 实盘交易组件（6 组件）
│   ├── paper-trading/   # 模拟盘组件（6 组件）
│   ├── charts/          # ECharts 图表（5 组件）
│   ├── factor-mining/   # 因子挖掘（11 组件）
│   ├── indicator-lab/   # 指标/策略实验室（13 组件）
│   ├── attribution/     # 归因分析图表（3 组件）
│   ├── auth/            # AuthGuard
│   ├── common/          # ErrorBoundary, Skeleton
│   └── ...
├── pages/               # 22 个页面，共 10,557 行
├── stores/              # 12 个 Zustand store
├── hooks/               # 3 个自定义 hook
├── lib/                 # 工具库（api, i18n, chart-theme, echarts 等）
└── workflow/            # 工作流画布（React Flow）
```

**技术栈**：React 19 + TypeScript + Tailwind CSS 3.4 + Zustand 5 + ECharts 6 + Monaco Editor + React Router 7 + react-markdown

---

## 2. 设计系统（本轮已升级）

### 2.1 排版
| 项目 | 之前 | 现在 |
|------|------|------|
| 正文字体 | Inter | **DM Sans** |
| 等宽字体 | JetBrains Mono | JetBrains Mono |
| h1 | text-lg | **text-2xl font-bold tracking-[-0.02em]** |
| h2 | text-base | **text-lg font-semibold tracking-[-0.01em]** |
| 新增 | — | `.display` / `.caption` / `.overline` |

### 2.2 色彩
| 令牌 | 值 | 用途 |
|------|-----|------|
| `--primary` | `hsl(24, 94%, 54%)` | 品牌琥珀色 |
| `--background` | `240 5% 99%` (亮) / `240 6% 4%` (暗) | 底色 |
| `--surface-1` | `240 5% 96%` / `240 6% 6%` | 侧边栏 |
| `--card` | `0 0% 100%` / `240 6% 8%` | 卡片 |
| `--accent-cyan/emerald/rose/violet/amber` | 5 个强调色 | 数据可视化 |

### 2.3 组件类
- **按钮**：`.btn` / `.btn-primary` / `.btn-secondary` / `.btn-ghost` / `.btn-outline` / `.btn-danger` / `.btn-sm` / `.btn-md`
- **卡片**：`.card` / `.card-hover` / `.card-metric` / `.section-card` / `.card-header` / `.card-body`
- **输入框**：`.input`（rounded-lg + focus ring）
- **表格**：`.data-table`
- **Tab**：`.tab-bar` / `.tab-item`
- **空状态**：`.empty-state` / `.empty-state-icon` / `.empty-state-text`
- **动画**：`.page-enter-stagger` / `.skeleton-shimmer` / `.animate-fade-in-up`

---

## 3. 页面总览

### 3.1 导航结构

侧边栏只有 **4 个主导航项**：

| 导航 | 路由 | 可见性 |
|------|------|--------|
| Projects | `/projects` | ✅ |
| Agent | `/agent` | ✅ |
| Data Sources | `/data-sources` | ✅ |
| Settings | `/settings` | ✅ |
| Admin/Users | `/admin/users` | 仅 admin 角色 |

**隐藏页面**（有路由但导航栏无入口）：

| 路由 | 页面 | 行数 |
|------|------|------|
| `/dashboard` | Dashboard | 390 |
| `/trading` | Trading | 330 |
| `/factor-mining` | FactorMining | 707 |
| `/screener` | Screener | 264 |
| `/paper-trading` | PaperTrading | 664 |
| `/strategy-lab` | StrategyLab | 1266 |
| `/indicator-lab` | IndicatorLab | 935 |
| `/alpha-zoo` | AlphaZoo | 1225 |
| `/attribution` | Attribution | 167 |
| `/sentiment` | Sentiment | 403 |
| `/correlation` | Correlation | 157 |
| `/compare` | Compare | 322 |
| `/scheduler` | Scheduler | 137 |
| `/marketplace` | Marketplace | 169 |
| `/options` | Options | 135 |
| `/docs` | Docs | 322 |
| `/workflow/:projectId/:workflowId` | Workflow | 266 |

### 3.2 各页面状态评估

#### ✅ 功能完整、生产可用
| 页面 | 评价 |
|------|------|
| **Login** (78行) | 简洁完整的登录/注册表单，`.input` + `.btn` 标准化 |
| **Projects** (283行) | 项目卡片网格，创建/归档/打开，模板库 |
| **Agent** (749行) | 核心 AI 对话界面，SSE 流式，消息气泡，工具调用时间线 |
| **Settings** (880行) | LLM/数据源/技能/MCP/账户设置，完整 |
| **PaperTrading** (664行) | 策略管理+K线+持仓+成交+风控，完整 |
| **Trading** (330行) | 自选股+分时图+K线+下单+券商+通知，完整 |
| **StrategyLab** (1266行) | 代码编辑器+回测+AI 生成+模板+历史+版本控制 |
| **IndicatorLab** (935行) | 指标编辑器+回测+验证+AI 生成+Alpha Zoo 浏览 |
| **AlphaZoo** (1225行) | Alpha 因子浏览/详情/基准测试 |
| **RunDetail** (403行) | 回测结果详情+交易记录+代码+指标 |
| **FactorMining** (707行) | GP 进化+LLM 提取+候选管理+进化图表 |

#### ⚠️ 功能存在但体验待完善
| 页面 | 问题 |
|------|------|
| **Dashboard** (390行) | 路由隐藏，无侧边栏入口；数据轮询正常但依赖所有后端模块 |
| **Screener** (264行) | 功能完整但无侧边栏入口 |
| **Sentiment** (403行) | SSE 实时数据，无侧边栏入口 |
| **Attribution** (167行) | 刚改为真实数据，无侧边栏入口 |
| **Correlation** (157行) | 功能简单，无侧边栏入口 |
| **Scheduler** (137行) | 定时任务管理，无侧边栏入口 |
| **Docs** (322行) | API 文档页面，无侧边栏入口 |
| **Workflow** (266行) | React Flow 画布，从 Projects 进入 |

#### ❌ 功能缺失
| 页面 | 问题 |
|------|------|
| **Marketplace** (169行) | 只能浏览/安装/评分，**缺少发布策略入口** |
| **Compare** (322行) | 策略对比，无侧边栏入口 |
| **Options** (135行) | 期权计算器，功能简单，无侧边栏入口 |
| **Home** (39行) | 已废弃，未使用 |

---

## 4. 已知问题清单

### 4.1 导航可发现性 — 严重
17 个页面中只有 4 个在侧边栏可见。其余页面需要用户手动输入 URL 或从其他页面跳转。**大量功能对用户不可见**。

### 4.2 Marketplace 不完整 — 中等
- 后端 API 完整（publish/browse/install/rate/unpublish）
- 前端只有 browse + install + rate
- **缺少 publish 入口**

### 4.3 Dashboard 无入口 — 中等
- Dashboard 聚合了所有模块的数据总览
- 路由存在但无导航入口
- 应该是首页但实际首页是 Projects

### 4.4 `(api as any)` 反模式 — 低
Marketplace 页面使用 `(api as any).browseMarketplace()` 而非类型安全的 `api.browseMarketplace()`

### 4.5 部分页面未接入新设计系统
旧式 inline Tailwind（`rounded-lg border bg-card p-4`）仍散见于 Compare、Scheduler、Options 等页面，未统一使用 `.card` 等组件类

---

## 5. CSS 组件类使用情况

| 类名 | 使用文件数 | 状态 |
|------|-----------|------|
| `.btn` / `.btn-*` | 36+ | ✅ 广泛使用 |
| `.card` / `.card-hover` | 15+ | ✅ 主要页面已接入 |
| `.input` | 10+ | ✅ 标准化 |
| `.section-card` | 8+ | ✅ 页面级面板 |
| `.page-header` | 5+ | ⚠️ 部分页面未使用 |
| `.tab-bar` / `.tab-item` | 5+ | ✅ Tab 统一 |
| `.empty-state` | 10+ | ✅ 空状态统一 |
| `.data-table` | 2+ | ⚠️ 新增，推广中 |
| `.page-enter-stagger` | 2+ | ⚠️ 仅 Dashboard/Projects |
| `.skeleton-shimmer` | 2+ | ⚠️ 新增 |

---

## 6. 性能

| 指标 | 数值 |
|------|------|
| 初始 JS bundle | 370 KB (gzip 119 KB) |
| React vendor | 101 KB (gzip 34 KB) |
| ECharts vendor | 1,121 KB (gzip 372 KB) |
| 总页面数 | 22 (全部 lazy loaded) |
| TS 类型错误 | **0** |
| Vite build 时间 | ~3.6s |

---

## 7. 总结

**整体评价**：前端功能丰富、架构清晰、代码量大（10,557 行页面 + 60+ 组件），是一个成熟的生产级量化交易平台前端。设计系统本轮已完成升级（DM Sans、4 级表面层级、交错动画、新组件类）。

**最大问题**：导航可发现性 — 大量功能隐藏在 URL 背后。

**待补**：Marketplace 发布入口、Dashboard 导航入口、老页面接入新设计系统。
