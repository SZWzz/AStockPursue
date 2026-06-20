package engine

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestGlobalFuturesES(t *testing.T) {
	e := NewGlobalFuturesEngine("ES")
	assert.NotNil(t, e)
	assert.InDelta(t, 50, e.ContractMultiplier, 0.01)
}

func TestGlobalFuturesNQ(t *testing.T) {
	e := NewGlobalFuturesEngine("NQ")
	assert.NotNil(t, e)
	assert.InDelta(t, 20, e.ContractMultiplier, 0.01)
}

func TestGlobalFuturesCommissionES(t *testing.T) {
	e := NewGlobalFuturesEngine("ES")
	assert.NotNil(t, e)
	comm := e.CalcCommission(&Order{Quantity: 1, Price: 5000})
	assert.InDelta(t, 2.50, comm, 0.01)
}

func TestGlobalFuturesMarginES(t *testing.T) {
	e := NewGlobalFuturesEngine("ES")
	assert.NotNil(t, e)
	margin := e.CalcMargin(&Position{Size: 1, CurrentPrice: 5000})
	assert.InDelta(t, 12500, margin, 0.01)
}

func TestGlobalFuturesPnL(t *testing.T) {
	e := NewGlobalFuturesEngine("ES")
	assert.NotNil(t, e)
	pnl := e.CalcPnL(&Position{Size: 1, EntryPrice: 4900, CurrentPrice: 5000})
	assert.InDelta(t, 5000, pnl, 0.01)
}

func TestGlobalFuturesRoundSize(t *testing.T) {
	e := NewGlobalFuturesEngine("ES")
	assert.NotNil(t, e)
	assert.InDelta(t, 1.0, e.RoundSize(1), 0.01)
}

func TestGlobalFuturesSlippage(t *testing.T) {
	e := NewGlobalFuturesEngine("ES")
	assert.NotNil(t, e)
	price := e.ApplySlippage(&Order{Side: Buy}, &Bar{Close: 5000})
	assert.InDelta(t, 5000.25, price, 0.01)
}

func TestGlobalFuturesCanExecute(t *testing.T) {
	e := NewGlobalFuturesEngine("ES")
	assert.NotNil(t, e)
	assert.True(t, e.CanExecute(&Order{Quantity: 1, Side: Buy}))
	assert.True(t, e.CanExecute(&Order{Quantity: 1, Side: Sell}))
}

func TestGlobalFuturesName(t *testing.T) {
	e := NewGlobalFuturesEngine("ES")
	assert.NotNil(t, e)
	assert.Equal(t, "global_futures", e.Name())
}

func TestGlobalFuturesUnknownSymbol(t *testing.T) {
	e := NewGlobalFuturesEngine("UNKNOWN")
	assert.Nil(t, e)
}
