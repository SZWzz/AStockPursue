# AStockPursue 前端 Coinbase 机构风重设计

> 日期：2026-06-20 | 状态：已确认 | 参考：[Coinbase DESIGN.md](../../../design-md/coinbase/DESIGN.md)

## 1. 目标

将前端从 OLED 暗黑 + 橙色主题，重构为 Coinbase 机构级金融服务风格：纯白画布、单一蓝色 primary (`#0052FF`)、轻体量字体、无阴影层次系统。

## 2. 设计原则

- **安静自信**：display 字体用 400 weight，不用 700 bold 大喊大叫
- **色块层次**：靠 surface 颜色递进 (`#F7F7F7` → `#EEF0F3` → `#DEE1E6`)，不用 box-shadow
- **单色品牌**：`#0052FF` 是唯一的品牌电压，只用在一级 CTA 和关键强调处
- **数字可读**：所有价格/百分比/数量用 JetBrains Mono，`tabular-nums`
- **hairline 边框**：1px `#DEE1E6` 是分隔主力，subtle 但精准

---

## 3. 色彩系统

### 3.1 Primary & Brand

| Token | 新值 | 用途 |
|-------|------|------|
| `--primary` | `#0052FF` | 主 CTA、品牌强调、active 态 |
| `--primary-foreground` | `#FFFFFF` | primary 上的文字 |
| `--primary-hover` | `#003ECC` | 按钮 hover/press |
| `--primary-muted` | `rgba(0,82,255,0.10)` | 浅蓝底（badge、选中行） |

### 3.2 Canvas & Surface（白底层次）

| Token | 新值 | 用途 |
|-------|------|------|
| `--background` | `#FFFFFF` | 页面地板 |
| `--foreground` | `#0A0B0D` | 最强文字（标题） |
| `--card` | `#FFFFFF` | 卡片底色 |
| `--card-foreground` | `#0A0B0D` | 卡片内文字 |
| `--popover` | `#FFFFFF` | 弹出层底色 |
| `--popover-foreground` | `#0A0B0D` | 弹出层文字 |
| `--secondary` | `#EEF0F3` | 次要按钮 / 区块底 |
| `--secondary-foreground` | `#0A0B0D` | 次要按钮文字 |
| `--muted` | `#F7F7F7` | 灰底（sidebar、disabled） |
| `--muted-foreground` | `#7C828A` | 辅助文字/标签 |
| `--accent` | `#EEF0F3` | 轻强调底 |
| `--accent-foreground` | `#0A0B0D` | 轻强调文字 |
| `--destructive` | `#CF202F` | 危险操作/亏损 |
| `--destructive-foreground` | `#FFFFFF` | 危险按钮文字 |

### 3.3 OLED Surface Aliases（重映射到白底层次）

```css
/* 保留旧别名，值完全翻转为白底体系 */
--surface-1: #F7F7F7;   /* 原 #0A0F1D → 侧边栏底 */
--surface-2: #EEF0F3;   /* 原 #0F172A → 卡片内子区块 */
--surface-3: #DEE1E6;   /* 原 #1A1E2F → hover 态 */
```

### 3.4 Text

| Token | 新值 | 用途 |
|-------|------|------|
| `--foreground` | `#0A0B0D` | 页面标题、强文字 |
| `--foreground-secondary` | `#5B616E` | body 正文 |
| `--foreground-muted` | `#7C828A` | 标签、表头、辅助信息 |

### 3.5 Semantic（Coinbase 精确色值）

| Token | 新值 | 用途 |
|-------|------|------|
| `--up` | `#05B169` | 上涨/盈利（绿） |
| `--down` | `#CF202F` | 下跌/亏损（红） |
| `--warning` | `#F4B000` | 警告 (Coinbase accent-yellow) |
| `--info` | `#0052FF` | 信息（复用 primary） |

### 3.6 Border & Hairline

| Token | 新值 | 用途 |
|-------|------|------|
| `--border` | `#DEE1E6` | 默认 1px 边框 |
| `--border-subtle` | `#EEF0F3` | 更轻的边框（sidebar 分隔、表行） |
| `--border-strong` | `#A8ACB3` | 强调边框（focus ring 外圈） |
| `--input` | `#DEE1E6` | 输入框边框 |
| `--ring` | `#0052FF` | Focus ring 颜色 |

### 3.7 中文红绿方向

```css
[lang="zh"] {
  --up: #CF202F;    /* A 股习惯：红涨 */
  --down: #05B169;  /* A 股习惯：绿跌 */
}
```

---

## 4. 字体系统

### 4.1 Font Family

| 角色 | 字体 | Fallback |
|------|------|----------|
| Display / UI | Inter | system-ui, -apple-system, sans-serif |
| Mono (数字) | JetBrains Mono | monospace |

```css
--font-sans: 'Inter', system-ui, -apple-system, sans-serif;
--font-body: 'Inter', system-ui, -apple-system, sans-serif;
--font-mono: 'JetBrains Code', 'JetBrains Mono', monospace;
```

### 4.2 Type Scale

| Token | Size | Weight | Line Height | Letter Spacing | Use |
|-------|------|--------|-------------|----------------|-----|
| display-lg | 52px | 400 | 1.0 | -1.3px | Dashboard 总权益大数 |
| display-md | 44px | 400 | 1.09 | -1px | KPI 主数值 |
| display-sm | 36px | 400 | 1.11 | -0.5px | 回测 return 大数 |
| title-lg | 32px | 400 | 1.13 | -0.4px | 页面主标题 |
| title-md | 18px | 600 | 1.33 | 0 | 卡片标题 |
| title-sm | 16px | 600 | 1.25 | 0 | 区块标题 |
| body-md | 16px | 400 | 1.5 | 0 | 正文 |
| body-sm | 14px | 400 | 1.5 | 0 | 辅助文字 |
| caption | 12px | 500 | 1.4 | 0 | 标签/表头 |
| button | 16px | 600 | 1 | 0 | 按钮标签 |

### 4.3 Number Typography（Mono 专用）

| Token | Size | Weight | Line Height | Use |
|-------|------|--------|-------------|-----|
| number-lg | 44px | 400 | 1.09 | KPI 大数 |
| number-md | 16px | 500 | 1.4 | 表格内价格/数量 |
| number-sm | 14px | 500 | 1.4 | 行内数字/百分比 |

### 4.4 字体加载

```html
<!-- Inter + JetBrains Mono via Google Fonts -->
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet" />
```

---

## 5. 间距 & 圆角 & 层次

### 5.1 Spacing

| Token | 新值 | 用途 |
|-------|------|------|
| `--grid-gap` | 16px | 卡片间/列间间距 |
| `--card-padding` | 24px | 卡片内边距 |
| `--page-padding` | 24px | 页面主内容外边距 |
| `--sidebar-width` | 240px | 侧边栏宽度 |
| `--header-height` | 56px | 顶栏高度 |

### 5.2 Radius

| Token | 新值 | 用途 |
|-------|------|------|
| `--radius` (种子) | 0.375rem | 6px 基准 |
| radius-sm (0.6x) | ~3.6px | 小标签/徽章 |
| radius-md (0.8x) | ~4.8px | 按钮、输入框 |
| radius-lg (1x) | 6px | 内容卡片 |
| radius-xl (1.4x) | ~8.4px | 大容器/模态 |

### 5.3 Elevation（无阴影层次）

| 层级 | 实现 | 说明 |
|------|------|------|
| Page floor | `bg(--background)` = `#FFF` | 全白地板 |
| Sidebar | `bg(--surface-1)` = `#F7F7F7`，无右边框 | 灰色块区分 |
| Card | `bg(--card)` = `#FFF` + `border: 1px solid var(--border)` | hairline 分隔 |
| Card inset | `bg(--surface-2)` = `#EEF0F3` | 卡片内子区块 |
| Hover | `bg(--surface-3)` = `#DEE1E6` | 行/按钮 hover |
| Header | `bg(#FFF)` + `border-bottom: 1px solid var(--border-subtle)` | 底部极轻分割 |

**严格禁止**：box-shadow、drop-shadow、glassmorphism、gradient surfaces。

---

## 6. 基础组件（shadcn/ui 适配）

以下所有组件沿用 shadcn/ui 结构，仅 CSS token 按第 3-5 节更新。

### 6.1 Button

| Variant | Background | Text | Border | Hover |
|---------|-----------|------|--------|-------|
| default (primary) | `#0052FF` | `#FFF` | none | bg `#003ECC` |
| secondary | `#EEF0F3` | `#0A0B0D` | none | bg `#DEE1E6` |
| outline | transparent | `#0A0B0D` | `1px #DEE1E6` | bg `#F7F7F7` |
| ghost | transparent | `#5B616E` | none | bg `#F7F7F7` |
| destructive | `#CF202F` | `#FFF` | none | bg 加深红 |

- 默认高度：40px (h-10)
- 默认 padding：16px 24px
- 默认圆角：6px
- 字号：16px / 600w

### 6.2 Card

```css
background: #FFF;
border: 1px solid #DEE1E6;
border-radius: 6px;
padding: 24px;
/* 无 box-shadow */
```

### 6.3 Input

- Height: 40px (h-10)
- Border: 1px `#DEE1E6`
- Border-radius: 6px
- Padding: 10px 16px
- Focus: `ring 2px #0052FF`
- Font: 16px / 400w

### 6.4 Table

| Element | Style |
|---------|-------|
| Header row | h-10 (40px), 12px 600w `#7C828A` |
| Body row | h-10 (40px), 14px 400w |
| Cell padding | 12px 16px |
| Row divider | `border-b: 1px solid #EEF0F3` |
| Row hover | bg `#F7F7F7` |
| Number cells | JetBrains Mono, tabular-nums, text-right |

### 6.5 Badge

Coinbase semitransparent 风格：

| Variant | Background | Text |
|---------|-----------|------|
| default | `rgba(0,82,255,0.10)` | `#0052FF` |
| success | `rgba(5,177,105,0.10)` | `#05B169` |
| destructive | `rgba(207,32,47,0.10)` | `#CF202F` |
| warning | `rgba(244,176,0,0.10)` | `#F4B000` |
| muted | `rgba(124,130,138,0.10)` | `#5B616E` |

- Padding: 2px 8px
- Border-radius: 4px
- Font: 12px / 500w
- **不** uppercase

### 6.6 Tabs

- 容器底边：`1px solid #EEF0F3`
- 非激活 tab：14px 400w `#7C828A`
- 激活 tab：14px 600w `#0A0B0D` + 底部 `2px #0052FF` 下划线
- Tab padding：8px 16px

### 6.7 Dialog / Popover

- Background: `#FFF`
- Border: `1px solid #DEE1E6`
- Border-radius: 8px
- **无 box-shadow**
- Backdrop: `rgba(0,0,0,0.3)`

### 6.8 其他组件

以下保持 shadcn 默认结构，颜色 token 自动适配：
DropdownMenu、Select、Textarea、Tooltip、ScrollArea、Separator、Command、Label、Sonner

---

## 7. 金融组件

### 7.1 现有组件重设计

#### KpiCard

```
结构:
┌──────────────────────────┐
│ label  12px 600w #5B616E │
│ $42,340.00  44px 400w    │ ← JetBrains Mono
│ ▲ +2.34%  14px up color  │
└──────────────────────────┘
- bg: #F7F7F7, 无边框
- padding: 20px 24px
- border-radius: 6px
- label/title 不 uppercase
- trend indicator: 箭头图标 + 14px mono 变化值
```

#### PositionTable

- 表头 12px 600w, h-10
- 数据行 14px, h-10
- 数字列 mono tabular-nums text-right
- PnL/PnL% 列色变 + ▲▼ 箭头
- 行间 hairline divider (`#EEF0F3`)
- hover: bg `#F7F7F7`

#### OrderForm

```
┌─────────────────────┐
│ 000001.SZ  平安银行  │ ← 14px 600w header
│ 现价 ¥12.50          │ ← 14px mono
├─────────────────────┤
│ [Buy] [Sell]        │ ← tab 切换，绿色/红色 active
│                     │
│ 类型: [市价 ▼]      │ ← Select
│ 数量: [________]     │ ← Input
│ 价格: [________]     │ ← Input (限价单显示)
│                     │
│ 预估成本: ¥12,500   │ ← 14px mono
│ 手续费:   ¥3.75     │
├─────────────────────┤
│ [     买入 ▼     ]  │ ← 大按钮, 绿底(buy)/红底(sell)
└─────────────────────┘
- bg: #FFF, border: 1px #DEE1E6
- padding: 20px
- border-radius: 6px
```

#### OrderBook

```
深度可视化:
bids (绿)           asks (红)
████████ 12.50      12.51 ████
██████   12.49      12.52 ██████
████     12.48      12.53 ████████
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
         价差: 0.02 (0.16%)
```
- 行高 20px (高密度)
- 价格列 + 数量列 + 累计列
- 背景 bar 用 opacity 渐降（最深 20%，最浅 3%）
- 字体: 14px JetBrains Mono
- 中间价差行: hairline 分隔

#### EquityChart / CandlestickChart

- Canvas: `#FFF`, border: `1px #DEE1E6`
- 网格线: `#EEF0F3`
- 涨: `#05B169` / 跌: `#CF202F`
- Tooltip: 白底 card

#### TradeTimeline / CorrelationMatrix / ScreenerGrid / LogViewer

- 整体容器用 Card 样式（白底 hairline）
- 颜色 token 自动适配
- 字体从 Fira 切换到 Inter

### 7.2 新增组件

#### StatCallout — 大数字标语

```tsx
<StatCallout
  label="总权益"
  value="¥1,247,890.50"
  change="+2.34%"
  direction="up"
/>
```
- 数字: display-md (44px 400w) JetBrains Mono
- 标签: 12px 600w #5B616E
- 变化: 14px mono + 箭头图标
- bg: transparent (不套卡片)

#### PriceTicker — 实时价格条

```tsx
<PriceTicker symbol="000001.SZ" name="平安银行" price={12.50} change={0.32} changePct={2.63} high={12.65} low={12.10} />
```
- 横条布局: symbol · 名称 · 价格 · 涨跌 · 24h高/低
- 价格: display-sm (36px 400w) mono
- 涨跌: 16px mono 色变
- bg: `#F7F7F7`, border-radius: 6px
- padding: 16px 24px

#### StatusBadge — 状态徽章

```tsx
<StatusBadge status="running" />
```
- 沿用 6.5 Badge 规范
- Preset: running=蓝, filled/success=绿, cancelled/error=红, paused=黄, pending=灰
- 12px 500w

#### MarketRow — 行情列表行

```tsx
<MarketRow symbol="000001.SZ" name="平安银行" price={12.50} changePct={2.63} onClick={...} />
```
- 一整行: coin/symbol · 名称 · 最新价 (mono) · 涨跌% (色变) · chevron →
- 行高 48px, padding 0 16px
- 行间 hairline divider
- hover: bg `#F7F7F7`

#### DividerSection — 分段标题

```tsx
<DividerSection title="风险控制" />
```
- 灰底横条 (`#F7F7F7`), 全宽
- 文字: 12px 600w `#5B616E`
- padding: 8px 16px
- 用于设置/分析页面分组

---

## 8. 布局组件

### 8.1 Sidebar

```
┌──────────────────┐
│ ■ AStockPursue   │ ← logo: 24px 蓝色方块 + 16px 600w
├──────────────────┤
│ TRADE            │ ← 12px 600w #7C828A (section label)
│  📊 Dashboard    │ ← 14px 400w, 36px height
│  📈 Trading      │    active: bg(rgba(0,82,255,0.08))
│  📋 Orders       │            text #0052FF
│  📌 Positions    │            no left border bar
│                  │    inactive: text #5B616E
│ RESEARCH         │    hover: bg #F7F7F7
│  ...             │
├──────────────────┤
│ user@account     │ ← 12px #7C828A
└──────────────────┘
- width: 240px
- bg: #F7F7F7
- 无右边框
- section label padding: 16px 16px 4px
```

### 8.2 Header

```
┌────────────────────────────────────────────────────────┐
│ Dashboard > Overview                     🔔  👤 User  │
└────────────────────────────────────────────────────────┘
- height: 56px
- bg: #FFF
- border-bottom: 1px solid #EEF0F3
- breadcrumb: 14px, 当前段 #0A0B0D, 上级 #7C828A
- notification bell: 18px icon + dot badge (蓝)
- user avatar: 32px 圆 + 14px 用户名文字
```

### 8.3 SidebarLayout

- Sidebar: fixed, left:0, top:0, width:240px, height:100vh
- Header: fixed, left:240px, right:0, top:0, height:56px
- Main: margin-left:240px, margin-top:56px, padding:24px

---

## 9. 页面适配策略

### 9.1 纯 Token 适配（无结构变化）
login, register, settings, system, agent, factors, workflow, broker, market, screener, scheduler

### 9.2 组件替换 + 微调

| 页面 | 改动 |
|------|------|
| Dashboard (`/`) | KpiCard → StatCallout (4个), PositionTable 保留 |
| Trading (`/trading`) | 顶部加 PriceTicker, OrderBook 密度提升, 底部加 StatusBadge |
| Backtest list | 表格 Return 列 mono + 色变, StatusBadge |
| Backtest detail | KpiCard → StatCallout (5个), 图表卡片白底 |
| Backtest create | Input h-10 对齐 |
| PaperTrading list | StatusBadge on Status 列 |
| PaperTrading detail | Start/Stop 按钮 Coinbase 样式 |
| Positions (`/trading/positions`) | PositionTable 紧凑版 + MarketRow 风格 |
| Orders (`/trading/orders`) | StatusBadge, mono 数字列 |
| Analysis pages | 图表卡片白底, DividerSection 分组 |
| Market page | MarketRow 列表组件 |

---

## 10. 实施顺序

按原子到页面逐层推进，每层独立验证：

1. **CSS Tokens** — `globals.css` 全部变量更新（颜色、字体、间距、圆角）
2. **Font loading** — `layout.tsx` 字体链接切换
3. **Base components** — 19 个 shadcn/ui 组件 theme 适配
4. **Layout components** — Sidebar, Header, SidebarLayout
5. **Financial components** — 现有 12 个重设计 + 5 个新增
6. **Pages** — 27 个页面逐页验证
7. **i18n** — 新增翻译 key（新组件标签）

---

## 11. 禁止事项

- ❌ 使用 box-shadow 做层次
- ❌ 引入第二个品牌色（只用 `#0052FF`）
- ❌ 在卡片上使用渐变背景
- ❌ display 标题用 700 weight（保持 400）
- ❌ 数字用 Inter/Sans（统一 JetBrains Mono）
- ❌ button 圆角超过 6px
- ❌ 保持 `--up`/`--down` 以外的语义色（不要黄=success、绿=info）
