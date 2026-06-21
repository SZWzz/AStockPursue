package engine

import (
	"fmt"
	"testing"
	"time"
)

// MockEngine implements the Engine interface for testing.
type MockEngine struct{}

func (m *MockEngine) Name() string                                { return "mock" }
func (m *MockEngine) CanExecute(order *Order) bool                 { return true }
func (m *MockEngine) RoundSize(size float64) float64               { return float64(int(size)) }
func (m *MockEngine) CalcCommission(order *Order) float64          { return 5.0 }
func (m *MockEngine) ApplySlippage(order *Order, bar interface{}) float64 {
	if b, ok := bar.(*Bar); ok {
		return b.Close
	}
	return order.Price
}
func (m *MockEngine) CalcMargin(position *Position) float64        { return 0 }
func (m *MockEngine) CalcPnL(position *Position) float64           { return position.UnrealizedPnL() }

// MockSignalGenerator implements SignalGenerator for testing.
type MockSignalGenerator struct {
	weights map[string]float64
	err     error
}

func (m *MockSignalGenerator) Generate(bars []interface{}, ts time.Time) (map[string]float64, error) {
	return m.weights, m.err
}

// --- Legacy mock types used by backtest_test.go ---
type mockSignalAdapter struct {
	called bool
	weight map[string]float64
	err    error
}

func (m *mockSignalAdapter) Generate(bars []interface{}, ts time.Time) (map[string]float64, error) {
	m.called = true
	return m.weight, m.err
}

type mockRiskPipeline struct {
	called bool
	orders []*Order
}

func (m *mockRiskPipeline) CheckExits(portfolio *Portfolio, bar interface{}) []*Order {
	m.called = true
	return m.orders
}

type mockEngine struct {
	canExec     bool
	roundSizeFn func(float64) float64
	commFn      func(*Order) float64
}

func (m *mockEngine) Name() string                       { return "mock" }
func (m *mockEngine) CanExecute(order *Order) bool        { return m.canExec }
func (m *mockEngine) RoundSize(size float64) float64      { return m.roundSizeFn(size) }
func (m *mockEngine) CalcCommission(order *Order) float64 { return m.commFn(order) }
func (m *mockEngine) ApplySlippage(order *Order, bar interface{}) float64 {
	if b, ok := bar.(*Bar); ok {
		return b.Close
	}
	return order.Price
}
func (m *mockEngine) CalcMargin(position *Position) float64 { return 0 }
func (m *mockEngine) CalcPnL(position *Position) float64    { return 0 }

func defaultMockEngine() *mockEngine {
	return &mockEngine{
		canExec:     true,
		roundSizeFn: func(f float64) float64 { return f },
		commFn:      func(o *Order) float64 { return 0 },
	}
}

func TestPipelinePortfolioRollbackOnSignalFailure(t *testing.T) {
	engine := &MockEngine{}
	pf := &Portfolio{
		Cash:      100000,
		Equity:    100000,
		Positions: make(map[string]*Position),
	}
	risk := NewRiskManager(RiskConfig{})

	// Signal that will fail
	signal := &MockSignalGenerator{err: fmt.Errorf("mock signal failure")}
	om := NewOrderManager()

	pipeline := &Pipeline{
		Engine:    engine,
		Portfolio: pf,
		Signal:    signal,
		Risk:      risk,
		OM:        om,
		LastBars:  make(map[string]interface{}),
	}

	bar := &Bar{Symbol: "000001.SZ", Open: 10, High: 11, Low: 9, Close: 10.5, Volume: 1000000}

	// Signal failure should not mutate portfolio
	pipeline.OnBar(bar, time.Now())

	if pf.Cash != 100000 {
		t.Errorf("portfolio cash should not change on signal failure, got %f", pf.Cash)
	}
	if len(pf.Positions) != 0 {
		t.Errorf("positions should remain empty on signal failure, got %d positions", len(pf.Positions))
	}
}

func TestPipelineProcessOrdersNoSignal(t *testing.T) {
	engine := &MockEngine{}
	pf := &Portfolio{
		Cash:      100000,
		Equity:    100000,
		Positions: make(map[string]*Position),
	}
	risk := NewRiskManager(RiskConfig{})
	om := NewOrderManager()

	pipeline := &Pipeline{
		Engine:    engine,
		Portfolio: pf,
		Signal:    nil, // no signal configured
		Risk:      risk,
		OM:        om,
		LastBars:  make(map[string]interface{}),
	}

	bar := &Bar{Symbol: "000001.SZ", Open: 10, High: 11, Low: 9, Close: 10.5, Volume: 1000000}

	// Should not crash and portfolio stays at initial state
	pipeline.OnBar(bar, time.Now())

	if pf.Cash != 100000 {
		t.Errorf("portfolio cash should not change without signal, got %f", pf.Cash)
	}
}

func TestPipelineProcessOrdersWithWeights(t *testing.T) {
	engine := &MockEngine{}
	pf := &Portfolio{
		Cash:      100000,
		Equity:    100000,
		Positions: make(map[string]*Position),
	}
	risk := NewRiskManager(RiskConfig{})
	signal := &MockSignalGenerator{
		weights: map[string]float64{"000001.SZ": 0.5}, // 50% allocation
	}
	om := NewOrderManager()

	pipeline := &Pipeline{
		Engine:    engine,
		Portfolio: pf,
		Signal:    signal,
		Risk:      risk,
		OM:        om,
		LastBars:  make(map[string]interface{}),
	}

	bar := &Bar{Symbol: "000001.SZ", Open: 10, High: 11, Low: 9, Close: 10, Volume: 1000000}

	pipeline.OnBar(bar, time.Now())

	// With 50% allocation at price 10, should buy ~5000 shares
	// cost = 5000*10 = 50000, commission = 5
	// cash = 100000 - 50005 = 49995
	if pf.Cash >= 100000 {
		t.Error("portfolio cash should decrease after buy order")
	}
	if len(pf.Positions) != 1 {
		t.Fatalf("expected 1 position, got %d", len(pf.Positions))
	}
	pos, ok := pf.Positions["000001.SZ"]
	if !ok {
		t.Fatal("expected position for 000001.SZ")
	}
	if pos.Size <= 0 {
		t.Errorf("expected positive position size, got %f", pos.Size)
	}
}

func TestPipelineProcessOrdersWithSellSignal(t *testing.T) {
	engine := &MockEngine{}
	pf := &Portfolio{
		Cash: 50000,
		Positions: map[string]*Position{
			"000001.SZ": {Symbol: "000001.SZ", Size: 1000, EntryPrice: 10},
		},
		Equity: 60000,
	}
	risk := NewRiskManager(RiskConfig{})
	signal := &MockSignalGenerator{
		weights: map[string]float64{"000001.SZ": 0.2}, // reduce from ~16.6% to 20%
	}
	om := NewOrderManager()

	pipeline := &Pipeline{
		Engine:    engine,
		Portfolio: pf,
		Signal:    signal,
		Risk:      risk,
		OM:        om,
		LastBars:  make(map[string]interface{}),
	}

	bar := &Bar{Symbol: "000001.SZ", Open: 10, High: 11, Low: 9, Close: 10, Volume: 1000000}

	pipeline.OnBar(bar, time.Now())

	// Position should still exist (we should still have some shares after sell)
	if len(pf.Positions) == 0 {
		t.Error("position should still exist after partial sell")
	}
}

func TestPipelineOnBarWrongType(t *testing.T) {
	pipeline := &Pipeline{
		Engine:    &MockEngine{},
		Portfolio: &Portfolio{Cash: 100000, Equity: 100000, Positions: make(map[string]*Position)},
		Risk:      NewRiskManager(RiskConfig{}),
		OM:        NewOrderManager(),
		LastBars:  make(map[string]interface{}),
	}

	// Passing a non-*Bar should not panic
	pipeline.OnBar("not a bar", time.Now())

	// Should not crash
	if pipeline.Portfolio.Cash != 100000 {
		t.Error("portfolio should not change on invalid type")
	}
}

func TestPipelineRiskExitOrders(t *testing.T) {
	engine := &MockEngine{}
	risk := NewRiskManager(RiskConfig{StopLossPercent: 5.0})
	pf := &Portfolio{
		Cash: 50000,
		Positions: map[string]*Position{
			"000001.SZ": {Symbol: "000001.SZ", Size: 1000, EntryPrice: 10},
		},
		Equity: 60000,
	}
	om := NewOrderManager()

	pipeline := &Pipeline{
		Engine:    engine,
		Portfolio: pf,
		Signal:    nil, // no signal, only risk exits
		Risk:      risk,
		OM:        om,
		LastBars:  make(map[string]interface{}),
	}

	// Price drops below 5% stop loss (10 * 0.95 = 9.5)
	bar := &Bar{Symbol: "000001.SZ", Open: 9, High: 9.5, Low: 9, Close: 9.4, Volume: 1000000}

	pipeline.OnBar(bar, time.Now())

	// Position should be closed by stop loss
	// Check that the position is gone (size = 0 → deleted)
	if _, ok := pf.Positions["000001.SZ"]; ok {
		t.Error("position should be closed by stop loss exit order")
	}
	// Cash should have increased from the sell
	if pf.Cash <= 50000 {
		t.Errorf("cash should increase after stop loss sell, got %f", pf.Cash)
	}
}

func TestPipelineBlockNewSignals(t *testing.T) {
	engine := &MockEngine{}
	pf := &Portfolio{
		Cash:          90000,
		Equity:        99000,
		InitialEquity: 100000,
		Positions: map[string]*Position{
			"000001.SZ": {Symbol: "000001.SZ", Size: 1000, EntryPrice: 10, CurrentPrice: 9},
		},
	}
	// Day loss = 100000 - 99000 = 1000, with DayLossLimit = 1000 should block
	risk := NewRiskManager(RiskConfig{DayLossLimit: 1000})
	signal := &MockSignalGenerator{
		weights: map[string]float64{"600519.SH": 0.5},
	}
	om := NewOrderManager()

	pipeline := &Pipeline{
		Engine:    engine,
		Portfolio: pf,
		Signal:    signal,
		Risk:      risk,
		OM:        om,
		LastBars:  make(map[string]interface{}),
	}

	bar := &Bar{Symbol: "000001.SZ", Open: 9, High: 9.5, Low: 9, Close: 9, Volume: 1000000}

	// Save pre-state
	initialCash := pf.Cash
	initialPositions := len(pf.Positions)

	pipeline.OnBar(bar, time.Now())

	// Signals should be blocked, portfolio unchanged
	if pf.Cash != initialCash {
		t.Errorf("cash should not change when new signals blocked, was %f now %f", initialCash, pf.Cash)
	}
	if len(pf.Positions) != initialPositions {
		t.Errorf("position count should not change when new signals blocked, was %d now %d", initialPositions, len(pf.Positions))
	}
}

func TestPipelineEmptyWeights(t *testing.T) {
	engine := &MockEngine{}
	pf := &Portfolio{
		Cash:      100000,
		Equity:    100000,
		Positions: make(map[string]*Position),
	}
	risk := NewRiskManager(RiskConfig{})
	signal := &MockSignalGenerator{weights: map[string]float64{}} // empty weights
	om := NewOrderManager()

	pipeline := &Pipeline{
		Engine:    engine,
		Portfolio: pf,
		Signal:    signal,
		Risk:      risk,
		OM:        om,
		LastBars:  make(map[string]interface{}),
	}

	bar := &Bar{Symbol: "000001.SZ", Open: 10, High: 11, Low: 9, Close: 10.5, Volume: 1000000}

	pipeline.OnBar(bar, time.Now())

	// Empty weights should not change portfolio
	if pf.Cash != 100000 {
		t.Errorf("portfolio should not change with empty weights, cash=%f", pf.Cash)
	}
	if len(pf.Positions) != 0 {
		t.Errorf("no positions should be created with empty weights, got %d", len(pf.Positions))
	}
}

func TestPipelineEquityTracking(t *testing.T) {
	engine := &MockEngine{}
	pf := &Portfolio{
		Cash:      100000,
		Equity:    100000,
		Positions: make(map[string]*Position),
	}
	risk := NewRiskManager(RiskConfig{})
	signal := &MockSignalGenerator{
		weights: map[string]float64{"000001.SZ": 0.5},
	}
	om := NewOrderManager()

	pipeline := &Pipeline{
		Engine:    engine,
		Portfolio: pf,
		Signal:    signal,
		Risk:      risk,
		OM:        om,
		LastBars:  make(map[string]interface{}),
	}

	bar := &Bar{Symbol: "000001.SZ", Open: 10, High: 11, Low: 9, Close: 10, Volume: 1000000}

	pipeline.OnBar(bar, time.Now())

	// Equity should be updated after OnBar
	if pf.Equity <= 0 {
		t.Error("portfolio equity should be positive after processing")
	}
	// EquityCache should match the equity at the time of OnBar
	if pipeline.EquityCache != 100000 {
		t.Errorf("equity cache should be 100000, got %f", pipeline.EquityCache)
	}
}

func TestPipelineRollbackPreservesRiskExits(t *testing.T) {
	// When risk exits succeed but signal fails, portfolio should be rolled
	// back to the state BEFORE risk exits (snapshot)
	engine := &MockEngine{}
	risk := NewRiskManager(RiskConfig{StopLossPercent: 5.0})
	pf := &Portfolio{
		Cash: 50000,
		Positions: map[string]*Position{
			"000001.SZ": {Symbol: "000001.SZ", Size: 1000, EntryPrice: 10},
		},
		Equity: 60000,
	}
	// Signal that will fail
	signal := &MockSignalGenerator{err: fmt.Errorf("mock failure")}
	om := NewOrderManager()

	pipeline := &Pipeline{
		Engine:    engine,
		Portfolio: pf,
		Signal:    signal,
		Risk:      risk,
		OM:        om,
		LastBars:  make(map[string]interface{}),
	}

	bar := &Bar{Symbol: "000001.SZ", Open: 9, High: 9.5, Low: 9, Close: 9.4, Volume: 1000000}

	// Signal fails → portfolio rolls back to pre-risk-exit state
	pipeline.OnBar(bar, time.Now())

	// Position should still exist (rollback restored it)
	pos, ok := pf.Positions["000001.SZ"]
	if !ok {
		t.Error("position should be restored after signal failure rollback")
	} else if pos.Size != 1000 {
		t.Errorf("position size should be restored to 1000, got %f", pos.Size)
	}
	// Cash should also be restored
	if pf.Cash != 50000 {
		t.Errorf("cash should be restored to 50000, got %f", pf.Cash)
	}
}
