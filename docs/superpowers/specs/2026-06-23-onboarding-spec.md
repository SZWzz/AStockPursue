# Onboarding Wizard Spec

> **Date**: 2026-06-23  
> **Scope**: 4-step onboarding wizard for new users

---

## 1. OnboardingWizard 组件

**File**: `frontend/components/onboarding/OnboardingWizard.tsx`

- 全屏半透明遮罩 `bg-black/50 fixed inset-0 z-50`
- 居中卡片 `max-w-lg w-full`，Coinbase 风格（`rounded-2xl bg-[var(--card)] border-[var(--border)]`）
- 顶部：步骤进度点（4 个圆点，已完成→实心 active→高亮 未完成→灰色）
- 中间：步骤内容（图标 + 标题 + 描述 + 操作按钮）
- 底部：「跳过」文字按钮 + 「下一步」主按钮

**4 步内容**：

| 步骤 | 图标 | 标题 | 描述 | 操作按钮 |
|------|------|------|------|---------|
| 1 | Rocket | 欢迎使用 AStockPursue | AI 驱动的量化研究与交易平台。自然语言描述策略，自动回测，一键实盘。 | 开始设置 |
| 2 | Link | 连接券商 | 连接 Binance/OKX/Futu 等券商账户，获取实时行情与交易能力。 | 去连接 / 跳过 |
| 3 | Brain | 创建第一个策略 | 用自然语言描述你的交易想法，AI 自动生成策略代码并回测。 | 试试看 / 跳过 |
| 4 | ChartBar | 运行首次回测 | 选择股票、设置参数，查看回测收益曲线和风险指标。 | 开始回测 / 完成 |

## 2. onboardingStore

**Modify**: `frontend/stores/uiStore.ts`

新增字段：
```ts
onboardingCompleted: boolean  // persist to localStorage
onboardingDismissed: boolean  // user explicitly skipped
```

## 3. Dashboard 触发

**Modify**: `frontend/app/page.tsx`

登录后检查 `onboardingCompleted === false` → 渲染 `<OnboardingWizard />`。
完成/跳过时设置 `onboardingCompleted = true`。

## 4. Dashboard 空状态升级

**Modify**: `frontend/app/page.tsx`

空数据时不再只显示纯 EmptyState，而是显示「快速开始」卡片组：
- 卡片 1: 创建策略 → `/strategy-lab`
- 卡片 2: 连接券商 → `/broker`
- 卡片 3: 运行回测 → `/backtest`

## 5. 设置页重入

**Modify**: `frontend/app/settings/page.tsx`

General tab 增加「重新开始引导」按钮，重置 `onboardingCompleted = false`。

## 6. 国际化

**Modify**: `frontend/messages/zh.json`, `frontend/messages/en.json`

新增 ~20 个 onboarding 相关翻译键。

---

## 验证

- `cd frontend && pnpm build` — 零错误
- `pnpm test` — 156 用例无回归
- 手动验证：清除 localStorage → 刷新 → 应弹出向导 → 走完 4 步 → 不再弹出
