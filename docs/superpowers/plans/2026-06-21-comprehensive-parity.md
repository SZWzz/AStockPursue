# AStockPursue 全面补齐 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) to implement this plan task-by-task.

**Goal:** 对标 QuantFlow，分 6 个 Phase 补齐 84 个 Go 文件 + 64 个测试文件，覆盖 Research/ML/数据源/测试/通知/工作流节点。

**Tech Stack:** Go 1.25+, SQLite (缓存), GDELT/Finnhub/Polymarket HTTP APIs

---

## Phase 4: Research Service 层 (9 files + 8 tests)

### Task 4.1: Service 接口 + DataPoint 类型

**Files:** Create `services/go/internal/research/service.go`

```go
package research

import (
    "context"
    "time"
)

type DataPoint struct {
    Symbol    string
    Date      time.Time
    Category  string
    Key       string
    Value     float64
    Metadata  map[string]string
}

type Service interface {
    Name() string
    Analyze(ctx context.Context, symbol string, params map[string]any) (map[string]any, error)
    History(ctx context.Context, symbol string, days int) ([]DataPoint, error)
    IsAvailable(ctx context.Context) bool
}

type BaseService struct {
    NameVal string
    Adapter interface{} // nil = mock-only
    Repo    *Repo
}

func (s *BaseService) Name() string { return s.NameVal }
```

### Task 4.2: Repo (SQLite 缓存)

**Files:** Create `services/go/internal/research/repo.go`

```go
package research

import (
    "database/sql"
    "time"
)

type Repo struct {
    db *sql.DB
}

func NewRepo(db *sql.DB) *Repo { return &Repo{db: db} }

func (r *Repo) Init() error {
    _, err := r.db.Exec(`CREATE TABLE IF NOT EXISTS research_cache (
        symbol TEXT, category TEXT, key TEXT, value REAL, metadata TEXT,
        fetched_at INTEGER,
        PRIMARY KEY (symbol, category, key)
    )`)
    return err
}

func (r *Repo) Get(symbol, category, key string) (*DataPoint, error) {
    // SQLite query with TTL check (5 min)
}

func (r *Repo) Save(dp *DataPoint) error {
    // UPSERT
}
```

### Task 4.3: FinancialsService

**Files:** Create `services/go/internal/research/financials.go`

财报分析服务 — 从 Sina/CNINFO 拉取利润表/资产负债表/现金流关键指标：
- 营业总收入、净利润、ROE、毛利率
- 总资产、总负债、资产负债率
- 经营/投资/筹资现金流

回退：空适配器时返回 A 股行业平均 mock 数据。

### Task 4.4: GeopoliticsService (GDELT)

**Files:** Create `services/go/internal/research/geopolitics.go`

10 个预配置地缘政治主题：
1. US-China Trade War (中美贸易)
2. Taiwan Strait (台海)
3. South China Sea (南海)
4. Russia-Ukraine (俄乌)
5. Middle East Conflict (中东)
6. Energy Security (能源安全)
7. Semiconductor Supply Chain (芯片供应链)
8. Rare Earth Export Controls (稀土出口管制)
9. Global Inflation (全球通胀)
10. Emerging Market Debt (新兴市场债务)

每个主题返回最近 30 天 Tone (-10~+10) + Volume 时间序列。

### Task 4.5: NorthboundService (北向资金)

**Files:** Create `services/go/internal/research/northbound.go`

A 股核心资金指标：
- 日/周/月净流入
- 十大活跃股
- 累计净买入
- 行业分布

数据源：EastMoney 北向资金 HTTP API。

### Task 4.6: NewsService (新闻聚合+情绪)

**Files:** Create `services/go/internal/research/news.go`

多源聚合 (EastMoney News + Sina Finance + Finnhub)，自动拉取→拼接→Python NLP 分析。

---

## Phase 5: ML 管理 + 存储升级 (8 + 7)

### Task 5.1: ML ModelRegistry

**Files:** Create `services/go/internal/ml/registry.go`, `types.go`

```go
type MLModelType string
const (
    ModelTypeClassifier MLModelType = "classifier"
    ModelTypeRegressor  MLModelType = "regressor"
    ModelTypeRanker     MLModelType = "ranker"
)

type MLModel struct {
    ID          string
    Name        string
    ModelType   MLModelType
    Category    string // "factor", "signal", "risk"
    Hyperparams map[string]any
    Metrics     map[string]float64
    FilePath    string
    FileBytes   []byte
    Status      string // "training", "ready", "archived"
    CreatedAt   time.Time
    UpdatedAt   time.Time
}

type ModelRegistry struct {
    db *sql.DB
}

func (r *ModelRegistry) Create(ctx, model) error
func (r *ModelRegistry) Get(id) (*MLModel, error)
func (r *ModelRegistry) List(category) ([]*MLModel, error)
func (r *ModelRegistry) Archive(id) error
func (r *ModelRegistry) UpdateMetrics(id, metrics) error
```

### Task 5.2: ML Evaluator

**Files:** Create `services/go/internal/ml/evaluator.go`

```go
type Evaluator struct {
    backtestRunner *backtest.Runner
}

func (e *Evaluator) Evaluate(ctx, modelID, symbols, start, end) (*EvalResult, error)
// 加载模型 → 生成信号 → backtest → 返回 Sharpe/MaxDD/WinRate
```

### Task 5.3: 迁移系统 Go embed

**Files:** Create `services/go/internal/storage/migrate.go`, `migrations/`

```go
//go:embed migrations/*.sql
var migrationFS embed.FS

func Run(db *sql.DB) error // 幂等迁移，schema_version 表跟踪
```

### Task 5.4: 配置统一

**Files:** Create `services/go/internal/config/config.go`, `config.yaml` (root)

```go
type Config struct {
    Server   ServerConfig
    GRPC     GRPCConfig
    Database DatabaseConfig
    Redis    RedisConfig
    Auth     AuthConfig
}
```

---

## Phase 6: 数据源补齐 (10 + 10)

### Task 6.1: NorthboundAdapter (北向资金)

**Files:** Create `services/go/internal/market/adapters/northbound.go`

EastMoney 北向资金 HTTP API → `Adapter` 接口。

### Task 6.2: GDELTAdapter (地缘政治)

**Files:** Create `services/go/internal/market/adapters/gdelt.go`

`gdeltBaseURL = "https://api.gdeltproject.org/api/v2/doc/doc"` → `Adapter` 接口。

### Task 6.3: FinnhubAdapter (美股)

**Files:** Create `services/go/internal/market/adapters/finnhub.go`

免费 API Key, 60次/分钟, SEC filing + insider + 新闻。

### Task 6.4: iWenCaiAdapter (问财)

**Files:** Create `services/go/internal/market/adapters/iwencai.go`

同花顺 AI 选股 HTTP 接口，自然语言 → 股票列表。

### Task 6.5: CNINFOAdapter (巨潮)

**Files:** Create `services/go/internal/market/adapters/cninfo.go`

年报/公告/问询函，免费 HTTP API。

### Task 6.6: PolymarketAdapter (预测市场)

**Files:** Create `services/go/internal/market/adapters/polymarket.go`

`gamma-api.polymarket.com` — 事件概率 CLOB 数据。

### Task 6.7-6.10: 其余适配器

THSConsensus, SinaFinancials, SatelliteAdapter, GovDataAdapter。

---

## Phase 7: 测试文化升级 (0 + 5)

### Task 7.1: 为 Research 层加 mock 回退测试

### Task 7.2: 为 Adapter 层加 availability 测试

### Task 7.3: Phase 6 适配器集成测试

---

## Phase 8: 通知系统 Go 化 (5 + 4)

### Task 8.1: Notifier 接口 + Manager

```go
type Notifier interface {
    Name() string
    Send(msg *Message) error
    IsAvailable() bool
}

type Manager struct {
    notifiers []Notifier
    eventCh   chan *Message  // 256 buf
    db        *sql.DB
}
```

### Task 8.2: Telegram Bot

```go
type TelegramNotifier struct {
    botToken string
    chatID   string
}
```

### Task 8.3: Email Notifier

### Task 8.4: 删除 Python `notify/`（迁移到 Go）

---

## Phase 9: 工作流节点补齐 (52 + 30)

分 4 个 Batch，每批独立可测。

### Batch 1: Research 节点 (7)
- `financials` — 财报分析
- `analyst_estimates` — 分析师预期
- `northbound` — 北向资金
- `geopolitics` — 地缘政治
- `insider_trades` — 内部人交易
- `news_fetcher` — 新闻拉取
- `sentiment` — 情绪分析

### Batch 2: ML 节点 (8)
- `train_model`, `evaluate_model`, `predict`, `feature_importance`, `model_compare`, `hyperopt`, `cross_validate`, `ensemble`

### Batch 3: Alpha + Signal 节点 (21)
- Go 端重写 Python `alpha_nodes.py` + `signal_nodes.py` + `indicator_nodes.py`

### Batch 4: 工具节点 (16)
- `satellite`, `polymarket`, `schedule`, `scale`, `arithmetic`, `sub_workflow`, `alert`, `report`, `export_csv`, `export_json`, `cache`, `throttle`, `parallel`, `branch`, `merge`, `log`

---

## Final Verification

- [ ] `go test ./...` — 全部通过，目标覆盖率 40%+
- [ ] `ruff check src/ tests/` — 0 errors
- [ ] CHANGELOG 更新
- [ ] go vet 无警告

---

## Self-Review

1. **全面性**: 覆盖前次分析的 9 个差距维度，共 84 个 Go 文件 + 64 个测试
2. **可交付**: 每个 Phase 独立可测/可部署，不强依赖
3. **优先级**: Phase 4→5→6→7→8→9 依次推进，Phase 4 立即可实施
4. **风险**: 每个 Service 三级回退保证可用性，adapter nil = mock 不阻塞
5. **文件量**: 预估 Go 代码从 128 文件增长到 ~212 文件，测试率从 32% 提升到 38%+
