# AStockPursue vs NautilusTrader — 回测系统对比分析

> 对比日期：2026-06-07  
> AStockPursue 版本：v2026.6.x  
> NautilusTrader 版本：develop 分支

---

## 目录

1. [架构与设计哲学](#1-架构与设计哲学)
2. [数据加载与处理](#2-数据加载与处理)
3. [订单执行模拟](#3-订单执行模拟)
4. [市场/交易所模拟](#4-市场交易所模拟)
5. [风险管理](#5-风险管理)
6. [策略集成](#6-策略集成)
7. [绩效指标与报告](#7-绩效指标与报告)
8. [前视偏差防护](#8-前视偏差防护)
9. [性能与健壮性](#9-性能与健壮性)
10. [各自独特优势](#10-各自独特优势)
11. [总结](#11-总结)

---

## 1. 架构与设计哲学

| 维度 | AStockPursue | NautilusTrader |
|---|---|---|
| **语言** | 纯 Python | Rust 核心 + Python 绑定 |
| **范式** | Bar-by-bar 循环，预计算权重或实时模拟 | 事件驱动，模拟交易所 + 撮合引擎 |
| **统一管线** | `TradingEngine.on_bar()` 同时用于回测和实盘 | 策略/Actor 通过同一内核在回测和实盘中运行，零代码切换 |
| **状态模型** | 简单 dataclass（`Position`、`TradeRecord`、`EquitySnapshot`），由 market engine 持有 | 完整账户模型：`Account`、`Position`、`Order`，由 `Cache`/`Portfolio` 管理 |
| **API 层级** | 单一 API（config dict + loader + signal_engine + market_engine） | 两级：**低级** `BacktestEngine` 直接操控，**高级** `BacktestNode` 配置驱动 |
| **扩展模型** | Market engine 继承 `BaseEngine`，覆写市场规则方法 | `SimulatedExchange` + `SimulationModule` + `FillModel` + `LatencyModel` |

### 核心设计差异

**AStockPursue** 的回测驱动类 [BacktestDriver](AStockPursue/backend/src/trading/backtest_driver.py:28) 提供两种模式：

- **快速模式（默认）**：提前通过 `signal_engine.generate()` 计算全部权重，然后逐根 bar 喂给 `TradingEngine.on_bar()`，传入 `precomputed_weights`
- **模拟模式**：逐根 bar 走过完整信号管线（信号生成 → 风险检查 → 执行），与实盘行为一致

两种模式共享同一个 [TradingEngine](AStockPursue/backend/src/trading/engine.py:58)，其核心管线为：

```
on_bar(bar, ts)
  ├─ 0a. 跳空检测（隔夜止损/移动止损/止盈）
  ├─ 0b. 停牌检测（收盘价不变 + 成交量为零 ≥2 根 bar → 强制平仓）
  ├─ 0.5 市场钩子（资金费率、强制平仓检查）
  ├─ 1. SignalAdapter → 目标权重（tick 模式或 batch generate()）
  ├─ 1.5 OptimizerAdapter → 调整权重（可选）
  ├─ 2. RiskPipeline → 强制退出（止损/移动止损/止盈）
  ├─ 3. 信号处理 → 开仓/平仓
  └─ 4. 记录权益快照
```

**NautilusTrader** 的 [BacktestEngine](nautilus_trader-develop/crates/backtest/src/engine.rs:85) 是完整的 Rust 事件驱动引擎，每个数据点执行三个阶段：

```
每个数据点 (ts=T)
  ├─ 阶段1: 交易所处理数据
  │   └─ SimulatedExchange 更新订单簿 → MatchingEngine 撮合已有订单
  ├─ 阶段2: 策略接收数据
  │   └─ DataEngine 分发数据 → Strategy.on_bar/on_quote_tick/on_trade_tick
  └─ 阶段3: 结算场所
      └─ 排空命令队列 → 撮合新订单 → 重复直到无待处理命令
```

---

## 2. 数据加载与处理

### AStockPursue

**三层数据访问架构**：

```
DataStore (data_store.py)
  ├─ 第1层: PostgreSQL 缓存
  ├─ 第2层: Parquet 本地存储
  └─ 第3层: Loader API（实时获取）
```

**A 股 8 源回退链**：`mootdx → tushare → eastmoney → tencent → futu → baidu → twelvedata → akshare`

- 数据通过 `loader.fetch()` 一次性加载为 `{code: DataFrame}` 映射
- 支持 `extra_fields`（基本面数据）增强
- 内置退市检测、停牌检测（≥2 根平盘+零量 bar）、交易时段过滤（期货夜盘）
- 前向填充限制 5-10 根 bar（跨市场场景自动扩展）

### NautilusTrader

**Parquet 数据目录系统**（`ParquetDataCatalog`）：

- 高效的列式存储，支持时间范围查询
- **流式数据**支持：生成器模式的批量加载，可处理超过内存大小的数据集
- **多场所、多品种**数据，严格按 `ts_init` 时间戳排序
- **数据类型层次结构**：

```
L3 订单簿(逐笔) → L2 订单簿(价位聚合) → L1 报价(最优价) → 逐笔成交 → Bar
```

- Bar 数据 OHLC → 4 个顺序价格点，支持 **自适应高低价排序**（~75-85% 准确率预测价格路径）
- **精度校验**：所有价格/数量与 instrument `price_precision`/`size_precision` 比对，不匹配立即 `RuntimeError`

### 关键差异

| 方面 | AStockPursue | NautilusTrader |
|---|---|---|
| 数据粒度 | 以 Bar 为中心（日线/分钟线） | 以订单簿为中心，Bar 为最低精度回退 |
| 内存策略 | 全量加载到 pandas DataFrame | 支持流式/分块加载 |
| A 股适配 | 8 源回退、T+1、涨跌停、印花税 | 需自行适配 |
| 时间戳处理 | pandas DatetimeIndex | UnixNanos，严格区分 `ts_event`/`ts_init` |
| 数据校验 | 基本的空值/退市检测 | 精度级别的严格校验 |

---

## 3. 订单执行模拟

### AStockPursue

- **快速模式**：预计算所有权重 → 逐根 bar 执行（`precomputed_weights` 传入）
- **模拟模式**：逐根 bar 完整信号管线（匹配实盘行为）
- **次根 bar 开盘执行**：使用 `open` 价格在信号生成的下一根 bar 执行（通过 `_align()` 中的 `shift(1)` 实现）
- 简单的佣金/滑点模型：每个 market engine 覆写 `apply_slippage()`、`calc_commission()`
- **无订单簿模拟** — 从权重直接计算仓位规模
- **无部分成交、无订单队列、无延迟模型**

执行流程（快速模式）：

```
signal_engine.generate(truncated_data) → 权重
    ↓
_align() + optimizer → 目标持仓矩阵
    ↓
逐 bar 循环: engine.on_bar(bar, ts, precomputed_weights=weights)
    ↓
TradingEngine._process_signals() → 开仓/平仓
```

### NautilusTrader

**完整的订单簿模拟**：即使使用 Bar 数据，也维护内部 L1 订单簿。

**9 种订单类型**：`MARKET`、`LIMIT`、`STOP_MARKET`、`STOP_LIMIT`、`MARKET_TO_LIMIT`、`MARKET_IF_TOUCHED`、`LIMIT_IF_TOUCHED`、`TRAILING_STOP_MARKET`、`TRAILING_STOP_LIMIT`

**撮合引擎**：每 tick 三阶段循环

**流动性消耗追踪**（可选）：防止同一订单簿流动性被重复成交

**11 种成交模型**：

| 模型 | 描述 |
|---|---|
| `FillModel` | 基础概率模型 |
| `BestPriceFillModel` | 最优价格无限流动性 |
| `OneTickSlippageFillModel` | 强制 1 tick 滑点 |
| `TwoTierFillModel` | 最优价 10 张 + 其余滑 1 tick |
| `ThreeTierFillModel` | 50/30/20 张三层分布 |
| `ProbabilisticFillModel` | 50% 最优价 / 50% 滑 1 tick |
| `SizeAwareFillModel` | 按订单规模差异化执行 |
| `LimitOrderPartialFillModel` | 每次最多 5 张成交 |
| `MarketHoursFillModel` | 低流动性时段扩大点差 |
| `VolumeSensitiveFillModel` | 基于近期成交量模拟深度 |
| `CompetitionAwareFillModel` | 仅部分可见流动性可用 |

**延迟模型**（`LatencyModel`）：可配置的基础延迟、插入延迟、随机抖动

**队列位置追踪**：模拟限价单在队列中的位置，根据成交 tick 递减前方排队量

**Bar 数据止损成交逻辑**：
- **跳空场景**（开盘价越过触发价）：在开盘价成交
- **穿越场景**（bar 内高低价穿越触发价）：在触发价成交

**价格保护**：交易所级别的市价单保护边界

### 关键差异

| 方面 | AStockPursue | NautilusTrader |
|---|---|---|
| 成交模拟 | 权重 → 仓位（无订单概念） | 订单簿撮合 + 多种成交模型 |
| 订单类型 | 无（直接 weight → direction） | 9 种完整订单类型 |
| 滑点 | 简单价格偏移 | 11 种成交模型 + 延迟模型 |
| 部分成交 | 不支持 | 完整支持 |
| 队列模拟 | 无 | 队列位置追踪 + 流动性消耗 |
| 成交确定性 | 确定性 | 可配置随机种子 |

---

## 4. 市场/交易所模拟

### AStockPursue

**Market Engine 继承体系**（[engines/](AStockPursue/backend/backtest/engines/)）：

```
BaseEngine (base.py)
  ├─ ChinaAEngine (china_a.py)         — A 股：T+1、涨跌停、印花税
  ├─ GlobalEquityEngine                — 美股/港股
  ├─ CryptoEngine (crypto.py)          — 永续合约：资金费率、强制平仓
  ├─ ForexEngine (forex.py)            — 外汇现货/CFD
  ├─ FuturesBase (futures_base.py)     — 合约乘数感知
  │   ├─ ChinaFuturesEngine            — 中金所/上期所/大商所/郑商所/能源中心/广期所
  │   └─ GlobalFuturesEngine           — CME/ICE/Eurex
  ├─ OptionsPortfolioEngine            — 欧式/美式 Black-Scholes
  └─ CompositeEngine (composite.py)    — 跨市场共享资金池
```

每个 engine 覆写方法：`can_execute()`、`round_size()`、`calc_commission()`、`apply_slippage()`、`_calc_margin()`、`_calc_pnl()`

### NautilusTrader

**`SimulatedExchange`**（[exchange.rs](nautilus_trader-develop/crates/backtest/src/exchange.rs)）：

- 每个场所独立的撮合引擎
- **账户类型**：`CASH`、`MARGIN`、`BETTING`
- **OMS 类型**：`NETTING`（净额）、`HEDGING`（对冲）
- **保证金模型**：`StandardMarginModel`（固定%）、`LeveragedMarginModel`（杠杆减免）、自定义
- **订单簿类型**：`L1_MBP`（最优价）、`L2_MBP`（价位聚合）、`L3_MBO`（逐笔委托）
- **模拟模块**：可扩展的场所行为（如 FX 展期利息）
- **合约到期自动处理**
- **资金费率结算**：在 `FundingRateUpdate` 边界结算

### 关键差异

AStockPursue 将市场规则嵌入轻量级 engine 方法；NautilusTrader 维护完整的模拟交易所。AStockPursue 对中国市场规则有更深入的覆盖（T+1、涨跌停、印花税、平今仓），而 NautilusTrader 拥有更通用的交易所基础设施。

---

## 5. 风险管理

### AStockPursue

**`RiskPipeline`**（[risk_pipeline.py](AStockPursue/backend/src/trading/risk_pipeline.py:40)）作为独立于策略的可组合中间件层：

```
优先级（高→低）：
  1. 止损（stop_loss_pct，默认 -5%）
  2. 移动止损（trailing_stop_pct，默认 0%/关闭）
  3. 止盈（take_profit_pct，默认 +10%）
```

完整功能列表：

| 功能 | 实现 |
|---|---|
| **止损** | 基于收盘价 + 可选 bar 内最高/最低价（更精确） |
| **移动止损** | 追踪最高价，从高点回撤触发 |
| **止盈** | 固定百分比止盈 |
| **每日亏损熔断** | 动态计算（当前权益 × 百分比），触发后阻止新开仓 |
| **单仓位上限** | 名义价值 ≤ 权益 × 百分比 |
| **跳空检测** | 隔夜开盘价越过止损/移动止损/止盈 → 开盘即平 |
| **日内止损** | 通过 bar 高/低价检测，比收盘价检查更精确 |

### NautilusTrader

风险管理在**策略层面**实现——策略通过订单管理自行控制风险：

- **交易所级别**价格保护（可配置保护点）
- **OMS 类型**头寸限制（`NETTING` 模式阻止反向持仓）
- 无与 AStockPursue 的 `RiskPipeline` 等价的独立风险层

### 关键差异

AStockPursue 拥有专用的、可配置的风险管理层，独立于策略逻辑运行。NautilusTrader 将风险管理推至策略或交易所级别——更灵活但需要更多策略代码。

---

## 6. 策略集成

### AStockPursue

**`SignalAdapter`**（[signal_adapter.py](AStockPursue/backend/src/trading/signal_adapter.py:31)）自动检测策略能力：

- **Tick 模式**（实现 `TickHandler` 协议）：`on_init()` + `on_bar()`，逐 bar O(n) 信号生成
- **Batch 模式**（回退）：`SignalEngine.generate(data_map)` 从完整历史计算
- **前视偏差防护**：策略永远看不到当前 bar — `_generate_signals()` 在 `_record_bars()` 之前运行
- **OptimizerAdapter**：在线滚动窗口组合优化（风险平价、均值方差、Black-Litterman、最大分散化、等波动率）
- 策略是简单的 Python 模块，包含 `SignalEngine` 类

策略只需实现：

```python
class SignalEngine:
    def generate(self, data_map: dict[str, pd.DataFrame]) -> dict[str, pd.Series]:
        """返回 {code: signal_series}"""
        ...
```

### NautilusTrader

**`Strategy` 基类**，完整的生命周期回调：

```python
class MyStrategy(Strategy):
    def on_start(self): ...
    def on_stop(self): ...
    def on_bar(self, bar: Bar): ...
    def on_quote_tick(self, tick: QuoteTick): ...
    def on_trade_tick(self, tick: TradeTick): ...
    def on_order_book(self, book: OrderBook): ...
    def on_order_filled(self, event: OrderFilled): ...
    def on_order_rejected(self, event: OrderRejected): ...
```

- **Actor 模型**：独立的 `Actor` 组件处理非交易关注点
- **执行算法**：可组合的 `ExecutionAlgorithm` 用于订单拆分
- **`ImportableStrategyConfig`**：策略通过 Python 导入路径加载，带类型化配置对象
- **`BacktestNode`**：编排多个 `BacktestRunConfig` 对象，支持批量运行/参数扫描
- 策略在回测和实盘中是**同一个类**——零代码更改

### 关键差异

NautilusTrader 拥有更丰富的组件模型（策略、Actor、执行算法），具有完整的生命周期回调和事件驱动架构。AStockPursue 的 signal adapter 更简单，但在策略层面集成了组合优化器。

---

## 7. 绩效指标与报告

### AStockPursue

**`calc_metrics()`**（[metrics.py](AStockPursue/backend/backtest/metrics.py)）：

- 年化处理：按数据源和 bar 周期自动选择交易日数（A 股 252 天、加密货币 365 天、分钟级按日折算）
- 标准指标：年化收益率、波动率、Sharpe 比率、最大回撤、Calmar 比率、胜率、盈亏比
- **基准对比**：自动解析基准（`resolve_benchmark()`）或显式指定 ticker → 超额收益、信息比率
- **按品种统计**：`by_symbol_stats()`
- **按退出原因统计**：`by_exit_reason_stats()`
- **验证框架**：可配置的权益曲线属性验证
- **输出物**：`equity.csv`、`positions.csv`、`trades.csv`、`metrics.csv`、`ohlcv_{code}.csv`
- **Run Card**：HTML 格式的回测报告

### NautilusTrader

- **`PortfolioAnalyzer`**：通过 `nautilus_analysis` crate（Rust）进行综合统计分析
- **`BacktestResult`**：结构化结果，包含 `stats_pnls`、`stats_returns`、`stats_general`、`summary`
- **Tearsheet 可视化**：基于 Streamlit 的报告
- **按币种 P&L 分解**
- 导出为 Parquet/JSON 用于外部分析

### 关键差异

AStockPursue 提供 CSV 物 + HTML run card，直观简洁；NautilusTrader 拥有专用的 Rust 分析器和 Streamlit tearsheet。AStockPursue 的基准对比和按退出原因统计在实际策略审核中非常实用。

---

## 8. 前视偏差防护

### AStockPursue

在 `TradingEngine.on_bar()` 中记录了明确的操作顺序约束（引用缺陷修复编号 P0-1、P1-1、P1-2）：

1. `_generate_signals()` 在 `_record_bars()` **之前**运行——策略只能看到 data[0..T-1]，永远看不到当前 bar
2. `equity_for_sizing` 在 `_check_risk_exits()` 更新 `_last_bar_prices` **之前**缓存——仓位计算使用昨日收盘价，而非今日收盘价
3. 快速模式下的渐进式信号生成：每根 bar 的 `generate()` 仅看到 `data.loc[:ts]`
4. 停牌检测正确阻止策略对停牌股票生成交易信号
5. 使用 `pd.infer_freq()` 而非 `Timedelta(days=1)` 推断 bar 时间戳（P1-01 修复）

### NautilusTrader

- Bar 数据的 `ts_init` 必须表示 bar **收盘时间**（而非开盘时间）
- `ts_init_delta` 参数将开盘时间戳数据偏移至收盘
- 数据排序强制执行——检测到未排序数据时引擎抛出 `RuntimeError`
- `BarDataWrangler` 在加载过程中验证时间戳
- 三阶段循环确保数据处理在策略接收之前完成
- 明确的文档："A bar's `ts_init` is its close timestamp, so the open price is only known once the bar arrives. Filling at that open from a signal generated on the prior bar would require look-ahead."

### 关键差异

两者都非常重视前视偏差防护。AStockPursue 在代码级别记录了明确的操作顺序约束和缺陷修复引用。NautilusTrader 在数据层面通过时间戳约定和排序验证来强制执行。

---

## 9. 性能与健壮性

| 方面 | AStockPursue | NautilusTrader |
|---|---|---|
| **速度** | Python — 快速模式预计算权重，bar 循环约 10k bars/秒 | Rust 核心 — 事件驱动循环，编译优化 |
| **内存** | 全量加载到 pandas DataFrame | 流式/分块模式可用于大数据集 |
| **重置/重跑** | 需新建 `BacktestDriver()` 实例 | `engine.reset()` 保留数据/品种；`BacktestNode` 每次创建新引擎 |
| **错误处理** | 每个品种捕获特定异常类型（ValueError, KeyError 等），不用裸 `except` | `shutdown_on_error` 配置 — Rust error log 触发优雅关闭，返回部分结果 |
| **可复现性** | 确定性（核心循环无随机性） | 确定性 `TradeId`，PRNG 使用固定 `random_seed` |
| **代码规模** | ~15 个核心 trading 文件 | 多个 Rust crate + Python 绑定 |
| **测试覆盖** | pytest 单元测试 | 单元测试 + 集成测试 + 验收测试 + 内存泄漏测试 + 性能测试 |

---

## 10. 各自独特优势

### AStockPursue 的独特优势

1. **深度 A 股适配**：T+1、涨跌停、印花税（万三）、8 源数据回退、停牌/退市检测，这些在 NautilusTrader 中需要大量自定义开发
2. **双模式回测**：快速模式（预计算权重，秒级完成）用于快速迭代；模拟模式（完整管线）用于验证
3. **内置组合优化器**：风险平价、均值方差、Black-Litterman、最大分散化、等波动率——开箱即用
4. **集成风险管线**：独立风险层，支持日内止损检测、跳空检测、每日亏损熔断
5. **因子挖掘集成**：GP 进化、表达式树、FDR 校正——回测是因子发现管线的验证步骤
6. **更紧凑的代码库**：~15 个核心交易文件，比 NautilusTrader 更容易理解和修改
7. **Run Card 报告**：自动化的 HTML 回测报告，包含策略路径、数据源、配置和完整指标
8. **Session 过滤**：自动过滤非交易时段（期货夜盘），支持跨交易所 session 感知

### NautilusTrader 的独特优势

1. **真正的事件驱动架构**：回测和实盘使用完全相同的执行内核——策略代码零修改
2. **完整订单簿模拟**：L2/L3 订单簿数据 + 真实撮合引擎 + 队列位置追踪 + 流动性消耗
3. **11 种成交模型 + 延迟模型**：机构级的执行模拟
4. **9 种订单类型**：完整的交易所订单语义
5. **多场所多资产**：同时在多个模拟交易所交易
6. **Rust 性能**：逐笔级别回测有数量级的性能优势
7. **流式数据**：可回测超大内存数据集（自动批处理、手动分块、生成器模式）
8. **成熟的工业生产系统**：NAUTEC 的机构客户使用，全面的测试套件
9. **可视化**：Streamlit tearsheet + Jupyter notebook 集成
10. **可扩展性**：自定义成交模型、保证金模型、模拟模块、执行算法

---

## 11. 总结

### 适用场景建议

| 场景 | 推荐 |
|---|---|
| A 股日频/周频组合策略 | **AStockPursue** — 快速模式 + 优化器管线更高效 |
| A 股期货日内策略 | **AStockPursue** — 中国期货市场规则支持更完善 |
| 加密货币永续合约 | 两者均可 — AStockPursue 更简单，NautilusTrader 更精确 |
| 美股/港股多资产组合 | **NautilusTrader** — 多场所多资产架构天然支持 |
| L2/L3 订单簿高频策略 | **NautilusTrader** — 没有订单簿模拟无法回测 |
| 需要精确成交建模的策略 | **NautilusTrader** — 成交模型 + 延迟模型 + 队列追踪 |
| 因子挖掘与验证 | **AStockPursue** — 内置 GP 进化、表达式树、FDR 校正 |
| 参数扫描/优化 | 两者均可 — NautilusTrader 的 `BacktestNode` 更结构化 |
| 从回测到实盘的无缝过渡 | **NautilusTrader** — 同一内核，零代码切换 |
| 快速原型验证 | **AStockPursue** — 代码量更少，上手更快 |

### 核心差异一句话

- **AStockPursue**：为中国市场优化的实用主义回测系统，从权重到仓位直接执行，集成组合优化和风险管理，代码紧凑易改
- **NautilusTrader**：机构级事件驱动交易平台，回测与实盘共享同一执行内核，订单簿级撮合模拟，Rust 性能，多场所架构

### 互补性

两者并非互斥。可以设想的工作流：

1. 使用 **AStockPursue** 进行因子挖掘和快速策略原型——利用其 GP 进化、组合优化器和 A 股适配
2. 将成熟的策略移植到 **NautilusTrader** 进行更精确的订单级回测和实盘部署——利用其撮合引擎和多场所架构
