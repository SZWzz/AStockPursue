# Go Engine 实现规范 —— 6 引擎全量迁移

> 日期：2026-06-20 | 状态：已确认
> 关联架构规范：`2026-06-20-go-python-hybrid-refactoring-design.md` (P3 阶段)

## 1. 目标

将 Python 端的 6 个交易引擎实现迁移至 Go，补全 `services/go/internal/engine/` 中缺失的引擎类型。

## 2. 引擎接口（已有）

```go
type Engine interface {
    Name() string
    CanExecute(order *Order, positions map[string]*Position) bool
    RoundSize(size float64) float64
    CalcCommission(order *Order, price float64) float64
    ApplySlippage(order *Order, bar interface{}) float64
    CalcMargin(position *Position) float64
    CalcPnL(position *Position) float64
}
```

## 3. 引擎实现细则

### 3.1 CryptoEngine (`crypto.go`)

**适用市场**：Binance / OKX / Bybit 永续合约 (perpetual swap)

| 参数 | 值 | 说明 |
|------|-----|------|
| MakerFee | 0.0002 (0.02%) | 挂单费率 |
| TakerFee | 0.0006 (0.06%) | 吃单费率 |
| Slippage | 0.001 (0.1%) | 价格滑点系数 |
| LeverageDefault | 10 | 默认杠杆倍数 |
| MaintenanceMargin | 0.005 (0.5%) | 维持保证金率 |

**关键逻辑**：
- `CanExecute`：双向交易（long/short），需检查保证金是否足够；开仓：`required_margin = qty * price / leverage` ≤ free cash
- `RoundSize`：按交易所最小交易单位做舍入（BTC：0.001，ETH：0.01，其他按 1）
- `CalcCommission`：按 `qty * price * fee_rate` 计算
- `ApplySlippage`：buy = close * (1 + slippage)，sell = close * (1 - slippage)
- `CalcMargin`：`abs(size) * current_price / position.leverage`
- `CalcPnL`：long = `(current - entry) * size`，short = `(entry - current) * abs(size)`
- **LiquidationPrice**：long = `entry * (1 - 1/leverage + maintenance_margin)`，short = `entry * (1 + 1/leverage - maintenance_margin)`
- **FundingFee**：每 8 小时结算一次（按 position 名义价值的费率）

### 3.2 GlobalEquityEngine (`global_equity.go`)

**适用市场**：US (NYSE/NASDAQ) / HK (HKEX) / 伦敦等

| 参数 | US | HK |
|------|-----|-----|
| Commission | $0.005/share (min $1) | 0.25% (min HKD 100) |
| StampDuty | 0 | 0.13% |
| Slippage | 0.001 (0.1%) | 0.001 (0.1%) |
| RoundLot | 1 | 1 |
| CanShort | true | limited |
| PriceLimit | 无 | 无 |

**关键逻辑**：
- `CanExecute`：US 允许做空（实现 uptick rule 可选），HK 默认仅 long
- `RoundSize`：最小 1 股
- `CalcCommission`：US = `max(flat_per_share * qty, min_commission)`，HK = `max(turnover * rate, min_commission) + turnover * stamp_duty`（仅 sell 侧）
- `ApplySlippage`：buy/sell 均 0.1%
- `CalcMargin`：无杠杆需求（现金交易），margin = turnover * 0.5（Reg T 50%）。做空需要额外保证金
- `CalcPnL`：standard = (current - entry) * size

### 3.3 ForexEngine (`forex.go`)

**适用市场**：FX spot / CFD（EUR/USD, USD/JPY, GBP/USD 等）

| 参数 | 值 | 说明 |
|------|-----|------|
| SpreadMajor | 0.0002 (2 pips) | 主要货币对点差（成本） |
| SpreadMinor | 0.0005 (5 pips) | 交叉盘点差 |
| Slippage | 0.0001 (1 pip) | 滑点 |
| LeverageDefault | 30 | 默认杠杆（零售客户） |
| LotSize | 100000 | 标准手单位基础货币 |
| MinCommission | 0 | 点差即成本，无额外佣金 |

**关键逻辑**：
- `CanExecute`：双向交易，只需检查 margin
- `RoundSize`：按 lot 舍入（0.01 lot 精度）
- `CalcCommission`：返回 0（点差已在价格中包含），或者按 `turnover * 0.00001`（ECN 模式，取决于配置）
- `ApplySlippage`：buy = close * (1 + slippage)，sell = close * (1 - slippage)
- `CalcMargin`：`turnover / leverage * rate`（如 1 标准手 EUR/USD 在 30:1 下：100000 / 30 = ~$3,333）
- `CalcPnL`：按 pip 值计算，1 pip on standard lot = $10 for USD quote pairs

### 3.4 FuturesBase (`futures_base.go`)

**基类/嵌入结构体**，提供期货共用的合约乘数、保证金、逐日盯市逻辑：

```go
type FuturesBase struct {
    ContractMultiplier float64  // 合约乘数（如 IF=300, IC=200, ES=$50）
    MarginRate         float64  // 保证金比例
    CommissionRate     float64  // 手续费率（按成交额）
    MinCommission      float64  // 最低手续费
    PriceTick          float64  // 最小变动价位
    RoundLot           float64  // 最小交易手数
    PriceLimitPct      float64  // 涨跌停幅度
}
```

| 方法 | 逻辑 |
|------|------|
| `RoundSize` | 整数手：`floor(size / lot_size) * lot_size` |
| `CalcCommission` | `max(turnover * commission_rate, min_commission)` |
| `CalcMargin` | `turnover * margin_rate` |
| `CalcPnL` | `(current - entry) * size * multiplier` |
| `CanExecute` | 双向开仓（期货天然做多做空），检查 margin |
| `ApplySlippage` | buy = close + priceTick，sell = close - priceTick（非百分比，按 tick） |

### 3.5 ChinaFuturesEngine (`china_futures.go`)

**嵌入 FuturesBase**，覆盖中国市场特定合约参数。

| 交易所 | 示例合约 | Multiplier | MarginRate | Commission | PriceLimit |
|--------|---------|------------|------------|------------|------------|
| CFFEX | IF, IC, IH | 300/200/300 | 12% | 0.0023% | ±10% |
| SHFE | RB, CU, AU | 10/5/1000 | 8-15% | 0.01% | ±5-8% |
| DCE | I, JM, C | 100/60/10 | 8-20% | 0.01% | ±4-8% |
| ZCE | CF, SR, TA | 5/10/20 | 5-15% | 0.01% | ±4-6% |
| INE | SC, NR | 1000/10 | 10-15% | 0.01% | ±8-10% |
| GFEX | SI, LC | 10/5 | 8-12% | 0.01% | ±8% |

**关键逻辑**：
- `RoundSize`：按整数手（最小 1 手），不支持小数
- T+0：当天开可当天平
- 逐日盯市：每日结算盈亏到现金账户
- 有涨跌停限制（结算价的 ±Pct%）
- 手续费为双边（开仓+平仓）

### 3.6 GlobalFuturesEngine (`global_futures.go`)

**嵌入 FuturesBase**，覆盖国际市场合约参数。

| 交易所 | 示例合约 | Multiplier | Commission | PriceLimit |
|--------|---------|-------------|------------|------------|
| CME | ES, NQ, CL | $50/$20/1000 | $2.50/contract | 熔断 |
| ICE | B, CC, KC | 50000/10/37500 | $1.50/contract | 无日限 |
| EUREX | FDAX, FESX | 25/10 | €1.80/contract | 无日限 |

**关键逻辑**：
- 佣金按合约数计算（per-contract fee），非按成交额
- 保证金为 SPAN 固定值（非百分比，但实现简化为百分比）
- 无涨跌停但有熔断机制（实现中简化为无限制）
- 可做多做空

### 3.7 OptionsEngine (`options.go`)

**适用**：欧式/美式期权

**定价**：Black-Scholes 定价模型

```go
type OptionContract struct {
    Symbol    string
    Strike    float64
    Expiry    time.Time
    OptionType string // "call" / "put"
    Style     string // "european" / "american"
    Multiplier float64 // 合约乘数（通常 100）
}
```

| 参数 | 值 |
|------|-----|
| CommissionPerContract | $0.65 (US 期权) |
| ExerciseFee | $5.00 |
| AssignmentFee | $5.00 |
| Slippage | $0.01 (1 cent per share) |
| MarginRateShort | 0.20 (裸卖空保证金 20% + 期权金) |

**关键逻辑**：
- `RoundSize`：按整数合约（1 合约 = 100 股）
- `CanExecute`：买卖期权只需要 premium + commission。裸卖空看涨/看跌需要额外保证金
- `CalcCommission`：`contracts * commission_per_contract * multiplier`
- `ApplySlippage`：buy = ask + $0.01, sell = bid - $0.01
- `CalcMargin`：long = 0（期权买方只需支付权利金），short = `turnover * 0.20 + premium_received`
- `CalcPnL`：call = `max(current_price - strike, 0) * multiplier * contracts - premium_paid`，put = `max(strike - current_price, 0) * multiplier * contracts - premium_paid`
- 到期自动行权逻辑（若 ITM）

## 4. EngineFactory 路由更新

`ForSymbol` 前缀路由表更新：

| 引擎 | 前缀/条件 |
|------|----------|
| ChinaAEngine | `6`, `0`, `3`, `4`, `8`, `9` |
| CryptoEngine | `BTC`, `ETH`, `BNB`, `SOL`, `XRP`... 或通过 config 注册 |
| GlobalEquityEngine | 非 A 股且非 crypto 的字母打头代码（通过 symbol 配置区分市场） |
| ForexEngine | `EUR`, `GBP`, `JPY`, `AUD`, `CAD`, `CHF`, `NZD` + `USD` 结构 |
| ChinaFuturesEngine | `IF`, `IC`, `IH`, `RB`, `CU`... CFFEX/SHFE/DCE/ZCE/INE/GFEX 代码 |
| GlobalFuturesEngine | `ES`, `NQ`, `CL`, `GC`, `SI`... CME/ICE/Eurex 代码 |
| OptionsEngine | 通过 symbol 后缀或 config 识别（如 `.OPT` 后缀） |

实际使用中，EngineFactory 支持 `RegisterEngine(name string, engine Engine)` 方式注入，`ForSymbol` 前缀匹配只是默认路由。

## 5. 测试策略

每个引擎包含独立 test 文件，覆盖率：

| 测试类别 | Crypto | GlobalEq | Forex | CFFutures | GbFutures | Options |
|----------|--------|----------|-------|-----------|-----------|---------|
| 方向计算 (PnL) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 佣金计算 | maker+taker | US+HK | spread | 各所费率 | per-contract | per-contract |
| 滑点 | ✓ | ✓ | ✓ | tick-based | tick-based | cent-based |
| 保证金 | 杠杆 | Reg T | leverage | margin rate | SPAN | short margin |
| 做空限制 | both | US=ok,HK=no | both | both | both | short=special |
| RoundSize | 精度舍入 | 1股 | 0.01lot | 整数手 | 整数手 | 整数合约 |
| 涨跌停/熔断 | 无 | 无 | 无 | ✓ | 熔断简化 | 无 |

## 6. 非目标

- **不实现** Python 端的 `_market_hooks.py`（资金费率、清算周期等），留待后续
- **不实现** Python 端的数据加载器，仅实现引擎执行规则
- **不迁移** OptimizerAdapter、StateMachine（保留在 Python）
- **不实现** 实时行情订阅（P4 阶段目标）
