# AStockPursue 前端功能补全设计

> 日期：2026-06-20 | 状态：待确认 | 参考：旧版前端、Go API 现状

## 1. 对比结论

旧版（Vite SPA）有 28 个功能页面、78 个组件、12 个 Zustand store，是一个完整的量化终端。新版（Next.js）仅有 12 个页面功能完整，6 个部分可用，13 个完全缺失，组件数 40 vs 78。

**核心差距不在样式（Coinbase 主题已完成），而在功能深度。**

---

## 2. 缺失功能清单与优先级

### P0 — 核心交互缺失（用户最直观感知）

| 功能 | 旧版 | 新版 | 差距 |
|------|------|------|------|
| **Workflow 画布** | @xyflow/react 可视化拖拽 DAG 编辑器，节点面板、运行摘要、图表查看器 | 仅有列表/详情 CRUD 页 | 整个画布子系统缺失 |
| **Strategy Lab** | Monaco 代码编辑器 + 图表面板 + AI 聊天 + 模板浏览器 + 优化/验证面板 | 仅有回测创建表单 | 整个 IDE 缺失 |
| **Factor Mining** | GP 进化实时 UI：适应度曲线、表达式树查看器、候选表、世代日志、精英追踪、IC 衰减图 | 因子列表页（空） | 整个挖掘 UI 缺失 |
| **AI Agent 聊天** | 13 个聊天组件：消息气泡、思考时间线、工具进度、运行完成卡片、示例提示、PineScript 查看器 | 基础聊天（消息+输入） | 聊天体验降级严重 |

### P1 — 分析工具缺失

| 功能 | 旧版 | 新版 |
|------|------|------|
| **Alpha Zoo 浏览器** | 因子浏览/搜索/基准测试/SSE 流式评测 | 无 |
| **Indicator Lab** | 指标 IDE：代码编辑器、AI 面板、内置指标、图表、参数面板 | 无 |
| **Attribution 归因** | Brinson 瀑布图、因子暴露、行业对比 | 无 |
| **Backtest Compare** | 多回测并排对比，ECharts 叠加图 | 无 |
| **Sentiment 情绪** | 多源新闻聚合、情绪评分、SSE 实时推送 | 无 |
| **Options 计算器** | Black-Scholes、二叉树、波动率曲面、希腊值 | 无 |

### P2 — 平台功能缺失

| 功能 | 旧版 | 新版 |
|------|------|------|
| **Dashboard** | 28KB：市场指数、数据源健康、情绪面板 | 2.4KB：KPI 卡片 |
| **Screener** | 18.7KB：多模式筛选、预设、AI 推荐、导出工作流 | 基础排序表格 |
| **Paper Trading** | 34.7KB：SSE 实时、月度热图、风险配置、交易历史 | 基础列表+详情 |
| **Live Trading** | 14.3KB：券商面板、自选股、分时图、通知配置、基本面 | 基础交易面板 |
| **Agent Chat** | 30.4KB：丰富的对话界面 + 工具可视化 | 基础聊天 |

### P3 — 辅助功能缺失

| 功能 | 旧版 | 新版 |
|------|------|------|
| Strategy Marketplace | 发布/浏览/安装/评分社区策略 | 无 |
| DataSource Status | 数据源健康监控、缓存命中率 | 无 |
| Projects Dashboard | 项目管理，工作流计数 | 无 |
| Docs | 应用内文档浏览器 | 无 |
| Admin/User Management | 用户管理 | 无 |

---

## 3. 实施策略

按用户体验影响排序，分 4 个 Phase 推进。

### Phase 1: 可视化 Workflow 画布（P0 最大缺口）

**目标**：在 Next.js 中恢复 @xyflow/react 可视化 DAG 编辑器。

**文件**：
- `frontend/components/workflow/WorkflowCanvas.tsx` — ReactFlow 画布
- `frontend/components/workflow/NodePalette.tsx` — 节点类型面板（可拖拽）
- `frontend/components/workflow/NodePanel.tsx` — 节点配置侧栏
- `frontend/components/workflow/BaseNode.tsx` — 画布上的自定义节点渲染
- `frontend/stores/workflowStore.ts` — Zustand 工作流状态
- `frontend/app/workflow/[id]/page.tsx` — 画布页面（替换当前列表）

**依赖**：`npm install @xyflow/react`

**API 需求**（Go 后端已有）：
- `POST /api/v1/workflow/execute` — 执行工作流
- `GET /api/v1/workflow/node/:id` — 获取节点结果

---

### Phase 2: 交易分析核心

#### 2a. Strategy Lab（代码 IDE）
- `frontend/components/strategy-lab/CodeEditor.tsx` — Monaco 编辑器
- `frontend/components/strategy-lab/BacktestPanel.tsx` — 回测配置+结果
- `frontend/components/strategy-lab/ChartPanel.tsx` — ECharts 图表
- `frontend/app/strategy-lab/page.tsx` — 策略 IDE 页面

**依赖**：`npm install @monaco-editor/react echarts`

#### 2b. Dashboard 增强
- 从旧版迁移 IndexTickerBar、MarketSentimentPanel、DataSourceHealthCard
- 连接 WebSocket ticker 频道 → 显示实时指数
- KPI 卡片连接 API 数据

#### 2c. Screener 增强
- 多模式筛选（AND / rank / score）
- 预设保存/加载
- 导出到 Workflow

---

### Phase 3: AI + 因子

#### 3a. Agent Chat 增强
- 恢复 13 个聊天组件：ThinkingTimeline、ToolProgressIndicator、RunCompleteCard 等
- 恢复 ExamplePrompts、WelcomeScreen
- SSE 流式响应（Go 已有 gRPC LLMService）

#### 3b. Factor Mining UI
- GP 进化控制面板
- 实时世代日志
- 适应度曲线、表达式树查看器
- 候选因子表

#### 3c. Alpha Zoo 浏览器
- 因子搜索/过滤/排序
- 基准测试面板
- 因子详情页

---

### Phase 4: 平台收尾

- Attribution 归因页面（Brinson/因子/行业）
- Sentiment 情绪分析页面
- Backtest Compare 对比页面
- Options 计算器页面
- Marketplace 策略市场
- DataSource Status 数据源监控
- Admin 用户管理

---

## 4. 组件复用策略

旧版 78 个组件可以直接迁移到新版，只需：
1. 替换 `react-router-dom` → Next.js `Link` / `useRouter`
2. 替换 `@/lib/api` → Next.js API Routes 或 SWR hooks
3. 替换 `useI18n()` → `useTranslations()`（next-intl）
4. 更新样式：`bg-[var(--surface-3)]` → `bg-white border border-[var(--border)]`
5. 保持组件内部逻辑不变

**估算**：约 40 个组件可直接迁移（60%），20 个需要较大改动（30%），7 个需要重写（10%）。

---

## 5. 新 API 端点需求

Go 后端需新增以下端点以支持恢复的页面：

| 端点 | 用途 | 页面 |
|------|------|------|
| `POST /api/v1/attribution/brinson` | Brinson 归因 | Attribution |
| `POST /api/v1/attribution/factor` | 因子归因 | Attribution |
| `POST /api/v1/attribution/sector` | 行业归因 | Attribution |
| `POST /api/v1/sentiment` | 新闻情绪查询 | Sentiment |
| `POST /api/v1/options/black-scholes` | BS 定价 | Options |
| `POST /api/v1/options/binomial` | 二叉树定价 | Options |
| `POST /api/v1/options/greeks` | 希腊值 | Options |
| `GET /api/v1/market/fundamentals/:symbol` | 基本面数据 | Trading |
| `GET /api/v1/market/intraday/:symbol` | 分时图 | Trading |
| `POST /api/v1/marketplace/publish` | 发布策略 | Marketplace |
| `GET /api/v1/marketplace/browse` | 浏览市场 | Marketplace |
| `POST /api/v1/marketplace/install` | 安装策略 | Marketplace |
| `GET /api/v1/admin/users` | 用户列表 | Admin |
| `DELETE /api/v1/admin/users/:id` | 删除用户 | Admin |

以上大部分可从旧版 Python `src/api/` 路由直接移植到 Go handler（逻辑已有 Python 参考）。

---

## 6. 实施时间估算

| Phase | 内容 | 前端 | Go API | 合计 |
|-------|------|------|--------|------|
| Phase 1 | Workflow 画布 | 3-4 天 | 0 | 3-4 天 |
| Phase 2a | Strategy Lab | 2-3 天 | 0 | 2-3 天 |
| Phase 2b | Dashboard 增强 | 1 天 | 0 | 1 天 |
| Phase 2c | Screener 增强 | 1 天 | 0 | 1 天 |
| Phase 3a | Agent Chat | 1-2 天 | 0 | 1-2 天 |
| Phase 3b | Factor Mining UI | 2 天 | 已有 gRPC | 2 天 |
| Phase 3c | Alpha Zoo | 1 天 | 已有 gRPC | 1 天 |
| Phase 4 | 收尾 7 页面 | 3 天 | 2-3 天 | 5-6 天 |
| **总计** | | **14-18 天** | **2-3 天** | **16-21 天** |
