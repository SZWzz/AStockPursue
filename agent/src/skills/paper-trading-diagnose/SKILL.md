---
name: paper-trading-diagnose
description: 模拟盘问题诊断 — 排查策略无信号、不交易、异常亏损、数据源问题、风控频繁触发等常见故障，定位根因并给出修复建议。
category: flow
---

# 模拟盘问题诊断 (Paper Trading Diagnosis)

## 诊断流程

```
用户报告问题
  ↓
1. 检查运行状态 → running? stopped? error?
  ↓
2. 查看持仓 (positions) → 有预期持仓吗？
  ↓
3. 查看成交 (trades) → 最近有交易吗？exit_reason 是什么？
  ↓
4. 查看信号日志 (signal log) → 策略产生了信号吗？
  ↓
5. 查看权益曲线 (equity) → 亏损模式是什么？
  ↓
6. 查看数据源 (data_source) → 实际用的 loader 对吗？
  ↓
定位根因 → 给出修复建议
```

## 常见问题分类

### A. 策略不产生信号

**症状**：signal log 为空，没有新交易

**排查步骤**：
1. 检查策略代码：`generate()` 方法是否返回了非零权重？是否因为市场条件不满足全部返回 0？
2. 查看当前 bar 数据：`GET /runs/{run_id}/bars?limit=5` 看最近几根 bar 的 OHLCV，确认数据是否正常（没有全 0 或 NaN）
3. 检查数据源：运行详情中的 `data_source` 字段——如果 loader 不可用，可能返回空数据
4. 确认 `interval` 设置：如果是日线（1D），每天只有一个 bar，非交易日不会产生信号

**修复建议**：
- 在 `generate()` 中添加日志/print 确认数据到达
- 降低策略条件的阈值
- 检查 `codes` 是否包含正确的标的代码格式（如 `000001.SZ` 而非 `000001`）

### B. 策略有信号但不成交

**症状**：signal log 有记录，但 positions 一直为空

**排查步骤**：
1. 检查风控参数：`max_daily_loss_pct` 是否过小导致日内熔断？
2. 检查 `max_position_pct`：信号权重 × 初始资金 ÷ 当前价格 < 最小交易单位？
3. A 股特别注意：T+1 限制、涨跌停（开盘即封板无法买入）
4. 查看 `trades` 中 `exit_reason`：如果全是 `stop_loss` 或 `trailing_stop`，可能是止损太紧

**修复建议**：
- 调大风控参数（止损/日内亏损限制）
- 降低 `max_position_pct` 下限
- 确认初始资金足够覆盖交易成本（A 股每笔最低 5 元佣金）

### C. 异常亏损

**症状**：equity 曲线持续下降，回撤超过预期

**排查步骤**：
1. 看 `trades` 中的每笔 pnl：是连续小亏（手续费侵蚀）还是单笔大亏（止损未触发）？
2. 检查 `use_intraday_stop`：如果为 `false`，止损只在收盘价检测，可能错过 bar 内的大幅波动
3. 查看 `exit_reason`：`stop_loss` / `trailing_stop` / `take_profit` 触发频率是否异常？
4. 对比回测结果：同一策略回测是否也亏损？如果回测盈利但模拟盘亏损 → 数据源不一致
5. 滑点：模拟盘使用固定滑点模型，小盘股实际滑点可能更大

**修复建议**：
- 启用 `use_intraday_stop: true`
- 放宽止损阈值
- 如果是手续费侵蚀 → 降低交易频率或提高单笔规模

### D. 数据源问题

**症状**：bar 数据为空、数据延迟、价格异常

**排查步骤**：
1. 检查 `data_source`：运行详情 header 显示的 loader 名称
2. 对比回测数据源：回测用的 loader（通过 `config.json` → `source` 指定）和模拟盘可能不同（fallback 链）
3. A 股：`tushare` 需要 token，可能 fallback 到 `akshare`（免费但数据质量低）
4. 查看 bar 时间戳：是否有长时间未更新的情况？

**修复建议**：
- 配置对应的 API token（Settings → 数据源配置）
- 如果免费数据源不可靠，切换市场或使用其他标的

### E. 风控频繁触发

**症状**：trades 中大量 `exit_reason = "stop_loss"`，胜率低

**排查步骤**：
1. 检查 `stop_loss_pct` 设置：A 股日波动 2-3%，止损设 2% 以下容易频繁触发
2. 检查 `trailing_stop_pct`：追迹止损太紧会过早止盈
3. 检查 `max_daily_loss_pct`：触发后当日不再开新仓

**修复建议**：
- A 股止损建议 ≥ 5%
- 追迹止损建议 ≥ 3%
- 日内亏损限制建议 ≥ 3%

### F. 策略运行中报错停止

**症状**：status 变为 `error`

**排查步骤**：
1. 查看 `GET /runs/{run_id}` 的 `status` 和可能的 `reason` 字段
2. 检查服务端日志（模拟盘 scheduler 日志）
3. 常见原因：策略代码有运行时错误（`generate()` 抛异常）、数据源不可用连续失败

**修复建议**：
- 先在回测中验证策略代码无运行时错误
- 检查数据源 API 是否正常

## 诊断输出格式

诊断完成后，以以下格式输出：

```
## 诊断结果

**问题类型**：A-F 之一
**严重程度**：严重 / 一般 / 提示

**根因**：一句话描述

**证据**：
- 列出具体数据（如 trades 最近 3 笔、positions 状态、signal log）

**修复建议**：
1. 具体操作 1
2. 具体操作 2
```
