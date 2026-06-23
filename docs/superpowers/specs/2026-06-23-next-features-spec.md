# Next Features Execution Spec — 2026-06-23

> **来源**: `docs/next-features.md`  
> **扫描结论**: 5 个功能中，基础设施全部就绪但特征层代码均未完成。  
> **执行方式**: 按优先级分 5 个 Wave，Wave 内 Go/Python/Frontend 任务可并行。

---

## 全局约束

| 层 | 验证命令 | 基线 |
|----|---------|------|
| Go | `cd services/go && go build ./... && go test ./... -race -count=1` | 零回归 |
| Python | `cd services/python && python -m pytest tests/ -v` | 零回归 |
| Frontend | `cd frontend && npx next build 2>&1 \| tail -5` | 零构建错误 |
| DB | migration SQL 需在 test DB 上验证通过 | schema 幂等 |

---

## 现状盘点

| 功能 | 基础设施 | 特征层 | 依赖风险 |
|------|:---:|:---:|:---:|
| 策略模板市场 | 🟢 templates.json + DB schema + 前端骨架 | 🔴 需 Go API + StrategyCard 组件 | 低 |
| 因子信号推送 | 🟢 scheduler + notify(6渠道) + signal nodes | 🔴 需简报生成 + 订阅管理 | 低 |
| 多轮策略精炼 | 🟢 AgentLoop + Swarm + 分解器 + 前端页 | 🔴 需顾问编排 + 精炼节点 | 中（LLM 质量依赖） |
| 回测竞技场 | 🟢 回测引擎 + 统一品种引擎 | 🔴 从零开始 | 低（引擎现成） |
| 实盘监控 | 🟢 WebSocket + LiveTrading + notify | 🔴 从零开始 | 中（需偏离度算法） |

---

## Wave 1 — 策略模板市场（★★★★ 业务价值，★★★ 难度，无依赖）

> **目标**: 11 个预置策略模板 + 参数面板 + 一键回测 + 发布到市场

### Task 1.1 — Go Marketplace API（Go）

**文件**:
- 新建 `services/go/internal/api/handler/marketplace.go`
- 修改 `services/go/internal/api/router.go`

**实现**:
1. 新建 `marketplace.go`，实现 `MarketplaceHandler` struct，接收 `sql.DB` 注入
2. `GET /api/v1/marketplace/templates` — 读取 `services/python/src/lab/templates.json` 并返回（Go 侧静态嵌入或文件读取）
3. `GET /api/v1/marketplace/strategies` — 查询 `vt_strategy_marketplace` 表，返回已发布策略列表（分页 + 排序：评分/安装数/最近）
4. `GET /api/v1/marketplace/strategies/:id` — 单个策略详情
5. `POST /api/v1/marketplace/strategies` — 发布策略（来自模板调参后的回测结果 + 参数快照）
6. `POST /api/v1/marketplace/strategies/:id/rate` — 评分（1-5 星）
7. `POST /api/v1/marketplace/strategies/:id/install` — 安装计数递增
8. 在 `router.go` 注册 6 个端点
9. `go build ./... && go test ./internal/api/handler/ -run TestMarketplace -v -count=1`（需要新建测试文件）
10. Commit: `feat: marketplace API — templates listing, strategy CRUD, rating, install`

---

### Task 1.2 — Frontend 策略卡片 + 参数面板（Frontend）

**文件**:
- 新建 `frontend/components/financial/StrategyCard.tsx`
- 新建 `frontend/components/financial/ParamPanel.tsx`
- 修改 `frontend/app/marketplace/page.tsx`（如果存在骨架，则改造为完整体）

**实现**:
1. 新建 `StrategyCard.tsx`：
   - Props: `{ id, name, category, author, params, avg_return, max_drawdown, sharpe, installs, rating }`
   - 卡片布局：分类标签 + 名称 + 关键指标（夏普/回撤）+ 安装数/评分 + 一键安装按钮
2. 新建 `ParamPanel.tsx`：
   - 从模板 YAML/JSON 的 params 定义动态生成滑块/输入框
   - 滑条范围取模板 `min`/`max`，步骤合理
   - 回测按钮（调用 Go backtest API，传入参数快照）
3. 改造 `app/marketplace/page.tsx`：
   - 顶部：模板分类筛选（trend/mean_reversion/momentum/volume/multi_factor）
   - 网格：每行 3 张 StrategyCard
   - 点击卡片 → 展开 ParamPanel + 回测结果区域
4. `npx next build` 验证零构建错误
5. Commit: `feat: StrategyCard + ParamPanel + marketplace browsing page`

---

### Task 1.3 — Frontend Marketplace 测试（Frontend）

**文件**: 新建 `frontend/__tests__/components/StrategyCard.test.tsx`

**实现**:
1. 6 个测试用例：
   - 渲染基本卡片（名称 + 分类标签）
   - 显示关键指标（夏普/最大回撤/年化收益）
   - 显示安装数 + 评分
   - 空数据回退（无评分 → 显示 "暂无"）
   - 安装按钮触发回调
   - 分类标签颜色映射（trend=蓝, mean_reversion=绿, momentum=橙, volume=紫）
2. `npx vitest run __tests__/components/StrategyCard.test.tsx`
3. Commit: `test: StrategyCard component tests (6 cases)`

---

## Wave 2 — 因子信号推送（★★★★★ 业务价值，★★☆ 难度）

> **目标**: 每日 15:30 跑因子计算，筛选 Top 5 IC 因子，生成简报推送
> **已有**: scheduler 引擎（Go+Python）、通知渠道（6种）、信号生成节点

### Task 2.1 — Python 信号简报生成（Python）

**文件**: 新建 `services/python/src/services/signal_brief.py`

**实现**:
1. 实现 `SignalBriefGenerator` 类：
   - `__init__(self, factor_service, market_data_provider)` — 注入依赖
   - `compute_daily_factors(date) → Dict[str, FactorResult]` — 调用现有因子服务，对 HS300/ZZ500 成分股计算所有因子值
   - `compute_cross_sectional_ic(factor_values, forward_returns, date) → Dict[str, float]` — 向量化截面 IC 计算（复用 fitness.py 的 `ic_fitness` 逻辑）
   - `select_top_factors(ics, n=5) → List[Tuple[str, float, List[Signal]]]` — 按 |IC| 排序取 Top 5，附带对应买卖信号
   - `render_markdown(top_factors, date) → str` — 按设计模板渲染 Markdown 简报
2. Markdown 模板严格按设计文档：
   ```markdown
   📊 AStockPursue 每日信号 — {date}
   
   今日最强因子（截面 IC Top 5）：
   1. momentum_20d   IC=0.042  看多: 600519.SH, 000858.SZ
   2. reversal_5d    IC=-0.038  看空: 601318.SH
   ...
   ```
3. 新建 `services/python/tests/test_signal_brief.py`：
   - `test_compute_cross_sectional_ic` — 用 mock DataFrame 验证 IC 计算
   - `test_select_top_factors` — 验证 Top 5 筛选
   - `test_render_markdown` — 验证简报模板渲染
   - `test_empty_factors` — 无因子时返回空简报
4. `python -m pytest tests/test_signal_brief.py -v`
5. Commit: `feat: signal brief generator — daily factor IC + Top 5 + Markdown report`

---

### Task 2.2 — Python 定时任务编排（Python）

**文件**:
- 新建 `services/python/src/services/signal_push_job.py`
- 修改 `services/python/src/services/scheduler_engine.py`（注册 job）

**实现**:
1. 新建 `signal_push_job.py`：
   - `run_signal_push(date=None)` — 入口函数，参数化以便测试
   - 调用 `SignalBriefGenerator` 生成简报
   - 调用 `NotifyEngine.send()` 推送简报到所有已启用渠道（Telegram/微信/邮件）
   - 通过 `user_settings` 表查询启用推送的用户及其渠道配置
   - 错误处理：渠道失败不阻断其他渠道，记录到 PG
   - 日志记录每次推送的因子数 + 渠道数 + 耗时
2. 在 `scheduler_engine.py` 注册 `signal_push` job type：
   - 默认 cron: `30 15 * * 1-5`（交易日下午 3:30）
   - 调用入口：`run_signal_push()`
3. 新建 `services/python/tests/test_signal_push_job.py`：
   - `test_run_signal_push_with_mock_channels` — 验证多渠道推送
   - `test_run_signal_push_no_users` — 无订阅用户时跳过
   - `test_run_signal_push_channel_failure` — 单渠道失败不阻断其他
4. `python -m pytest tests/test_signal_push_job.py -v`
5. Commit: `feat: daily signal push job — cron-driven factor brief → multi-channel notify`

---

### Task 2.3 — Go 信号订阅 API（Go）

**文件**:
- 新建 `services/go/internal/api/handler/signal_push.go`
- 修改 `services/go/internal/db/user_settings.go`（如果不存在则新建）
- 修改 `services/go/internal/api/router.go`

**实现**:
1. 新建 `signal_push.go`，实现 `SignalPushHandler`：
   - `GET /api/v1/signals/subscription/status` — 返回当前用户订阅状态 + 各渠道配置快照（脱敏）
   - `PUT /api/v1/signals/subscription` — 更新订阅：`{ "enabled": true, "channels": {"telegram": {"chat_id": "..."}, "email": {"to": "..."}} }`
   - `POST /api/v1/signals/subscription/test` — 发送一条测试简报到选中渠道
2. 持久化：写入 `user_settings` 表（若不存在则新建 migration）：
   - `signal_push_enabled BOOLEAN DEFAULT false`
   - `push_channels JSONB DEFAULT '{}'`
3. 在 `router.go` 注册 3 个端点
4. 新建测试：`services/go/internal/api/handler/signal_push_test.go`
5. `go build ./... && go test ./internal/api/handler/ -run TestSignal -v -count=1`
6. Commit: `feat: signal push subscription API — enable/disable/channels/test`

---

### Task 2.4 — Frontend 推送配置页（Frontend）

**文件**:
- 新建 `frontend/app/settings/push/page.tsx`（或扩展现有 `app/settings/` 页）
- 修改 `frontend/app/settings/layout.tsx`（添加子导航）

**实现**:
1. 推送频道配置表单：
   - 总开关：`signal_push_enabled` toggle
   - Telegram：`bot_token`（已预填）+ `chat_id` 输入框 + 获取 chat_id 指引链接
   - 企业微信：`webhook_url` 输入框
   - 邮件：SMTP host/port + 收件邮箱 + 密码（字段脱敏显示，修改时需输入当前密码）
2. 测试按钮：每个渠道一个「发送测试」按钮
3. `useSWR` 获取/更新订阅状态（调用 Wave 2.3 的 API）
4. `npx next build` 验证零构建错误
5. Commit: `feat: push settings page — channel config + test send`

---

## Wave 3 — 多轮策略精炼（★★★★ 业务价值，★★★★ 难度）

> **目标**: NL→策略从单轮变多轮：反问→澄清→生成→回测→展示→追问调整
> **已有**: AgentLoop（50轮ReAct）+ Swarm DAG + 分解器 + 前端 agent 页

### Task 3.1 — Python 策略顾问 Agent（Python）

**文件**: 新建 `services/python/src/agent/strategy_advisor.py`

**实现**:
1. 实现 `StrategyAdvisor` 类，继承/复用 `AgentLoop`：
   - **状态机 5 阶段**：
     - `INTENT_ANALYSIS` — 分析用户意图，识别缺失参数（标的池/频率/风控偏好）
     - `PARAM_CLARIFICATION` — 生成反问，等待用户补充
     - `STRATEGY_GENERATION` — 调用分解器/策略生成器生成代码
     - `BACKTEST_RESULT` — 展示回测结果（夏普/回撤/权益曲线），AI 解读
     - `ITERATION` — 等待用户反馈，迭代调整
   - 每阶段有 `max_rounds` 限制（防止无限循环）
   - 上下文管理：前轮对话摘要 + 当前参数状态 + 回测结果
2. 工具定义（注册到 AgentLoop 的工具集）：
   - `analyze_intent(text) → IntentResult` — LLM 解析意图
   - `generate_strategy(params) → StrategyCode` — 生成策略代码
   - `run_backtest(strategy_code, universe, date_range) → BacktestResult` — 调用 Go backtest API
   - `interpret_result(result) → str` — AI 解读回测结果
3. 新建 `services/python/tests/test_strategy_advisor.py`：
   - `test_intent_analysis_extracts_params` — 从自然语言提取参数
   - `test_param_clarification_generates_question` — 缺失参数时生成反问
   - `test_full_conversation_flow` — 端到端对话流程（mock backtest）
   - `test_iteration_feedback_changes_strategy` — 用户反馈触发策略调整
4. `python -m pytest tests/test_strategy_advisor.py -v`
5. Commit: `feat: StrategyAdvisor — 5-stage multi-round strategy refinement agent`

---

### Task 3.2 — Go Agent Chat API（Go）

**文件**:
- 新建 `services/go/internal/api/handler/agent.go`
- 修改 `services/go/internal/api/router.go`

**实现**:
1. 新建 `agent.go`，实现 `AgentHandler`：
   - `POST /api/v1/agent/chat` — 接收 `{ "message": "...", "session_id": "..." }`，转发到 Python StrategyAdvisor
   - `GET /api/v1/agent/sessions/:id` — 获取历史会话记录
   - `DELETE /api/v1/agent/sessions/:id` — 删除会话
2. Python 通信：通过 gRPC 或 HTTP 调用 Python Agent 服务（根据现有 gRPC 基础设施选择）
3. 流式响应支持（SSE 或 WebSocket，AgentLoop 已有 streaming）
4. 在 `router.go` 注册端点
5. `go build ./... && go test ./internal/api/handler/ -run TestAgent -v -count=1`
6. Commit: `feat: agent chat API — multi-round conversation with streaming`

---

### Task 3.3 — Frontend Agent 页面增强（Frontend）

**文件**: 修改 `frontend/app/agent/page.tsx`

**实现**:
1. 增强现有 agent 页面（当前存在骨架）：
   - 多轮对话界面：用户消息气泡 + AI 回复气泡（支持 Markdown 渲染）
   - 反问突出显示：AI 反问用 QuestionCard 组件突出（黄色边框 + ❓图标）
   - 回测结果嵌入：当 AI 返回回测结果时，自动渲染 BacktestResultCard（夏普/回撤/权益图缩略图）
   - 迭代建议区：AI 追问「需要调整吗？」时，显示快捷调整按钮（"调整参数""换个策略""满意"）
   - 对话持久化：通过 session_id 保存/恢复对话历史
2. 流式响应：逐字打字效果（使用 SSE EventSource）
3. `npx next build` 验证
4. Commit: `feat: enhanced agent chat — multi-round UI with backtest embedding`

---

## Wave 4 — 回测竞技场（★★★★★ 业务价值，★★★ 难度）

> **目标**: 统一评测集跑策略，按夏普/回撤排名，每周结算榜单
> **已有**: 完整回测引擎 + 统一品种引擎 + 标准化评测集配置

### Task 4.1 — Go Arena Engine（Go）

**文件**: 新建 `services/go/internal/engine/arena.go`

**实现**:
1. 实现 `ArenaEngine` struct：
   - `Evaluate(ctx context.Context, subm *ArenaSubmission) (*ArenaResult, error)` — 入口
   - 加载评测集配置（HS300 / 2022-2024 / 100万 / 佣金0.0003 / 滑点0.001 / 基准000300.SH）
   - 运行回测（复用 `BacktestRunner` + `Pipeline`）
   - 计算排名指标：夏普比率、年化收益、最大回撤、胜率、Alpha/Beta vs 基准
2. 防作弊（设计文档要求）：
   - 限制每人每周 3 次提交（查询 `arena_submissions` 表本周计数）
   - 策略代码 AST 白名单检查（复用 `sandbox` 模块）
   - 未来数据泄露检测：在回测中检测 benchmark-beating 过分合理（>99% 胜率）→ 自动标记
3. 新建测试：`services/go/internal/engine/arena_test.go`
   - `test_evaluate_with_mock_pipeline`
   - `test_submission_rate_limit`
   - `test_future_data_detection`
4. `go build ./... && go test ./internal/engine/ -run TestArena -v -count=1`
5. Commit: `feat: ArenaEngine — standardized eval runner with anti-cheat`

---

### Task 4.2 — Go Arena API + Redis 队列（Go）

**文件**:
- 新建 `services/go/internal/api/handler/arena.go`
- 修改 `services/go/internal/api/router.go`

**实现**:
1. 新建 `arena.go`：
   - `POST /api/v1/arena/submit` — 接收策略代码 + 参数 → 写入 `arena_submissions` 表 → 推入 Redis 队列（`arena:queue`）
   - `GET /api/v1/arena/submissions` — 我的提交记录（status: pending/running/done/failed）
   - `GET /api/v1/arena/rankings?week=2024-W25` — 每周榜单 Top 10（夏普/年化/回撤/胜率）
   - `GET /api/v1/arena/rankings/:id` — 单个提交的详细结果
2. Redis 队列消费者：后台 goroutine `BLPOP arena:queue` → 调用 `ArenaEngine.Evaluate()` → 结果写入 PG → 更新 `arena_rankings` 表
3. DB migration（新建 `services/go/internal/db/migrations/000005_arena.sql`）：
   ```sql
   CREATE TABLE IF NOT EXISTS arena_submissions (
     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
     user_id INT NOT NULL,
     strategy_name TEXT NOT NULL,
     strategy_code TEXT NOT NULL,
     parameters JSONB DEFAULT '{}',
     status TEXT DEFAULT 'pending',
     submitted_at TIMESTAMPTZ DEFAULT NOW(),
     completed_at TIMESTAMPTZ
   );
   CREATE TABLE IF NOT EXISTS arena_rankings (
     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
     submission_id UUID REFERENCES arena_submissions(id),
     week TEXT NOT NULL,
     sharpe_ratio FLOAT,
     annual_return FLOAT,
     max_drawdown FLOAT,
     win_rate FLOAT,
     alpha FLOAT,
     beta FLOAT,
     rank INT,
     UNIQUE(submission_id, week)
   );
   ```
4. 在 `router.go` 注册端点
5. `go build ./... && go test ./internal/api/handler/ -run TestArena -v -count=1`
6. Commit: `feat: arena API — submit/queue/rank with Redis-backed async eval`

---

### Task 4.3 — Frontend Arena 页面（Frontend）

**文件**:
- 新建 `frontend/app/arena/page.tsx`
- 新增路由到前端导航

**实现**:
1. 榜单页面：
   - 顶部：当前周标签 + 基准对比行（HS300 同期收益/夏普）
   - 排行榜表格：排名/策略名称/作者/夏普/年化/回撤/胜率
   - 金色/银色/铜色高亮前 3 名
   - 点击行展开详细结果（Alpha/Beta/权益曲线缩略图）
2. 提交页面（同页或子页）：
   - 策略代码文本框 + 策略名称
   - 提交按钮 + 本周剩余次数显示
   - 提交后轮询状态（pending → running → done）
   - 完成后显示结果卡片
3. 首页嵌入：在 `app/page.tsx` 的 Dashboard 中添加 Arena 排行榜卡片（Top 5）
4. `npx next build` 验证
5. Commit: `feat: arena page — leaderboard + submission + home page widget`

---

## Wave 5 — 实盘监控仪表盘（★★★ 业务价值，★★★★ 难度）

> **目标**: 实时监控偏离度/滑点/因子衰减，异常自动告警
> **已有**: WebSocket pub/sub + LiveTradingRunner + notify(6渠道)

### Task 5.1 — Go Monitor Engine（Go）

**文件**: 新建 `services/go/internal/engine/monitor.go`

**实现**:
1. 实现 `MonitorEngine` struct：
   - `OnBar(ctx context.Context, live *LiveStats, backtest *BacktestStats)` — 每个 bar 后计算偏离指标
   - 计算项（设计文档要求）：
     - `cumulative_return_drift` — 实盘累计收益 vs 回测预期，阈值 >20% → 🟡
     - `slippage_ratio` — 实盘滑点 / 回测预期滑点，阈值 >2x → 🟡
     - `factor_ic_decay` — 连续滑动窗口 IC < 0.01 天数，阈值 >=5 天 → 🟠
     - `max_drawdown_breach` — 实盘回撤突破历史最大 → 🔴
2. 写入监控表（新建 migration 000006_monitor.sql）：
   ```sql
   CREATE TABLE strategy_drift (
     id BIGSERIAL PRIMARY KEY,
     strategy_id INT NOT NULL,
     bar_time TIMESTAMPTZ NOT NULL,
     live_cumulative_return FLOAT,
     backtest_expected_return FLOAT,
     drift_pct FLOAT,
     slippage_ratio FLOAT,
     max_drawdown_current FLOAT,
     max_drawdown_historical FLOAT,
     alert_level TEXT
   );
   ```
3. 集成到 `LiveTradingRunner`：每个 `on_bar()` 后调用 `MonitorEngine.OnBar()`
4. `go build ./... && go test ./internal/engine/ -run TestMonitor -v -count=1`
5. Commit: `feat: MonitorEngine — real-time drift/slippage/factor-decay tracking`

---

### Task 5.2 — Go Alert 告警模块（Go）

**文件**: 新建 `services/go/internal/notify/alert.go`

**实现**:
1. 实现 `AlertManager` struct：
   - `CheckAndAlert(ctx context.Context, drift *StrategyDrift)` — 根据告警规则判断 + 推送
   - 告警规则映射（设计文档要求）：
     - 🟡 WARNING：累计偏离 >20% OR 滑点 >2x
     - 🟠 CRITICAL：因子 IC 连续 5 天 <0.01
     - 🔴 EMERGENCY：最大回撤破历史
   - 速率限制：同一规则 1 小时内不重复告警
   - 推送渠道：复用 `notify.Manager` 推送 Telegram/微信
2. `go test ./internal/notify/ -run TestAlert -v -count=1`
3. Commit: `feat: AlertManager — rule-based alerting with rate limiting + multi-channel`

---

### Task 5.3 — Go Monitor API + WebSocket 推送（Go）

**文件**:
- 新建 `services/go/internal/api/handler/monitor.go`
- 修改 `services/go/internal/api/router.go`
- 修改 `services/go/internal/api/ws.go`（可选：添加 monitor channel）

**实现**:
1. 新建 `monitor.go`：
   - `GET /api/v1/monitor/strategies/:id/dashboard` — 返回策略监控面板数据（今日收益/偏离/滑点/因子健康/回撤/持仓）
   - `GET /api/v1/monitor/strategies/:id/alerts` — 返回告警历史列表（分页）
   - `GET /api/v1/monitor/strategies/:id/drift` — 返回偏离度时间序列（供图表）
2. WebSocket 推送：MonitorEngine 每次计算后通过 `WSHub.Broadcast("monitor:{strategy_id}", ...)` 推送最新指标
3. 在 `router.go` 注册端点
4. `go build ./... && go test ./internal/api/handler/ -run TestMonitor -v -count=1`
5. Commit: `feat: monitor API + WebSocket push — dashboard data + alert history`

---

### Task 5.4 — Frontend Monitor Dashboard（Frontend）

**文件**: 新建 `frontend/app/monitor/` 目录下的页面

**实现**:
1. 新建 `frontend/app/monitor/page.tsx`：
   - 仪表盘卡片网格（2×3）：
     - 当日收益（绿色正/红色负，大号字体）
     - 累计偏离（🟢/🟡 颜色指示器）
     - 因子健康度（IC 数值 + 趋势箭头）
     - 滑点统计（百分比）
     - 最大回撤（当前 vs 历史，🔴 突破时闪烁）
     - 持仓数（N/M 已占用）
   - 卡片使用 `react-countup` 或 CSS animation 动画效果
2. 告警列表区：最近告警时间线（🟡/🟠/🔴 图标 + 时间 + 消息），可展开查看详情
3. WebSocket 连接监听 `monitor:{strategy_id}` channel，实时刷新卡片数据
4. 策略选择器：下拉切换不同的实盘策略
5. `npx next build` 验证
6. Commit: `feat: monitor dashboard — real-time cards + alert timeline via WebSocket`

---

## 执行顺序

```
Wave 1（模板市场）──────► Wave 2（信号推送）──────► Wave 3（多轮精炼）
                                    └──────────────► Wave 4（竞技场）
                                                         └──────► Wave 5（监控）
```

- Wave 1 和 Wave 2 **可并行开始**（无相互依赖）
- Wave 3、4、5 **顺序执行**（依赖前面的基础设施 + 需要注意力集中）

---

## Task 数量汇总

| Wave | 功能 | 任务数 | Go | Python | Frontend | 预估工作量 |
|------|------|:---:|:---:|:---:|:---:|:---:|
| Wave 1 | 策略模板市场 | 3 | 1 | 0 | 2 | 中 |
| Wave 2 | 因子信号推送 | 4 | 1 | 2 | 1 | 中 |
| Wave 3 | 多轮策略精炼 | 3 | 1 | 1 | 1 | 中高 |
| Wave 4 | 回测竞技场 | 3 | 2 | 0 | 1 | 中 |
| Wave 5 | 实盘监控 | 4 | 3 | 0 | 1 | 中高 |
| **总计** | **5 个功能** | **17** | **8** | **3** | **6** | — |
