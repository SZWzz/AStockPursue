package engine

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func newTestUSEq() *GlobalEquityEngine {
	return &GlobalEquityEngine{
		Market:         "US",
		PerShareComm:   0.005,
		MinCommission:  1.0,
		StampDutyRate:  0,
		Slippage:       0.001,
		CanShort:       true,
	}
}

func newTestHKEq() *GlobalEquityEngine {
	return &GlobalEquityEngine{
		Market:         "HK",
		CommissionRate: 0.0025,
		MinCommission:  100,
		StampDutyRate:  0.0013,
		Slippage:       0.001,
		CanShort:       false,
	}
}

func TestGlobalEquityName(t *testing.T) {
	e := &GlobalEquityEngine{}
	assert.Equal(t, "global_equity", e.Name())
}

func TestGlobalEquityUSCommission(t *testing.T) {
	e := newTestUSEq()
	order := &Order{Quantity: 1000, Price: 200, Side: Buy}
	assert.InDelta(t, 5.0, e.CalcCommission(order), 0.01)
}

func TestGlobalEquityUSMinCommission(t *testing.T) {
	e := newTestUSEq()
	order := &Order{Quantity: 10, Price: 10, Side: Buy}
	assert.InDelta(t, 1.0, e.CalcCommission(order), 0.01)
}

func TestGlobalEquityHKCommission(t *testing.T) {
	e := newTestHKEq()
	order := &Order{Quantity: 1000, Price: 100, Side: Buy}
	assert.InDelta(t, 250.0, e.CalcCommission(order), 0.01)
}

func TestGlobalEquityHKStampDuty(t *testing.T) {
	e := newTestHKEq()
	order := &Order{Quantity: 1000, Price: 100, Side: Sell}
	assert.InDelta(t, 380.0, e.CalcCommission(order), 0.01)
}

func TestGlobalEquityRoundSize(t *testing.T) {
	e := &GlobalEquityEngine{}
	assert.Equal(t, 1.0, e.RoundSize(1.0))
	assert.Equal(t, 100.0, e.RoundSize(100.0))
}

func TestGlobalEquityUSCanShort(t *testing.T) {
	e := newTestUSEq()
	assert.True(t, e.CanExecute(&Order{Quantity: 100, Side: Sell}))
}

func TestGlobalEquityHKCannotShort(t *testing.T) {
	e := newTestHKEq()
	assert.False(t, e.CanExecute(&Order{Quantity: 100, Side: Sell}))
}

func TestGlobalEquityCanExecuteBuy(t *testing.T) {
	e := &GlobalEquityEngine{}
	assert.True(t, e.CanExecute(&Order{Quantity: 100, Side: Buy}))
}

func TestGlobalEquitySlippage(t *testing.T) {
	e := newTestUSEq()
	price := e.ApplySlippage(&Order{Side: Buy}, &Bar{Close: 100.0})
	assert.InDelta(t, 100.1, price, 0.01)
}

func TestGlobalEquityPnL(t *testing.T) {
	e := &GlobalEquityEngine{}
	pnl := e.CalcPnL(&Position{Size: 100, EntryPrice: 90, CurrentPrice: 100})
	assert.InDelta(t, 1000.0, pnl, 0.01)
}

func TestGlobalEquityMargin(t *testing.T) {
	e := &GlobalEquityEngine{}
	margin := e.CalcMargin(&Position{Size: 100, CurrentPrice: 100})
	assert.InDelta(t, 5000.0, margin, 0.01)
}

func TestGlobalEquityShortMargin(t *testing.T) {
	e := &GlobalEquityEngine{}
	margin := e.CalcMargin(&Position{Size: -100, CurrentPrice: 100})
	assert.InDelta(t, 15000.0, margin, 0.01)
}
