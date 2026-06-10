# AStockPursue OLED Trading Terminal — 全面重设计规范

> 日期：2026-06-07 | 状态：已确认

## 1. 设计目标

将 AStockPursue 前端重设计为 **OLED 深色量化交易终端**，以 Data-Dense Dashboard 布局理念为核心，在保留品牌橙色的前提下，全面提升数据密度、可读性和专业感。

### 核心原则

- **数据优先**：每一屏最大化可见数据量，减少装饰性留白
- **暗色原生**：纯 OLED 暗色模式（无亮色切换），`#020617` 基底
- **品牌延续**：保留橙色 `#FB923C` 作为唯一强调色，用户无重新认知成本
- **数字即产品**：等宽数字、对齐排版、涨跌语义色是核心体验
- **触控可达**：最小 44px 交互区、安全区域适配、键盘可访问

---

## 2. 设计决策（已确认）

| 维度 | 决策 |
|------|------|
| 范围 | **全面重设计** — 所有页面、组件、token |
| 模式 | **纯暗色 OLED** — 仅深色，`--background: #020617` |
| 品牌色 | **保留橙色** — `--primary: #FB923C`，进化非革命 |
| 字体 | **Fira Sans**（正文）+ **Fira Code**（数据/代码/价格） |

---

## 3. 设计 Token 系统

### 3.1 颜色 — OLED 暗色体系

```
层级（从深到浅）：
  --background        #020617    页面底色（最深，纯 OLED 黑）
  --surface-1         #0A0F1D    大面积面板背景
  --surface-2         #0F172A    卡片/图表背景
  --surface-3         #1A1E2F    悬浮卡片（dialog/dropdown/tooltip）
  --border-subtle     #1E293B    弱分割线
  --border-default    #272F42    默认边框
  --border-strong     #334155    强边框（focus/active）

语义色：
  --primary           #FB923C    品牌橙（CTA、选中态、强调）
  --primary-hover     #FBA86C    悬停亮化
  --primary-muted     rgba(251,146,60,0.12)  橙色背景层

  --up / --profit     #22C55E    涨/盈利（中国用户：红涨绿跌场景单独处理）
  --down / --loss     #EF4444    跌/亏损
  --warning           #F59E0B    警告
  --info              #3B82F6    信息
  --destructive       #DC2626    危险操作

文字色：
  --foreground        #F8FAFC    正文（对比度 >7:1 对 #020617）
  --foreground-secondary #94A3B8 辅助文字
  --foreground-muted  #64748B    三级文字/占位符
```

### 3.2 字体

| 用途 | 字体 | 字重 | 大小 |
|------|------|------|------|
| 页面标题 | Fira Sans | 700 Bold | 20px |
| 板块标题 | Fira Sans | 600 Semibold | 14px |
| 正文 | Fira Sans | 400 Regular | 13px |
| 辅助文字/标签 | Fira Sans | 400 Regular | 11px |
| 价格/数字 | Fira Code | 500 Medium | 14-20px |
| 表格数据 | Fira Code | 400 Regular | 12-13px (tabular-nums) |
| 代码/Monaco | Fira Code | 400 Regular | 13px |

### 3.3 间距与网格

```
--grid-gap: 8px          （Data-Dense 级别，原系统 12-16px）
--card-padding: 12px     （原系统 16px）
--section-gap: 12px
--page-padding: 12px
--table-row-height: 32px
--header-height: 48px    （原系统 56px+）
--sidebar-width: 220px   （原系统约 260px）

网格体系：12 列 CSS Grid
  grid-template-columns: repeat(12, 1fr)
  KPI 卡片：span 3（一行 4 个）
  图表主区：span 7-8
  侧边面板：span 4-5
```

### 3.4 圆角与阴影

```
--radius-sm: 4px
--radius-md: 6px
--radius-lg: 8px
--radius-xl: 12px

阴影（暗色环境下不用传统 box-shadow，改用亮边框暗示层级）：
  surface-1: 无阴影（和背景融为一体）
  surface-2: border-subtle 边框
  surface-3: border-default 边框 + 微 glow
  modal overlay: rgba(0,0,0,0.6)
```

### 3.5 动画

```
--duration-fast: 120ms   （hover/active 瞬时反馈）
--duration-normal: 200ms （展开/收起/切换）
--duration-slow: 300ms   （页面入场/路由过渡）

count-up 数字动画：requestAnimationFrame，200ms 从旧值滚动到新值
表格行 hover：background-color 150ms 过渡
图表 loading → data：300ms 骨架屏淡出 + 图表淡入
尊重 prefers-reduced-motion：所有动画降级为 0ms 即时切换
```

---

## 4. 组件体系变更

### 4.1 布局组件

#### Layout（重写）
- 移除亮色切换按钮（纯暗色）
- 侧边栏收窄至 220px，使用 `surface-1` 背景
- 顶栏合并至 48px 高，品牌 Logo + 面包屑 + 快捷操作
- 移除现有 `mobile-bottom-nav`，改为常驻底部 Tab Bar（iOS/Android 风格各适配）

#### PageHeader（统一）
- 高度从 49px → 40px
- 字体从 18px → 14px Semibold
- 移除 `rounded-xl bg-card shadow-sm`，改为底部 `border-subtle` 边框分隔
- 面包屑组件新增

### 4.2 数据展示组件

#### KPI 卡片（新增 `KpiCard`）
```
结构：
  <KpiCard>
    <KpiCard.Label>Portfolio Value</KpiCard.Label>      // 11px overline
    <KpiCard.Value>¥1,234,567</KpiCard.Value>           // 20px Fira Code 700
    <KpiCard.Change>+2.34%</KpiCard.Change>             // 12px Fira Code + 涨跌色
    <KpiCard.Sparkline data={...} />                    // 可选迷你趋势线
  </KpiCard>

规格：padding 12px, gap 4px, min-width 0（弹性收缩）
      grid-column: span 3 / span 4 / span 6（响应式）
```

#### DataTable（重写 `data-table`）
- 行高从 44px → 32px（更紧凑）
- 字体 Fira Code 12px + tabular-nums
- sticky header + 虚拟滚动（>100 行时）
- 排序指示器（aria-sort）
- 行 hover 背景 `rgba(251,146,60,0.04)`（极淡橙色）
- 选中行左边框 2px 橙色指示

#### 数字格式化（新增 `formatNumber` 工具集）
```typescript
formatPrice(15.82)        → "¥15.82"      // Fira Code tabular-nums
formatPercent(0.0347)     → "+3.47%"      // 涨跌色自动
formatVolume(125600000)   → "125.60M"     // 大数缩写
formatCountUp(from, to)   → requestAnimationFrame 动画
```

### 4.3 图表组件

#### ECharts 主题（重写 `chart-theme.ts`）
- 默认暗色主题：`#020617` 背景，`#1E293B` 网格线
- K 线颜色沿用中国习惯（红涨绿跌，`zh` locale）或国际习惯（绿涨红跌，`en` locale）
- tooltip 背景 `rgba(15,23,42,0.96)`，边框 `#334155`
- 坐标轴标签 Fira Code 11px
- 数据缩放滑块暗色主题
- 移除 ECharts 默认动画或压缩至 200ms

#### CandlestickChart（重构）
- 减少内边距，图表填满容器
- 十字光标 tooltip（移动端长按触发）
- 时间范围快捷切换（1D / 1W / 1M / 3M / 1Y / All）

### 4.4 导航组件

#### Sidebar（重写）
```
结构（从上到下）：
  Logo（橙色图标 + 文字，32px）
  ── 分割线 ──
  导航项（图标 18px + 文字 12px Fira Sans，高 36px）
    - Dashboard
    - Trading
    - Strategy Lab
    - Factor Mining
    - Paper Trading
    - Screener
    - Agent
  ── 分割线 ──
  辅助导航
    - Data Sources
    - Settings
  ── spacer ──
  用户头像 + 快捷菜单
```

- 活跃项：橙色左边框 2px + `primary-muted` 背景
- 折叠态：仅图标 36px 宽，hover 展开 tooltip
- 键盘快捷键 `Cmd+K` 唤起命令面板（搜索导航）

#### BottomTabBar（新增，移动端）
- 最多 5 项：Dashboard / Trading / Strategy / Agent / More
- 图标 20px + 文字 10px
- 活跃项橙色
- 安全区域适配 `safe-area-inset-bottom`

### 4.5 交互组件

#### Button（统一）
```
层级：
  primary   — bg-primary text-white（橙色实心，主要 CTA）
  secondary — bg-surface-2 text-foreground border（常规操作）
  ghost     — transparent text-foreground-secondary（低优先级）
  danger    — bg-destructive/12 text-destructive（危险操作）

规格：h 32px（sm）/ 36px（md）/ 40px（lg）
      px 12（sm）/ 16（md）/ 20（lg）
      font 12px Fira Sans Medium
      radius 6px
      transition 120ms
      active: scale(0.97)
      focus-visible: ring 2px primary/40
```

#### Input / Select（统一）
- 背景 `surface-2`，边框 `border-default`
- focus 边框 `primary` + ring 2px `primary/20`
- 高度 36px，字体 Fira Code 13px
- placeholder `foreground-muted`
- 暗色 autofill 覆盖（避免浏览器白底）

#### Toast（Sonner）
- 暗色主题 `surface-3` 背景
- 成功/错误/警告左侧色条
- 3 秒自动消失
- `aria-live="polite"`

#### Dialog / Modal
- 背景 `surface-2`，scrim `rgba(0,0,0,0.6)`
- 入场动画：scale(0.96)→scale(1) + opacity 0→1，200ms
- 退出动画：120ms 反向
- Escape 关闭 + 点击 scrim 关闭
- focus trap

---

## 5. 页面重设计要点

### 5.1 Dashboard（`/`）
- 顶部：日期 + 市场状态指示灯（open/closed/午休）
- 四联 KPI 卡片行：Portfolio Value / Daily P&L / Open Positions / Win Rate
- 左侧 7 列：主 K 线图（含十字光标、时间切换）
- 右侧 5 列：Watchlist 紧凑列表 + 最近信号流
- 底部 12 列：持仓表（sticky header，可排序）

### 5.2 Trading（`/trading`）
- 左侧 3 列：Watchlist（可搜索、可排序、点击切换标的）
- 中间 6 列：K 线图 + 分时图切换
- 右侧 3 列：下单面板（Buy/Sell tab、价格/数量输入、确认按钮）
- 底部：持仓表 + 订单历史

### 5.3 Strategy Lab（`/strategy-lab`）
- 顶部工具栏：策略选择器 + Run/Stop 按钮 + 状态指示
- 左侧 3 列：策略代码编辑器（Monaco，Fira Code，暗色主题）
- 右侧 9 列：回测结果（权益曲线图 + 统计指标表 + 交易明细表）
- 底部状态栏：最后运行时间、耗时、错误计数

### 5.4 Factor Mining（`/factor-mining`）
- KPI 条：Generation / Best IC / Elite Count / Runtime
- 主区域：EvolutionChart（适应度曲线） + CandidatesTable（因子列表）
- 侧边面板：EliteTracker + ExpressionTreeViewer
- 进度卡片：MiningProgressCard（当前代/总代、最佳 IC、FDR 状态）

### 5.5 Agent（`/agent`）
- 左侧边栏 260px：会话列表（可搜索、重命名、删除）
- 主区域：对话流（Markdown 渲染、代码高亮、loading dots）
- 底部：输入框 + 发送按钮（Cmd+Enter 发送）
- SSE 连接状态指示灯

### 5.6 其余页面
- **Projects**：卡片网格或表格式，显示项目名/描述/最近运行/状态
- **Data Sources**：数据源健康表（名称/状态/延迟/最近检查）
- **Screener**：筛选条件面板 + 结果表（无限滚动）
- **Settings**：分组表单（Profile / Notifications / API Keys / Preferences）
- **Login**：居中卡片，品牌 Logo + 表单 + 暗色背景

---

## 6. 技术实施路径

### Phase 1 — Token 系统重建（基础层）
1. 重写 `index.css` — 全部 CSS 变量替换为 OLED 暗色值
2. 更新 `tailwind.config.ts` — 确认所有 token 引用正确
3. 引入 Fira Sans + Fira Code 字体（Google Fonts CDN + 本地 fallback）
4. 更新 `chart-theme.ts` — ECharts 暗色主题
5. 移除 `useDarkMode` hook，硬编码暗色（或保留 hook 但设为 always dark）

### Phase 2 — 布局 & 导航（结构层）
1. 重写 `Layout.tsx` — 新侧边栏 + 顶栏 + 内容区
2. 新增 `BottomTabBar` 组件（移动端）
3. 新增 `Breadcrumb` 组件
4. 新增 `CommandPalette` 组件（Cmd+K）
5. 重写 `PageHeader` 组件
6. 更新所有页面的布局结构适配新 Layout

### Phase 3 — 数据展示组件（内容层）
1. 新增 `KpiCard` 组件
2. 重写 `DataTable` 组件（含排序、虚拟滚动、sticky header）
3. 新增 `formatNumber` / `CountUp` 工具
4. 更新所有表格和数字展示为 Fira Code + tabular-nums
5. 重写 `Skeleton` / `EmptyState` 组件

### Phase 4 — 图表 & 编辑器（专业层）
1. 重构 `CandlestickChart`（暗色主题、十字光标、时间切换）
2. 重构 `EquityChart`（暗色主题、更紧凑）
3. 适配所有图表组件到新主题
4. Monaco Editor 暗色主题 + Fira Code 字体

### Phase 5 — 页面逐一重设计（页面层）
按照 5.1→5.6 顺序，每个页面独立重设计
1. Dashboard
2. Trading
3. Strategy Lab
4. Factor Mining
5. Agent
6. 其余页面

### Phase 6 — 交互打磨（体验层）
1. 全局键盘快捷键
2. CountUp 数字动画
3. 图表入场动画
4. 路由过渡动画
5. Toast 通知优化
6. 无障碍审计（WCAG AAA 目标）
7. 移动端全面适配

---

## 7. 兼容性 & 约束

- **浏览器**：Chrome 90+, Firefox 90+, Safari 15+, Edge 90+
- **移动端**：iOS Safari 15+, Chrome Android 90+
- **不兼容亮色模式**：所有硬编码的暗色背景假设，不提供亮色切换
- **中国涨跌色**：通过 `html[lang="zh"]` 自动切换红涨绿跌 / 绿涨红跌
- **现有数据/API 不变**：仅前端视觉层变化，不修改任何 API 调用或数据结构
- **i18n 保持**：所有 `t.keyName` 调用不变，仅组件结构和样式变化

---

## 8. 风险 & 缓解

| 风险 | 缓解 |
|------|------|
| 暗色下低对比度元素不可见 | 全部文字/边框/图表元素使用 WCAG AAA 对比度验证（≥7:1 正文） |
| Data-Dense 布局在小屏上过密 | 移动端降级为 2 列 KPI、单列布局、折叠侧边栏 |
| 移除亮色模式用户不满 | 在 Settings 中保留反馈入口；设计 token 系统保留 `:root` / `.dark` 结构以支持未来恢复 |
| Fira 字体中文 fallback 效果差 | 中文使用系统默认（PingFang SC / Microsoft YaHei），仅英文/数字使用 Fira |

---

## 9. 成功标准

- [ ] 所有页面纯暗色，无亮色残留
- [ ] KPI 卡片密度提升 ≥30%（一屏可见指标数对比旧版）
- [ ] 所有数字使用 Fira Code tabular-nums，列对齐无误
- [ ] 涨跌颜色自动适配中英文
- [ ] 所有交互元素有 focus-visible 指示
- [ ] prefers-reduced-motion 全站生效
- [ ] 移动端无横向滚动
- [ ] Lighthouse Accessibility ≥95
- [ ] TypeScript 编译零错误
- [ ] 现有功能无回归
