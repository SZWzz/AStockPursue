# Onboarding Wizard Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development

**Goal:** Build 4-step onboarding wizard with localStorage persistence and dashboard CTA cards.

**Tech Stack:** Next.js 15, React 19, TypeScript, Zustand, next-intl, Tailwind CSS

## Global Constraints

- `cd frontend && pnpm build` 零错误
- `pnpm test` 156 用例无回归
- i18n: zh.json + en.json 键值同步
- Coinbase 设计语言：`bg-[var(--card)]`, `border-[var(--border)]`, `rounded-2xl`

---

### Task 1: 扩展 uiStore 添加 onboarding 状态

**Files:** Modify `frontend/stores/uiStore.ts`

- [ ] 添加 `onboardingCompleted: boolean`, `onboardingDismissed: boolean`
- [ ] 添加 `completeOnboarding()`, `dismissOnboarding()`, `resetOnboarding()` 方法
- [ ] persist 到 localStorage
- [ ] `pnpm test __tests__/stores/uiStore.test.ts` 扩展
- [ ] Commit: `feat: add onboarding state to uiStore`

---

### Task 2: 添加 i18n 翻译

**Files:** Modify `frontend/messages/zh.json`, `frontend/messages/en.json`

- [ ] 新增 `onboarding` 命名空间，含 step1-4 的 title/description/button、skip/next/complete
- [ ] 新增 `dashboard.quickStart` 卡片文字
- [ ] `pnpm build` 验证无缺失键

---

### Task 3: 创建 OnboardingWizard 组件

**Files:** Create `frontend/components/onboarding/OnboardingWizard.tsx`

- [ ] 实现遮罩 + 居中卡片
- [ ] 4 步步骤内容（图标 + 标题 + 描述 + 按钮）
- [ ] 进度点指示器
- [ ] 跳过/下一步按钮逻辑
- [ ] 使用 `useTranslations('onboarding')` 国际化

---

### Task 4: Dashboard 集成触发

**Files:** Modify `frontend/app/page.tsx`

- [ ] 引入 `useUIStore`，检查 `onboardingCompleted`
- [ ] 未完成时渲染 `<OnboardingWizard />`
- [ ] 升级空状态：无数据时显示快速开始卡片组（创建策略/连接券商/运行回测）
- [ ] `pnpm build && pnpm test`

---

### Task 5: 设置页重入按钮

**Files:** Modify `frontend/app/settings/page.tsx`

- [ ] General tab 添加「重新开始引导」按钮
- [ ] 点击调用 `resetOnboarding()` → 刷新页面弹出向导

---

### Task 6: 组件测试

**Files:** Create `frontend/__tests__/components/OnboardingWizard.test.tsx`

- [ ] 10+ 测试：渲染 4 步、前进/后退、跳过、完成回调、进度点状态
- [ ] `pnpm test` — 166+ 用例通过

---

## Final Verification

- [ ] `cd frontend && pnpm build` — 零错误
- [ ] `cd frontend && pnpm test` — 166+ 用例通过
