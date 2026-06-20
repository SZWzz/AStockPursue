package engine

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func newTestForex() *ForexEngine {
	return &ForexEngine{
		SpreadMajor: 0.0002,
		SpreadMinor: 0.0005,
		Slippage:    0.0001,
		Leverage:    30,
		LotSize:     100000,
	}
}

func TestForexName(t *testing.T) {
	e := newTestForex()
	assert.Equal(t, "forex", e.Name())
}

func TestForexRoundSize(t *testing.T) {
	e := newTestForex()
	assert.Equal(t, 0.01, e.RoundSize(0.015))
	assert.Equal(t, 1.0, e.RoundSize(1.0))
}

func TestForexCommissionZero(t *testing.T) {
	e := newTestForex()
	order := &Order{Quantity: 1, Price: 1.1}
	assert.Equal(t, 0.0, e.CalcCommission(order))
}

func TestForexMarginStandardLot(t *testing.T) {
	e := newTestForex()
	pos := &Position{Size: 1, CurrentPrice: 1.1}
	assert.InDelta(t, 3666.67, e.CalcMargin(pos), 0.01)
}

func TestForexMarginShort(t *testing.T) {
	e := newTestForex()
	pos := &Position{Size: -1, CurrentPrice: 1.1}
	assert.InDelta(t, 3666.67, e.CalcMargin(pos), 0.01)
}

func TestForexPnLLong(t *testing.T) {
	e := newTestForex()
	pos := &Position{Size: 1, EntryPrice: 1.1000, CurrentPrice: 1.1100}
	assert.InDelta(t, 1000.0, e.CalcPnL(pos), 0.01)
}

func TestForexPnLShort(t *testing.T) {
	e := newTestForex()
	pos := &Position{Size: -1, EntryPrice: 1.1000, CurrentPrice: 1.0900}
	assert.InDelta(t, 1000.0, e.CalcPnL(pos), 0.01)
}

func TestForexCanExecute(t *testing.T) {
	e := newTestForex()
	assert.True(t, e.CanExecute(&Order{Quantity: 1, Side: Buy}))
	assert.True(t, e.CanExecute(&Order{Quantity: 1, Side: Sell}))
}

func TestForexSlippageBuy(t *testing.T) {
	e := newTestForex()
	price := e.ApplySlippage(&Order{Side: Buy}, &Bar{Close: 1.1000})
	assert.InDelta(t, 1.1001, price, 0.0001)
}

func TestForexSlippageSell(t *testing.T) {
	e := newTestForex()
	price := e.ApplySlippage(&Order{Side: Sell}, &Bar{Close: 1.1000})
	assert.InDelta(t, 1.0999, price, 0.0001)
}

func TestForexSpread(t *testing.T) {
	e := newTestForex()
	assert.NotNil(t, e)
	assert.Equal(t, 0.0002, e.SpreadMajor)
	assert.Equal(t, 0.0005, e.SpreadMinor)
}
