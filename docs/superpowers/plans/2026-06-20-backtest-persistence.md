# 回测数据持久化 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将回测结果从进程内内存存储迁移到 PostgreSQL/TimescaleDB，支持重启后数据不丢失。

**Architecture:** Repository 接口模式——`BacktestRepository` 接口定义 Save/Get/List，`MemoryBacktestStore`（已有，改造为接口实现）和 `PostgresBacktestStore`（新建，pgx 实现）两种实现。Handler 通过接口依赖注入，生产环境根据 DB 连接可用性选择实现。

**Tech Stack:** Go 1.22+, pgx/v5, TimescaleDB, github.com/google/uuid

## 全局约束

- 所有 Go 代码在 `services/go/internal/`
- Repository 接口定义在 `internal/api/handler/backtest.go`（与 Handler 同包）
- PostgresBacktestStore 在 `internal/db/backtest.go`
- Schema 创建在 `internal/db/timescale.go` 的 InitSchema 中追加
- UUID 使用 `github.com/google/uuid`
- 测试使用 `stretchr/testify` 断言

---

### Task 1: Repository 接口 + MemoryStore 改造

**Files:**
- Create: `services/go/internal/api/handler/backtest_test.go`
- Modify: `services/go/internal/api/handler/backtest.go`

**Interfaces:**
- Produces: `BacktestRepository` 接口（Save/Get/List），`MemoryBacktestStore` 实现该接口

- [ ] **Step 1: 添加依赖并初始化 go modules**

```powershell
cd services/go
go get github.com/google/uuid
```

- [ ] **Step 2: 写单元测试（handler 测试）**

```go
// services/go/internal/api/handler/backtest_test.go
package handler

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/astockpursue/go-core/internal/engine"
	"github.com/astockpursue/go-core/internal/market"
	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/assert"
)

func TestBacktestHandlerRun(t *testing.T) {
	store := NewBacktestStore()
	ds := market.NewDataStore(nil, market.NewMemoryCache(time.Hour))
	factory := engine.NewEngineFactory()
	h := NewBacktestHandler(store, ds, factory)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	body := `{"symbols":["000001"],"start_date":"2026-01-01","end_date":"2026-01-10","frequency":"1d","initial_cash":100000}`
	c.Request, _ = http.NewRequest("POST", "/api/v1/backtest", strings.NewReader(body))
	c.Request.Header.Set("Content-Type", "application/json")

	h.Run(c)
	assert.Equal(t, 200, w.Code)

	var resp struct {
		ID     string             `json:"id"`
		Result *engine.BacktestResult `json:"result"`
	}
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.NotEmpty(t, resp.ID)
	assert.NotNil(t, resp.Result)
	assert.Equal(t, 100000.0, resp.Result.InitialCash)
}

func TestBacktestHandlerGetResult(t *testing.T) {
	store := NewBacktestStore()
	ds := market.NewDataStore(nil, market.NewMemoryCache(time.Hour))
	factory := engine.NewEngineFactory()
	h := NewBacktestHandler(store, ds, factory)

	result := &engine.BacktestResult{
		InitialCash: 100000, FinalEquity: 110000, TotalReturn: 0.1,
		EquityCurve: []engine.EquityPoint{
			{Timestamp: time.Now(), Equity: 100000, Cash: 100000},
		},
		Trades: []engine.TradeRecord{
			{Symbol: "000001", Side: "buy", Quantity: 100, Price: 10},
		},
	}
	store.Save(context.Background(), result)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Request, _ = http.NewRequest("GET", "/api/v1/backtest/1", nil)
	c.Params = []gin.Param{{Key: "id", Value: "1"}}

	h.GetResult(c)
	assert.Equal(t, 200, w.Code)
	assert.True(t, strings.Contains(w.Body.String(), `"total_return":0.1`))
}

func TestBacktestHandlerGetNotFound(t *testing.T) {
	store := NewBacktestStore()
	ds := market.NewDataStore(nil, market.NewMemoryCache(time.Hour))
	factory := engine.NewEngineFactory()
	h := NewBacktestHandler(store, ds, factory)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Request, _ = http.NewRequest("GET", "/api/v1/backtest/nonexistent", nil)
	c.Params = []gin.Param{{Key: "id", Value: "nonexistent"}}

	h.GetResult(c)
	assert.Equal(t, 404, w.Code)
}
```

- [ ] **Step 3: Run test to verify it fails**

```powershell
cd services/go
go test ./internal/api/handler/ -v -count=1 -run TestBacktestHandler
```
Expected: FAIL — compilation errors (BacktestRepository not defined, Save not found on store)

- [ ] **Step 4: 定义 Repository 接口 + 改造 MemoryBacktestStore**

```go
// services/go/internal/api/handler/backtest.go
// 在文件顶部添加接口定义，改造 MemoryBacktestStore 实现接口

type BacktestRepository interface {
	Save(ctx context.Context, result *engine.BacktestResult) (string, error)
	Get(ctx context.Context, id string) (*engine.BacktestResult, error)
	List(ctx context.Context) ([]string, error)
}

// MemoryBacktestStore 实现 BacktestRepository 接口
// 改 save/get/list 方法签名为公开方法（大写首字母）
```

完整修改后文件内容：

```go
package handler

import (
	"context"
	"fmt"
	"net/http"
	"sync"
	"time"

	"github.com/astockpursue/go-core/internal/engine"
	"github.com/astockpursue/go-core/internal/market"
	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
)

type BacktestRepository interface {
	Save(ctx context.Context, result *engine.BacktestResult) (string, error)
	Get(ctx context.Context, id string) (*engine.BacktestResult, error)
	List(ctx context.Context) ([]string, error)
}

type BacktestRequest struct {
	Symbols     []string `json:"symbols" binding:"required"`
	StartDate   string   `json:"start_date" binding:"required"`
	EndDate     string   `json:"end_date" binding:"required"`
	Frequency   string   `json:"frequency" binding:"required"`
	InitialCash float64  `json:"initial_cash" binding:"required"`
}

type MemoryBacktestStore struct {
	mu      sync.RWMutex
	results map[string]*engine.BacktestResult
}

func NewBacktestStore() *MemoryBacktestStore {
	return &MemoryBacktestStore{results: make(map[string]*engine.BacktestResult)}
}

func (s *MemoryBacktestStore) Save(ctx context.Context, result *engine.BacktestResult) (string, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	id := uuid.New().String()
	s.results[id] = result
	return id, nil
}

func (s *MemoryBacktestStore) Get(ctx context.Context, id string) (*engine.BacktestResult, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	r, ok := s.results[id]
	if !ok {
		return nil, fmt.Errorf("backtest result not found: %s", id)
	}
	return r, nil
}

func (s *MemoryBacktestStore) List(ctx context.Context) ([]string, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	ids := make([]string, 0, len(s.results))
	for id := range s.results {
		ids = append(ids, id)
	}
	return ids, nil
}

type BacktestHandler struct {
	repo    BacktestRepository
	ds      *market.DataStore
	factory *engine.EngineFactory
}

func NewBacktestHandler(repo BacktestRepository, ds *market.DataStore, factory *engine.EngineFactory) *BacktestHandler {
	return &BacktestHandler{repo: repo, ds: ds, factory: factory}
}

func (h *BacktestHandler) Run(c *gin.Context) {
	var req BacktestRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	start, err := time.Parse("2006-01-02", req.StartDate)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid start_date, use YYYY-MM-DD"})
		return
	}
	end, err := time.Parse("2006-01-02", req.EndDate)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid end_date, use YYYY-MM-DD"})
		return
	}

	p := &engine.Pipeline{
		Engine:    h.factory.ForSymbol(req.Symbols[0]),
		Portfolio: &engine.Portfolio{
			Cash:      req.InitialCash,
			Equity:    req.InitialCash,
			Positions: make(map[string]*engine.Position),
		},
		Signal:   engine.NewNoopSignalAdapter(),
		Risk:     engine.NewRiskManager(engine.RiskConfig{}),
		LastBars: make(map[string]interface{}),
	}

	runner := engine.NewBacktestRunner(p, h.ds)
	result, err := runner.Run(req.Symbols, start, end, req.Frequency)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	id, err := h.repo.Save(c.Request.Context(), result)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"id": id, "result": result})
}

func (h *BacktestHandler) GetResult(c *gin.Context) {
	id := c.Param("id")
	result, err := h.repo.Get(c.Request.Context(), id)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"id": id, "result": result})
}

func (h *BacktestHandler) ListResults(c *gin.Context) {
	ids, err := h.repo.List(c.Request.Context())
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"ids": ids})
}
```

- [ ] **Step 5: Run tests to verify**

```powershell
cd services/go
go mod tidy
go test ./internal/api/handler/ -v -count=1 -run TestBacktestHandler
```
Expected: PASS

- [ ] **Step 6: Commit**

```powershell
git add services/go/internal/api/handler/backtest.go services/go/internal/api/handler/backtest_test.go services/go/go.mod services/go/go.sum
git commit -m "refactor(handler): extract BacktestRepository interface, MemoryStore implements it"
```

---

### Task 2: InitSchema 追加回测表

**Files:**
- Modify: `services/go/internal/db/timescale.go`
- Modify: `services/go/internal/db/timescale_test.go`

**Interfaces:**
- Consumes: pool from TimescaleDB
- Produces: backtest_runs, equity_curves, trades 三张表

- [ ] **Step 1: 写测试**

```go
// services/go/internal/db/timescale_test.go
func TestBuildBacktestSQL(t *testing.T) {
	db := &TimescaleDB{}
	sql := db.buildBacktestRunsSQL()
	assert.Contains(t, sql, "CREATE TABLE IF NOT EXISTS backtest_runs")
	assert.Contains(t, sql, "UUID")
}

func TestBuildEquityCurvesSQL(t *testing.T) {
	db := &TimescaleDB{}
	sql := db.buildEquityCurvesSQL()
	assert.Contains(t, sql, "CREATE TABLE IF NOT EXISTS equity_curves")
	assert.Contains(t, sql, "create_hypertable")
}

func TestBuildTradesSQL(t *testing.T) {
	db := &TimescaleDB{}
	sql := db.buildTradesSQL()
	assert.Contains(t, sql, "CREATE TABLE IF NOT EXISTS trades")
	assert.Contains(t, sql, "idx_trades_run_id")
}
```

- [ ] **Step 2: Run to fail**

```powershell
cd services/go
go test ./internal/db/ -v -count=1 -run TestBuildBacktest
```
Expected: FAIL — functions not defined

- [ ] **Step 3: 在 InitSchema 中追加建表语句**

在 `timescale.go` 的 `buildCreateTableSQL()` 方法（重命名为 `buildBarsTableSQL()`）后追加三个新方法。InitSchema 依次执行所有建表语句。

```go
func (db *TimescaleDB) InitSchema(ctx context.Context) error {
	statements := []string{
		db.buildBarsTableSQL(),
		db.buildBacktestRunsSQL(),
		db.buildEquityCurvesSQL(),
		db.buildTradesSQL(),
	}
	for _, s := range statements {
		if _, err := db.pool.Exec(ctx, s); err != nil {
			return fmt.Errorf("schema init: %w", err)
		}
	}
	return nil
}

func (db *TimescaleDB) buildBarsTableSQL() string {
	return `...` // 原有的 buildCreateTableSQL 内容
}

func (db *TimescaleDB) buildBacktestRunsSQL() string {
	return `
CREATE TABLE IF NOT EXISTS backtest_runs (
    id              UUID PRIMARY KEY,
    symbols         TEXT[] NOT NULL,
    start_date      TIMESTAMPTZ NOT NULL,
    end_date        TIMESTAMPTZ NOT NULL,
    frequency       TEXT NOT NULL DEFAULT '1d',
    initial_cash    DOUBLE PRECISION NOT NULL,
    final_equity    DOUBLE PRECISION NOT NULL DEFAULT 0,
    total_return    DOUBLE PRECISION NOT NULL DEFAULT 0,
    sharpe_ratio    DOUBLE PRECISION NOT NULL DEFAULT 0,
    max_drawdown    DOUBLE PRECISION NOT NULL DEFAULT 0,
    max_drawdown_pct DOUBLE PRECISION NOT NULL DEFAULT 0,
    win_rate        DOUBLE PRECISION NOT NULL DEFAULT 0,
    total_trades    INT NOT NULL DEFAULT 0,
    winning_trades  INT NOT NULL DEFAULT 0,
    losing_trades   INT NOT NULL DEFAULT 0,
    signal_name     TEXT,
    risk_config     JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);`
}

func (db *TimescaleDB) buildEquityCurvesSQL() string {
	return `
CREATE TABLE IF NOT EXISTS equity_curves (
    run_id          UUID NOT NULL REFERENCES backtest_runs(id) ON DELETE CASCADE,
    timestamp       TIMESTAMPTZ NOT NULL,
    equity          DOUBLE PRECISION NOT NULL,
    cash            DOUBLE PRECISION NOT NULL,
    position_count  INT NOT NULL DEFAULT 0,
    PRIMARY KEY (run_id, timestamp)
);
SELECT create_hypertable('equity_curves', 'timestamp', if_not_exists => TRUE);`
}

func (db *TimescaleDB) buildTradesSQL() string {
	return `
CREATE TABLE IF NOT EXISTS trades (
    id          UUID PRIMARY KEY,
    run_id      UUID NOT NULL REFERENCES backtest_runs(id) ON DELETE CASCADE,
    symbol      TEXT NOT NULL,
    side        TEXT NOT NULL,
    quantity    DOUBLE PRECISION NOT NULL,
    price       DOUBLE PRECISION NOT NULL,
    commission  DOUBLE PRECISION NOT NULL DEFAULT 0,
    pnl         DOUBLE PRECISION,
    timestamp   TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_trades_run_id ON trades(run_id);`
}
```

同时重命名原 `buildCreateTableSQL` 为 `buildBarsTableSQL`，并更新 `buildInsertSQL` 等引用处。

- [ ] **Step 4: Run tests**

```powershell
cd services/go
go test ./internal/db/ -v -count=1 -run TestBuild
```
Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add services/go/internal/db/timescale.go services/go/internal/db/timescale_test.go
git commit -m "feat(db): add backtest_runs, equity_curves, trades schema to InitSchema"
```

---

### Task 3: PostgresBacktestStore

**Files:**
- Create: `services/go/internal/db/backtest.go`
- Create: `services/go/internal/db/backtest_test.go`

**Interfaces:**
- Consumes: `BacktestRepository` 接口（Task 1），`engine.BacktestResult` / `EquityPoint` / `TradeRecord`
- Produces: `PostgresBacktestStore` 实现 `BacktestRepository`

- [ ] **Step 1: 写测试**

由于 PostgresBacktestStore 需要真实 DB 连接，测试在无 DB 环境通过 `testing.Short()` 跳过。但我们可以写 SQL 构建函数的单元测试。

```go
// services/go/internal/db/backtest_test.go
package db

import (
	"testing"
	"time"

	"github.com/astockpursue/go-core/internal/engine"
	"github.com/google/uuid"
	"github.com/stretchr/testify/assert"
)

func TestBuildInsertBacktestRunSQL(t *testing.T) {
	store := &PostgresBacktestStore{}
	sql := store.buildInsertRunSQL()
	assert.Contains(t, sql, "INSERT INTO backtest_runs")
	assert.Contains(t, sql, "RETURNING id")
}

func TestBuildInsertEquitySQL(t *testing.T) {
	store := &PostgresBacktestStore{}
	sql := store.buildInsertEquitySQL()
	assert.Contains(t, sql, "INSERT INTO equity_curves")
}

func TestBuildInsertTradesSQL(t *testing.T) {
	store := &PostgresBacktestStore{}
	sql := store.buildInsertTradesSQL()
	assert.Contains(t, sql, "INSERT INTO trades")
}

func TestBuildGetRunSQL(t *testing.T) {
	store := &PostgresBacktestStore{}
	sql := store.buildGetRunSQL()
	assert.Contains(t, sql, "symbols")
	assert.Contains(t, sql, "frequency")
	assert.Contains(t, sql, "FROM backtest_runs")
}

func TestBuildGetEquitySQL(t *testing.T) {
	store := &PostgresBacktestStore{}
	sql := store.buildGetEquitySQL()
	assert.Contains(t, sql, "FROM equity_curves")
	assert.Contains(t, sql, "ORDER BY timestamp")
}

func TestBuildGetTradesSQL(t *testing.T) {
	store := &PostgresBacktestStore{}
	sql := store.buildGetTradesSQL()
	assert.Contains(t, sql, "FROM trades")
	assert.Contains(t, sql, "ORDER BY timestamp")
}

func TestBuildListRunsSQL(t *testing.T) {
	store := &PostgresBacktestStore{}
	sql := store.buildListRunsSQL()
	assert.Contains(t, sql, "SELECT id FROM backtest_runs")
	assert.Contains(t, sql, "ORDER BY created_at DESC")
}

func TestNewPostgresBacktestStoreNilPool(t *testing.T) {
	if testing.Short() {
		t.Skip("skipping integration test")
	}
	store := NewPostgresBacktestStore(nil)
	assert.NotNil(t, store)
}
```

- [ ] **Step 2: Run to fail**

```powershell
cd services/go
go test ./internal/db/ -v -count=1 -run TestBuildInsert|TestBuildGet|TestBuildList|TestNewPostgres
```
Expected: FAIL — PostgresBacktestStore not defined

- [ ] **Step 3: 实现 PostgresBacktestStore**

```go
// services/go/internal/db/backtest.go
package db

import (
	"context"
	"fmt"
	"time"

	"github.com/astockpursue/go-core/internal/engine"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
)

type PostgresBacktestStore struct {
	pool *pgxpool.Pool
}

func NewPostgresBacktestStore(pool *pgxpool.Pool) *PostgresBacktestStore {
	return &PostgresBacktestStore{pool: pool}
}

func (s *PostgresBacktestStore) Save(ctx context.Context, result *engine.BacktestResult) (string, error) {
	id := uuid.New().String()
	
	_, err := s.pool.Exec(ctx, s.buildInsertRunSQL(),
		id, result.StartTime, result.EndTime, // ... 所有字段
	)
	if err != nil {
		return "", fmt.Errorf("insert backtest run: %w", err)
	}

	if err := s.insertEquityPoints(ctx, id, result.EquityCurve); err != nil {
		return "", err
	}

	if err := s.insertTrades(ctx, id, result.Trades); err != nil {
		return "", err
	}

	return id, nil
}

// ... (完整实现在实施时写出)
```

完整代码：

```go
package db

import (
	"context"
	"fmt"
	"time"

	"github.com/astockpursue/go-core/internal/engine"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type PostgresBacktestStore struct {
	pool *pgxpool.Pool
}

func NewPostgresBacktestStore(pool *pgxpool.Pool) *PostgresBacktestStore {
	return &PostgresBacktestStore{pool: pool}
}

func (s *PostgresBacktestStore) Save(ctx context.Context, result *engine.BacktestResult) (string, error) {
	id := uuid.New().String()

	_, err := s.pool.Exec(ctx, s.buildInsertRunSQL(),
		id, result.Symbols, result.Frequency,
		result.StartTime, result.EndTime,
		result.InitialCash, result.FinalEquity,
		result.TotalReturn, result.SharpeRatio,
		result.MaxDrawdown, result.MaxDrawdownPct,
		result.WinRate, result.TotalTrades,
		result.WinningTrades, result.LosingTrades,
	)
	if err != nil {
		return "", fmt.Errorf("insert backtest run: %w", err)
	}

	if len(result.EquityCurve) > 0 {
		batch := &pgx.Batch{}
		for _, ep := range result.EquityCurve {
			batch.Queue(s.buildInsertEquitySQL(), id, ep.Timestamp, ep.Equity, ep.Cash, ep.PositionCount)
		}
		br := s.pool.SendBatch(ctx, batch)
		defer br.Close()
		if _, err := br.Exec(); err != nil {
			return "", fmt.Errorf("insert equity curves: %w", err)
		}
	}

	if len(result.Trades) > 0 {
		batch := &pgx.Batch{}
		for _, t := range result.Trades {
			tradeID := uuid.New().String()
			batch.Queue(s.buildInsertTradesSQL(),
				tradeID, id, t.Symbol, string(t.Side),
				t.Quantity, t.Price, t.Commission, t.PnL, t.Timestamp,
			)
		}
		br := s.pool.SendBatch(ctx, batch)
		defer br.Close()
		if _, err := br.Exec(); err != nil {
			return "", fmt.Errorf("insert trades: %w", err)
		}
	}

	return id, nil
}

func (s *PostgresBacktestStore) Get(ctx context.Context, id string) (*engine.BacktestResult, error) {
	result := &engine.BacktestResult{}

	row := s.pool.QueryRow(ctx, s.buildGetRunSQL(), id)
	err := row.Scan(
		&result.Symbols, &result.Frequency,
		&result.StartTime, &result.EndTime,
		&result.InitialCash, &result.FinalEquity,
		&result.TotalReturn, &result.SharpeRatio,
		&result.MaxDrawdown, &result.MaxDrawdownPct,
		&result.WinRate, &result.TotalTrades,
		&result.WinningTrades, &result.LosingTrades,
	)
	if err != nil {
		if err == pgx.ErrNoRows {
			return nil, fmt.Errorf("backtest result not found: %s", id)
		}
		return nil, fmt.Errorf("query backtest run: %w", err)
	}

	rows, err := s.pool.Query(ctx, s.buildGetEquitySQL(), id)
	if err != nil {
		return nil, fmt.Errorf("query equity curve: %w", err)
	}
	defer rows.Close()
	for rows.Next() {
		var ep engine.EquityPoint
		if err := rows.Scan(&ep.Timestamp, &ep.Equity, &ep.Cash, &ep.PositionCount); err != nil {
			return nil, fmt.Errorf("scan equity point: %w", err)
		}
		result.EquityCurve = append(result.EquityCurve, ep)
	}

	tRows, err := s.pool.Query(ctx, s.buildGetTradesSQL(), id)
	if err != nil {
		return nil, fmt.Errorf("query trades: %w", err)
	}
	defer tRows.Close()
	for tRows.Next() {
		var t engine.TradeRecord
		if err := tRows.Scan(&t.Symbol, &t.Side, &t.Quantity, &t.Price, &t.Commission, &t.PnL, &t.Timestamp); err != nil {
			return nil, fmt.Errorf("scan trade: %w", err)
		}
		result.Trades = append(result.Trades, t)
	}

	return result, nil
}

func (s *PostgresBacktestStore) List(ctx context.Context) ([]string, error) {
	rows, err := s.pool.Query(ctx, s.buildListRunsSQL())
	if err != nil {
		return nil, fmt.Errorf("list backtest runs: %w", err)
	}
	defer rows.Close()
	var ids []string
	for rows.Next() {
		var id string
		if err := rows.Scan(&id); err != nil {
			return nil, fmt.Errorf("scan id: %w", err)
		}
		ids = append(ids, id)
	}
	return ids, nil
}

func (s *PostgresBacktestStore) buildInsertRunSQL() string {
	return `INSERT INTO backtest_runs (
		id, symbols, frequency, start_date, end_date,
		initial_cash, final_equity,
		total_return, sharpe_ratio,
		max_drawdown, max_drawdown_pct,
		win_rate, total_trades, winning_trades, losing_trades
	) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)`
}

func (s *PostgresBacktestStore) buildInsertEquitySQL() string {
	return `INSERT INTO equity_curves (run_id, timestamp, equity, cash, position_count) VALUES ($1,$2,$3,$4,$5)`
}

func (s *PostgresBacktestStore) buildInsertTradesSQL() string {
	return `INSERT INTO trades (id, run_id, symbol, side, quantity, price, commission, pnl, timestamp) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)`
}

func (s *PostgresBacktestStore) buildGetRunSQL() string {
	return `SELECT symbols, frequency, start_date, end_date, initial_cash, final_equity, total_return, sharpe_ratio, max_drawdown, max_drawdown_pct, win_rate, total_trades, winning_trades, losing_trades FROM backtest_runs WHERE id = $1`
}

func (s *PostgresBacktestStore) buildGetEquitySQL() string {
	return `SELECT timestamp, equity, cash, position_count FROM equity_curves WHERE run_id = $1 ORDER BY timestamp ASC`
}

func (s *PostgresBacktestStore) buildGetTradesSQL() string {
	return `SELECT symbol, side, quantity, price, commission, pnl, timestamp FROM trades WHERE run_id = $1 ORDER BY timestamp ASC`
}

func (s *PostgresBacktestStore) buildListRunsSQL() string {
	return `SELECT id FROM backtest_runs ORDER BY created_at DESC`
}
```

注意：需要在 PostgresBacktestStore 中添加 `symbols` 和 `frequency` 字段的读写支持。但 engine.BacktestResult 结构体当前没有 Symbols 字段。我们需要在 BacktestResult 中增加 Symbols 和 Frequency 字段，或者在 handler 层面存储。

- [ ] **Step 3.5: 在 BacktestResult 中补充 Symbols/Frequency 字段**

```go
// services/go/internal/engine/backtest.go
// 在 BacktestResult struct 中追加
type BacktestResult struct {
    // ... 已有字段
    Symbols   []string `json:"symbols"`
    Frequency string   `json:"frequency"`
}
```

在 `BacktestRunner.Run` 返回 result 前填充：
```go
// backtest.go — Run() 末尾，calculateMetrics 返回后
result.Symbols = symbols
result.Frequency = freq
return result, nil
```

- [ ] **Step 4: Run tests**

```powershell
cd services/go
go test ./internal/db/ -v -count=1 -run TestBuildInsert|TestBuildGet|TestBuildList|TestNewPostgres
```
Expected: PASS

```powershell
cd services/go
go build ./...
```
Expected: no errors

- [ ] **Step 5: Commit**

```powershell
git add services/go/internal/db/backtest.go services/go/internal/db/backtest_test.go services/go/internal/engine/backtest.go services/go/internal/engine/backtest_test.go
git commit -m "feat(db): add PostgresBacktestStore implementing BacktestRepository"
```

---

### Task 4: 更新 main.go 依赖注入

**Files:**
- Modify: `services/go/cmd/server/main.go`

**Interfaces:**
- Consumes: `PostgresBacktestStore`（Task 3），`MemoryBacktestStore`（Task 1），Config
- Produces: 根据 DB 可用性选择 Repository 实现

- [ ] **Step 1: 写测试**（main.go 为可运行入口，无需单元测试，改为构建验证）

- [ ] **Step 2: 更新 main.go**

```go
package main

import (
	"context"
	"log"
	"time"

	"github.com/astockpursue/go-core/internal/api"
	"github.com/astockpursue/go-core/internal/api/handler"
	"github.com/astockpursue/go-core/internal/config"
	"github.com/astockpursue/go-core/internal/db"
	"github.com/astockpursue/go-core/internal/engine"
	"github.com/astockpursue/go-core/internal/market"
)

func main() {
	cfg := config.Load()

	factory := engine.NewEngineFactory()
	cache := market.NewMemoryCache(5 * time.Minute)
	ds := market.NewDataStore(nil, cache)

	var repo handler.BacktestRepository
	timescaleDB, err := db.NewTimescaleDB(context.Background(), cfg.DatabaseURL)
	if err != nil {
		log.Printf("DB unavailable, using in-memory backtest store: %v", err)
		repo = handler.NewBacktestStore()
	} else {
		defer timescaleDB.Close()
		if err := timescaleDB.InitSchema(context.Background()); err != nil {
			log.Fatalf("init schema: %v", err)
		}
		repo = db.NewPostgresBacktestStore(timescaleDB)
		log.Print("DB connected, using PostgreSQL backtest store")
	}

	btHandler := handler.NewBacktestHandler(repo, ds, factory)

	pipeline := &engine.Pipeline{
		Engine:    factory.ForSymbol("000001"),
		Portfolio: &engine.Portfolio{
			Cash:      100000,
			Equity:    100000,
			Positions: make(map[string]*engine.Position),
		},
		Signal:   engine.NewNoopSignalAdapter(),
		Risk:     engine.NewRiskManager(engine.RiskConfig{}),
		LastBars: make(map[string]interface{}),
	}
	runner := engine.NewLiveTradingRunner(pipeline, 1*time.Minute)
	trHandler := handler.NewTradingHandler(runner)

	healthH := &handler.HealthHandler{}
	r := api.NewRouter(healthH, btHandler, trHandler)

	log.Printf("Starting go-core on :%s", cfg.Port)
	r.Run(":" + cfg.Port)
}
```

- [ ] **Step 3: 构建验证**

```powershell
cd services/go
go build ./...
```
Expected: no errors

```powershell
cd services/go
go test ./...
```
Expected: all tests pass (db package TestNewTimescaleDB or similar skips due to short mode, but SQL template tests pass)

- [ ] **Step 4: commit**

```powershell
git add services/go/cmd/server/main.go
git commit -m "feat(server): wire PostgresBacktestStore or MemoryBacktestStore based on DB availability"
```

---

## 自审

1. **Spec 覆盖：**
   - 3 张表结构 → Task 2 (schema) + Task 3 (读写)
   - Repository 接口 → Task 1
   - MemoryStore 改接口实现 → Task 1
   - PostgresStore → Task 3
   - main.go 依赖注入 → Task 4
   - UUID v4 → Task 1 (MemoryStore) + Task 3 (PostgresStore)
   - equity_curves hypertable → Task 2

2. **占位符检查：** 无 "TBD"、"TODO"

3. **类型一致性：** BacktestRepository 接口的 Save 返回 `(string, error)`，Get 返回 `(*engine.BacktestResult, error)`，在 Task 1 和 Task 3 中保持一致。
