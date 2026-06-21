package engine

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestStopLossTrigger(t *testing.T) {
	r := NewRiskManager(RiskConfig{StopLossPercent: 5.0})
	portfolio := &Portfolio{Positions: map[string]*Position{
		"000001": {Symbol: "000001", Size: 100, EntryPrice: 10.0},
	}}
	orders := r.CheckExits(portfolio, &Bar{Symbol: "000001", Close: 9.0})
	assert.Equal(t, 1, len(orders))
	assert.Equal(t, Sell, orders[0].Side)
}

func TestStopLossNotTriggered(t *testing.T) {
	r := NewRiskManager(RiskConfig{StopLossPercent: 5.0})
	portfolio := &Portfolio{Positions: map[string]*Position{
		"000001": {Symbol: "000001", Size: 100, EntryPrice: 10.0},
	}}
	orders := r.CheckExits(portfolio, &Bar{Symbol: "000001", Close: 9.8})
	assert.Equal(t, 0, len(orders))
}

func TestTakeProfitTrigger(t *testing.T) {
	r := NewRiskManager(RiskConfig{TakeProfitPercent: 10.0})
	portfolio := &Portfolio{Positions: map[string]*Position{
		"000001": {Symbol: "000001", Size: 100, EntryPrice: 10.0},
	}}
	orders := r.CheckExits(portfolio, &Bar{Symbol: "000001", Close: 12.0})
	assert.Equal(t, 1, len(orders))
	assert.Equal(t, Sell, orders[0].Side)
}

func TestTrailingStopTrigger(t *testing.T) {
	r := NewRiskManager(RiskConfig{TrailingStopPercent: 5.0})
	portfolio := &Portfolio{Positions: map[string]*Position{
		"000001": {Symbol: "000001", Size: 100, EntryPrice: 10.0},
	}}
	orders := r.CheckExits(portfolio, &Bar{Symbol: "000001", Close: 11.0})
	assert.Equal(t, 0, len(orders), "price up, trailing not triggered")

	orders = r.CheckExits(portfolio, &Bar{Symbol: "000001", Close: 10.2})
	assert.Equal(t, 1, len(orders), "price dropped more than 5% from high of 11")
}

func TestTrailingStopNotTriggeredOnSmallDrop(t *testing.T) {
	r := NewRiskManager(RiskConfig{TrailingStopPercent: 5.0})
	portfolio := &Portfolio{Positions: map[string]*Position{
		"000001": {Symbol: "000001", Size: 100, EntryPrice: 10.0},
	}}
	orders := r.CheckExits(portfolio, &Bar{Symbol: "000001", Close: 11.0})
	assert.Equal(t, 0, len(orders))

	orders = r.CheckExits(portfolio, &Bar{Symbol: "000001", Close: 10.6})
	assert.Equal(t, 0, len(orders), "only 3.6% drop, below 5% trailing threshold")
}

func TestNoRiskConfig(t *testing.T) {
	r := NewRiskManager(RiskConfig{})
	portfolio := &Portfolio{Positions: map[string]*Position{
		"000001": {Symbol: "000001", Size: 100, EntryPrice: 10.0},
	}}
	orders := r.CheckExits(portfolio, &Bar{Symbol: "000001", Close: 5.0})
	assert.Equal(t, 0, len(orders), "no risk config means no exits")
}

func newTestPortfolio(cash, equity float64, positions map[string]*Position) *Portfolio {
	if positions == nil {
		positions = make(map[string]*Position)
	}
	return &Portfolio{
		Cash:      cash,
		Equity:    equity,
		Positions: positions,
	}
}

func newTestPosition(symbol string, qty, avgCost, lastPrice float64) *Position {
	return &Position{
		Symbol:       symbol,
		Size:         qty,
		EntryPrice:   avgCost,
		CurrentPrice: lastPrice,
	}
}

func TestStopLossClose(t *testing.T) {
	rm := NewRiskManager(RiskConfig{StopLossPercent: 5.0})
	pos := newTestPosition("000001.SZ", 1000, 10.0, 9.4)
	pf := newTestPortfolio(0, 100000, map[string]*Position{"000001.SZ": pos})

	orders := rm.CheckExits(pf, &Bar{Symbol: "000001.SZ", Close: 9.4})
	if len(orders) == 0 {
		t.Error("expected risk exit for stop-loss breach")
	}
	if orders[0].Side != Sell {
		t.Error("expected sell order for stop-loss")
	}
}

func TestTakeProfitClose(t *testing.T) {
	rm := NewRiskManager(RiskConfig{TakeProfitPercent: 10.0})
	pos := newTestPosition("000001.SZ", 1000, 10.0, 11.1)
	pf := newTestPortfolio(0, 100000, map[string]*Position{"000001.SZ": pos})

	orders := rm.CheckExits(pf, &Bar{Symbol: "000001.SZ", Close: 11.1})
	if len(orders) == 0 {
		t.Error("expected risk exit for take-profit breach")
	}
}

func TestTrailingStopClose(t *testing.T) {
	rm := NewRiskManager(RiskConfig{TrailingStopPercent: 3.0})
	pos := newTestPosition("000001.SZ", 1000, 10.0, 9.5)
	pf := newTestPortfolio(0, 100000, map[string]*Position{"000001.SZ": pos})
	// pre-set high water mark to simulate peak at 11.0
	rm.HighWaterMarks["000001.SZ"] = 11.0

	orders := rm.CheckExits(pf, &Bar{Symbol: "000001.SZ", Close: 9.5})
	if len(orders) == 0 {
		t.Error("expected risk exit for trailing-stop breach")
	}
}

func TestDayLossLimit(t *testing.T) {
	rm := NewRiskManager(RiskConfig{DayLossLimit: 1000})
	pos := newTestPosition("000001.SZ", 1000, 10.0, 9.0) // -1000 unrealized loss
	pf := newTestPortfolio(90000, 99000, map[string]*Position{"000001.SZ": pos})
	// Started with 100000, spent 10000 on position, now worth 9000 → loss=1000
	pf.InitialEquity = 100000

	accepted := !rm.BlockNewSignals(pf)
	if accepted {
		t.Error("expected new signals blocked when day loss limit reached")
	}
}

func TestMaxPositionCount(t *testing.T) {
	rm := NewRiskManager(RiskConfig{MaxPositionCount: 2})
	pf := newTestPortfolio(0, 100000, map[string]*Position{
		"000001.SZ": newTestPosition("000001.SZ", 100, 10.0, 10.0),
		"600519.SH": newTestPosition("600519.SH", 100, 1680.0, 1680.0),
		"600036.SH": newTestPosition("600036.SH", 100, 38.0, 38.0),
	})

	accepted := !rm.BlockNewSignals(pf)
	if accepted {
		t.Error("expected new signals blocked when position count exceeds limit")
	}
}

func TestRiskConfigZeroDefaultsSafe(t *testing.T) {
	rm := NewRiskManager(RiskConfig{})
	pf := newTestPortfolio(0, 100000, nil)

	if rm.BlockNewSignals(pf) {
		t.Error("zero/default config should not block signals")
	}
}
