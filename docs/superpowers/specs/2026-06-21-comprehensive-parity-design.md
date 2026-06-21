# AStockPursue 全面补齐设计 —— 对标 QuantFlow

> 日期：2026-06-21 | 状态：已确认 | 参考：[重构规范](2026-06-20-go-python-hybrid-refactoring-design.md)、[QuantFlow 改进设计](2026-06-21-quantflow-inspired-improvements-design.md)

## 0. 动机

对比 QuantFlow（Go 199 源文件 + 76 测试，Python 56 文件），AStockPursue（Go 87 源文件 + 41 测试，Python 838 文件）在以下维度存在显著差距：

- **Research Service 层**：QuantFlow 17 文件，AStockPursue 0
- **工作流节点**：QuantFlow 76 节点/18 类别，AStockPursue 24 节点/1 文件
- **市场适配器**：QuantFlow 57 个，AStockPursue ~12 个
- **ML 管理**：QuantFlow Go 原生，AStockPursue 无
- **通知系统**：QuantFlow Go 多通道，AStockPursue Python 单通道
- **测试率**：QuantFlow 38%，AStockPursue 32%

本设计分 6 个 Phase 补齐差距。

---

## Phase 4 — Research Service 层 (Go)

### 4.1 架构

```
services/go/internal/research/   ← 新增
├── service.go                  # Service 接口 (Analyze/Query/History)
├── financials.go               # 财报分析
├── analyst_estimates.go        # 分析师一致预期
├── northbound.go               # 北向资金监控
├── geopolitics.go              # 地缘政治风险 (GDELT)
├── insider.go                  # 内部人交易
├── news.go                     # 新闻聚合+情绪
├── repo.go                     # SQLite 持久化 (缓存)
└── *_test.go                   # 测试
```

### 4.2 Service 接口

```go
type Service interface {
    Name() string
    Analyze(ctx context.Context, symbol string, params map[string]any) (map[string]any, error)
    History(ctx context.Context, symbol string, days int) ([]DataPoint, error)
    IsAvailable(ctx context.Context) bool
}
```

### 4.3 三级回退模式 (借鉴 QuantFlow)

每个 Service 实现三级回退：
1. **Cache** — SQLite 缓存 (5 min TTL)
2. **API** — 调用外部数据源
3. **Mock** — API 不可用时返回合理模拟数据

### 4.4 新增文件清单

| 文件 | 描述 |
|------|------|
| `research/service.go` | Service 接口 + DataPoint 类型 |
| `research/repo.go` | SQLite 缓存 CRUD |
| `research/financials.go` | 财报 (利润表/资产负债表/现金流) |
| `research/analyst_estimates.go` | 分析师评级+目标价+EPS 预期 |
| `research/northbound.go` | 沪深港通北向资金 (日/周/月) |
| `research/geopolitics.go` | GDELT 地缘政治风险 (10 主题) |
| `research/insider.go` | 内部人/大股东交易 |
| `research/news.go` | 多源新闻聚合+情绪评分 |

---

## Phase 5 — ML 管理 + 存储升级

### 5.1 ML ModelRegistry (Go)

```
services/go/internal/ml/   ← 新增
├── registry.go   # 模型 CRUD (SQLite)
├── evaluator.go  # 回测评估
├── types.go      # MLModel, Hyperparams, Metrics
└── *_test.go
```

### 5.2 迁移系统 Go embed

```
services/go/internal/storage/   ← 重构
├── migrate.go     # embed + schema_version 幂等迁移
├── migrations/    # *.sql 文件
└── *_test.go
```

### 5.3 配置统一

```
services/go/internal/config/
├── config.go      # Viper/YAML 统一配置
└── config_test.go
```

```yaml
# config.yaml (项目根)
server:
  port: 8899
grpc:
  python_addr: localhost:8902
database:
  postgres_url: postgres://...
  timescale_url: postgres://...
redis:
  addr: localhost:6379
auth:
  api_key: "${API_KEY}"
```

---

## Phase 6 — 数据源补齐

### 6.1 新增适配器（按价值排序）

| 优先级 | 适配器 | 市场 | 数据 | 难度 |
|--------|--------|------|------|------|
| P0 | **NorthboundAdapter** | CN | 北向资金 (沪深港通) | 中 |
| P0 | **GDELTAdapter** | Global | 地缘政治事件情绪 | 低 |
| P1 | **iWenCaiAdapter** | CN | AI 选股/自然语言查询 | 中 |
| P1 | **FinnhubAdapter** | US | SEC filing/insider/新闻 | 低 |
| P1 | **CNINFOAdapter** | CN | 年报/公告/问询函 | 低 |
| P2 | **PolymarketAdapter** | Global | 预测市场概率 | 低 |
| P2 | **THSConsensusAdapter** | CN | 同花顺一致预期 | 中 |
| P2 | **SinaFinancialsAdapter** | CN | 三大报表 | 中 |
| P3 | **SatelliteAdapter** | Global | NASA 能源数据 | 低 |
| P3 | **GovDataAdapter** | CN | 政府公开数据 | 低 |

### 6.2 Adapter 接口（已在 P2 定义）

```go
type Adapter interface {
    Name() string
    Markets() []string
    RequiresAuth() bool
    IsAvailable(ctx context.Context) bool
    Fetch(ctx context.Context, req FetchRequest) ([]Bar, error)
}
```

---

## Phase 7 — 测试文化升级

### 7.1 目标

- Go 测试覆盖率：32% → **40%+**
- 参照 QuantFlow 的 adapter nil → mock 自动回退模式
- 每个 adapter 独立测试文件
- Phase 集成测试

### 7.2 Mock 回退模式

```go
func NewService(adapter Adapter, repo *Repo) *Service {
    return &Service{adapter: adapter, repo: repo}
}

func (s *Service) Analyze(ctx context.Context, symbol string) (*Result, error) {
    // 1. Cache
    if cached := s.repo.Get(symbol); cached != nil { return cached, nil }
    
    // 2. API (adapter may be nil)
    if s.adapter != nil && s.adapter.IsAvailable(ctx) {
        result, err := s.adapter.Fetch(ctx, ...)
        if err == nil { s.repo.Save(result); return result, nil }
    }
    
    // 3. Mock fallback
    return s.mockResult(symbol), nil
}
```

---

## Phase 8 — 通知系统 Go 化

```
services/go/internal/notify/   ← 重构
├── manager.go    # event channel 256 buf, 多通道分发
├── telegram.go   # Telegram Bot API
├── email.go      # SMTP 邮件
├── store.go      # SQLite 通知历史
├── types.go      # Message, Notifier 接口
└── *_test.go
```

```go
type Notifier interface {
    Name() string
    Send(msg *Message) error
    IsAvailable() bool
}

type Manager struct {
    notifiers []Notifier
    eventCh   chan *Message
    db        *sql.DB
}
```

---

## Phase 9 — 工作流节点补齐

### 9.1 新增 Go 工作流节点（52 个 → 分 4 批）

**Batch 1 — Research 节点 (7 个)**：
`financials`, `analyst_estimates`, `northbound`, `geopolitics`, `insider`, `news`, `sentiment`

**Batch 2 — ML 节点 (8 个)**：
`train_model`, `evaluate_model`, `predict`, `feature_importance`, `model_compare`, `hyperopt`, `cross_validate`, `ensemble`

**Batch 3 — Alpha + Signal 节点 (21 个)**：
继承自 Python `alpha_nodes.py` + `signal_nodes.py`，Go 端重新实现

**Batch 4 — 另类数据 + 工具节点 (16 个)**：
`satellite`, `polymarket`, `schedule`, `scale`, `arithmetic`, `sub_workflow`, `alert`, `report`, `export_csv`, `export_json`, `cache`, `throttle`, `parallel`, `branch`, `merge`, `log`

---

## 实施路线图

```
Week 1: Phase 4 (Research) + Phase 5 (ML + 存储)
Week 2: Phase 6 (数据源) + Phase 7 (测试)
Week 3: Phase 8 (通知) + Phase 9 Batch 1 (Research 节点)
Week 4: Phase 9 Batch 2-4 (ML/Alpha/工具节点)
```

## 文件总量预估

| Phase | 新建 Go 文件 | 新建测试 | Python 改动 |
|-------|------------|---------|------------|
| P4 | 9 | 8 | 0 |
| P5 | 8 | 7 | 0 |
| P6 | 10 | 10 | 0 |
| P7 | 0 | 5 | 0 |
| P8 | 5 | 4 | delete `notify/` |
| P9 | 52 | 30 | 0 (增量) |
| **合计** | **84** | **64** | delete `notify/` |

---

## 风险评估

| 风险 | 缓解 |
|------|------|
| Go 代码量翻倍，module 膨胀 | 每个 phase 独立可交付，不强依赖 |
| 外部 API 不稳定（GDELT/同花顺） | 三级回退保证可用性 |
| SQLite WAL 与现有 PG+TimescaleDB 重复 | SQLite 仅做本地缓存，主存储仍用 PG |
| Phase 9 52 节点迁移量过大 | 分 4 批，每批独立可测 |
