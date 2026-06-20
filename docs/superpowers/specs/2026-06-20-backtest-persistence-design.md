# 回测数据持久化设计

> 日期：2026-06-20 | 状态：草稿

## 1. 目标

将当前回测结果从进程内内存存储迁移到 PostgreSQL/TimescaleDB 持久化存储，使回测结果在服务重启后不丢失，并支持后续查询、对比和报表功能。

## 2. 数据模型

### 2.1 表结构

#### backtest_runs（普通 PG 表）

存储回测级别的概要指标。每条记录对应一次 POST /api/v1/backtest 调用。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | PRIMARY KEY，服务端生成 v4 |
| symbols | TEXT[] | 回测标的列表，如 {"000001","600001"} |
| start_date | TIMESTAMPTZ | 回测开始日期 |
| end_date | TIMESTAMPTZ | 回测结束日期 |
| frequency | TEXT | 如 "1d"、"60m" |
| initial_cash | DOUBLE PRECISION | 初始资金 |
| final_equity | DOUBLE PRECISION | 最终权益 |
| total_return | DOUBLE PRECISION | 总收益率 |
| sharpe_ratio | DOUBLE PRECISION | 夏普比率（年化） |
| max_drawdown | DOUBLE PRECISION | 最大回撤（金额） |
| max_drawdown_pct | DOUBLE PRECISION | 最大回撤（百分比） |
| win_rate | DOUBLE PRECISION | 胜率 |
| total_trades | INT | 总交易次数 |
| winning_trades | INT | 盈利交易次数 |
| losing_trades | INT | 亏损交易次数 |
| signal_name | TEXT | 策略名称（预留） |
| risk_config | JSONB | 风控配置（预留） |
| created_at | TIMESTAMPTZ | 默认 NOW() |

#### equity_curves（TimescaleDB hypertable）

存储每根 bar 结束后的权益快照。按 timestamp 分区，使用 TimescaleDB 自动管理。

| 字段 | 类型 | 说明 |
|------|------|------|
| run_id | UUID | FK → backtest_runs(id) |
| timestamp | TIMESTAMPTZ NOT NULL | bar 结束时间 |
| equity | DOUBLE PRECISION | 当前权益 |
| cash | DOUBLE PRECISION | 当前现金 |
| position_count | INT | 持仓品种数 |

主键：(run_id, timestamp)

#### trades（普通 PG 表）

存储回测过程中每笔成交记录。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | PRIMARY KEY |
| run_id | UUID | FK → backtest_runs(id) |
| symbol | TEXT | 标的 |
| side | TEXT | "buy" / "sell" |
| quantity | DOUBLE PRECISION | 成交数量 |
| price | DOUBLE PRECISION | 成交价格 |
| commission | DOUBLE PRECISION | 佣金 |
| pnl | DOUBLE PRECISION | 盈亏（仅平仓记录有） |
| timestamp | TIMESTAMPTZ | 成交时间 |
| created_at | TIMESTAMPTZ | 默认 NOW() |

索引：CREATE INDEX idx_trades_run_id ON trades(run_id)

### 2.2 Schema 创建

在 `db.TimescaleDB.InitSchema()` 中加入以上表的 CREATE TABLE IF NOT EXISTS 语句。执行顺序：

1. `backtest_runs`（普通表）
2. `equity_curves`（hypertable）
3. `trades`（普通表）

## 3. 架构

### 3.1 Repository 接口

```go
type BacktestRepository interface {
    Save(ctx context.Context, result *engine.BacktestResult) (string, error)
    Get(ctx context.Context, id string) (*engine.BacktestResult, error)
    List(ctx context.Context) ([]string, error)
}
```

### 3.2 两个实现

| 实现 | 文件 | 用途 |
|------|------|------|
| MemoryBacktestStore | `internal/api/handler/backtest.go`（已有，改名为实现接口） | 开发/测试/无 DB 环境 |
| PostgresBacktestStore | `internal/db/backtest.go`（新建） | 生产环境 |

### 3.3 Handler 层改动

`BacktestHandler` 不再依赖具体 Store 类型，改为注入 `BacktestRepository` 接口：

```go
type BacktestHandler struct {
    repo    BacktestRepository
    ds      *market.DataStore
    factory *engine.EngineFactory
}
```

### 3.4 数据流

**写入（POST /api/v1/backtest）：**
```
Request → BacktestRunner.Run() → BacktestResult
  → repo.Save(ctx, result) 写入:
      1. INSERT INTO backtest_runs → 返回 UUID
      2. Batch INSERT equity_curves
      3. Batch INSERT trades
  → 返回 { id, result }
```

**读取（GET /api/v1/backtest/:id）：**
```
Request → repo.Get(ctx, id):
  1. SELECT FROM backtest_runs WHERE id = $1
  2. SELECT FROM equity_curves WHERE run_id = $1 ORDER BY timestamp
  3. SELECT FROM trades WHERE run_id = $1 ORDER BY timestamp
  → 组装 BacktestResult
→ 返回 { id, result }
```

## 4. 文件清单

| 文件 | 动作 | 说明 |
|------|------|------|
| `internal/db/backtest.go` | 新建 | PostgresBacktestStore 实现 |
| `internal/db/backtest_test.go` | 新建 | 单元测试 |
| `internal/db/timescale.go` | 修改 | InitSchema 加新表 |
| `internal/api/handler/backtest.go` | 修改 | 引入 Repository 接口，MemoryStore 实现接口 |
| `internal/api/handler/backtest_test.go` | 修改/新建 | Handler 测试适配接口 |
| `cmd/server/main.go` | 修改 | 根据 DB 配置选择 Repository 实现 |
| `internal/config/config.go` | 不动 | 已有 DatabaseURL |

## 5. 边界与约束

- 回测运行是统计计算，数据量可控（单次回测 equity_curves ~数千行，trades ~数百行）
- 暂不支持回测结果删除/修改（幂等的 CREATE TABLE IF NOT EXISTS，未来可通过 ON CONFLICT 实现 upsert）
- equity_curves 使用 hypertable 的 timestamp 分区，无需手动管理分区
- UUID 使用 PostgreSQL 原生 `gen_random_uuid()` 或 Go 端 `github.com/google/uuid`

## 6. 未来扩展

- 回测结果对比（两个回测并列展示 equity curve）
- 按 signal_name + symbols 搜索历史回测
- 回测结果分页（当前数据量下不需要，预留 limit/offset 参数接口即可）
