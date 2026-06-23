# 后续功能改进方案

> **Date**: 2026-06-23  
> **Status**: 设计完成，待实施

---

## 1. 策略回测竞技场

### 目标
用户提交策略跑在统一评测集上，按夏普/回撤排名，每周结算榜单。

### 技术方案
```
用户提交策略 → Redis 评测队列 → Go 回测引擎 → 结果写入 PG
                                        ↓
                              标准化评测集（HS300/2022-2024/初始100万）
                                        ↓
                              首页排行榜 Top 10（夏普/年化/最大回撤/胜率）
```

### 涉及文件
| 层 | 文件 |
|----|------|
| Go | `internal/api/handler/arena.go` — 提交/榜单 API |
| Go | `internal/engine/arena.go` — 标准化评测 runner |
| DB | migrations 新表 `arena_submissions` / `arena_rankings` |
| 前端 | `app/arena/` — 榜单页 + 提交页 |
| 前端 | `app/page.tsx` — 首页嵌入榜单卡片 |

### 评测集配置
```yaml
universe: HS300
start: 2022-01-01
end: 2024-12-31
capital: 1,000,000
commission: 0.0003
slippage: 0.001
benchmark: 000300.SH
```

### 防作弊
- 限制每人每周 3 次提交
- 策略代码 AST 白名单检查（复用现有 sandbox）
- 泄露未来数据的策略自动标记无效

---

## 2. 因子信号推送

### 目标
每天定时跑因子计算，筛选当日 IC 最强 Top 5 因子，生成信号简报推送到 Telegram/微信/邮件。

### 技术方案
```
Scheduler 定时任务（每日 15:30）
  → Python 因子服务（gp_engine/alpha_zoo）
  → 计算当日所有因子值 + 截面 IC
  → 筛选 Top 5 因子 + 对应买卖信号
  → 生成简报（Markdown）
  → 推送到 Telegram Bot / 企业微信 Webhook / 邮件
```

### 涉及文件
| 层 | 文件 |
|----|------|
| Python | `src/services/signal_brief.py` — 信号生成 + 简报渲染 |
| Python | `src/services/notify.py` — 推送渠道适配（Telegram/WeChat/Email） |
| Go | `internal/api/handler/signals.go` — 信号订阅管理 API |
| DB | `user_settings` 表新增 `signal_push_enabled` + `push_channels` |
| 前端 | `app/settings/` — 推送渠道配置页 |

### 简报模板
```markdown
📊 AStockPursue 每日信号 — 2024-06-23

今日最强因子（截面 IC Top 5）：
1. momentum_20d   IC=0.042  看多: 600519.SH, 000858.SZ
2. reversal_5d    IC=-0.038  看空: 601318.SH
3. volume_surge   IC=0.035  看多: 300750.SZ, 002594.SZ
...
```

### 推送渠道配置
```json
{
  "telegram": { "bot_token": "...", "chat_id": "..." },
  "wechat_work": { "webhook_url": "..." },
  "email": { "smtp_host": "...", "to": "..." }
}
```

---

## 3. 多轮策略精炼

### 目标
NL→策略从单轮对话变为多轮精炼：AI 反问 → 用户澄清 → 生成 → 回测 → 展示结果 → 追问调整。

### 技术方案
```
用户描述策略意图
  → Swarm Agent 分析意图 + 反问缺失参数
  → 用户补充（标的池/频率/风控偏好）
  → Agent 生成策略代码（复用 strategy_nodes）
  → 自动回测（复用 Go backtest pipeline）
  → 展示结果（夏普/回撤/权益曲线）
  → Agent 解读结果 + 追问"需要调整吗？"
  → 用户反馈 → 迭代优化
```

### 涉及文件
| 层 | 文件 |
|----|------|
| Python | `src/agent/strategy_advisor.py` — 多轮对话 Agent |
| Python | `src/workflow/nodes/strategy_refine.py` — 策略迭代节点 |
| Go | `internal/api/handler/agent.go` — 对话 API |
| 前端 | `app/agent/` — 对话界面增强（回测结果嵌入） |

### 对话示例
```
用户: 我想做一个低吸高抛的策略
AI: 我理解你想做均值回归。日线还是小时线？持仓几只？止损多少？
用户: 日线，最多5只，止损5%
AI: 生成策略中... [回测完成] 夏普1.2，最大回撤15%，胜率58%。需要调整参数吗？
用户: 回撤太大了，加个指数过滤
AI: 已添加沪深300指数过滤。重新回测... 夏普1.5，最大回撤11%。有改善，还需要调整吗？
```

---

## 4. 实盘监控仪表盘

### 目标
策略上实盘后，实时监控偏离度、滑点、因子衰减，异常自动告警。

### 技术方案
```
LiveTradingRunner 每次 on_bar() 后计算偏离指标
  → 写入监控表（strategy_monitor）
  → 仪表盘实时刷新（WebSocket 推送）

告警规则:
- 实盘收益偏离回测预期 > 20% → 🟡 警告
- 滑点 > 预期 2x → 🟡 警告
- 因子截面 IC 连续 5 天 < 0.01 → 🟠 严重
- 最大回撤突破历史最大 → 🔴 紧急
```

### 涉及文件
| 层 | 文件 |
|----|------|
| Go | `internal/engine/monitor.go` — 偏离度计算 |
| Go | `internal/api/handler/monitor.go` — 监控数据 API |
| Go | `internal/notify/alert.go` — 告警推送 |
| DB | 新表 `strategy_drift` / `factor_decay` / `slippage_stats` |
| 前端 | `app/monitor/` — 监控面板（仪表盘式卡片 + 告警列表） |

### 监控面板
```
┌─────────────┬─────────────┬─────────────┐
│ 当日收益     │ 累计偏离     │ 因子健康度   │
│ +2.3%       │ -1.8% 🟡   │ 0.035 ✅    │
├─────────────┼─────────────┼─────────────┤
│ 滑点统计     │ 最大回撤     │ 持仓数       │
│ 0.12% ✅    │ -15% ✅    │ 5/5         │
└─────────────┴─────────────┴─────────────┘

最近告警:
🟡 14:30 偏离度扩大至 -1.8%
🟠 11:00 因子 IC 连续 5 日下降
```

---

## 6. 社区策略模板市场

### 目标
10 个预置策略模板 + 参数面板 + 一键发布到市场，让不会写代码的用户也能参与。

### 技术方案
```
策略模板库（YAML 定义） → 前端参数面板 → 调参回测 → 一键发布
    ↓
模板定义:                                 发布:
- 双均线交叉 (MA Crossover)               - 策略卡片（自动生成）
- 海龟交易 (Turtle Trading)                - 参数快照 + 回测结果
- 网格交易 (Grid Trading)                  - 评分/评论/收藏
- 动量突破 (Momentum Breakout)
- 均值回归 (Mean Reversion)
- RSI 超买超卖
- MACD 金叉死叉
- 布林带突破
- 成交量突破
- 多因子选股
```

### 模板定义格式
```yaml
id: ma_crossover
name: 双均线交叉
category: trend
params:
  fast_period: { type: int, default: 5, min: 2, max: 60 }
  slow_period: { type: int, default: 20, min: 5, max: 200 }
  stop_loss_pct: { type: float, default: 0.05, min: 0.01, max: 0.2 }
code_template: |
  fast_ma = close.rolling({fast_period}).mean()
  slow_ma = close.rolling({slow_period}).mean()
  signal = (fast_ma > slow_ma) & (fast_ma.shift(1) <= slow_ma.shift(1))
```

### 涉及文件
| 层 | 文件 |
|----|------|
| Go | `internal/api/handler/marketplace.go` — 策略发布/浏览/安装 API |
| DB | 新表 `strategy_marketplace` — 策略卡片（参数+结果+评分） |
| Python | `src/lab/templates/` — 10 个 YAML 模板定义 |
| 前端 | `app/marketplace/` — 策略浏览 + 参数面板 + 一键安装 |
| 前端 | `components/financial/StrategyCard.tsx` — 策略卡片组件 |

---

## 实施优先级

| 顺序 | 功能 | 技术难度 | 业务价值 | 依赖 |
|------|------|:---:|:---:|------|
| 1 | 数据预装包 | ★★☆ | ★★★★★ | ✅ 已完成 |
| 2 | 策略模板市场 | ★★★ | ★★★★ | 无 |
| 3 | 因子信号推送 | ★★☆ | ★★★★★ | Scheduler + 通知系统 |
| 4 | 多轮策略精炼 | ★★★★ | ★★★★ | Swarm Agent |
| 5 | 回测竞技场 | ★★★ | ★★★★★ | 评测引擎 |
| 6 | 实盘监控 | ★★★★ | ★★★ | 实盘桥接 |
