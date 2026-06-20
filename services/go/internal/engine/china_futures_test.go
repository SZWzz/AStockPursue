package engine

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestChinaFuturesIF(t *testing.T) {
	e := NewChinaFuturesEngine("IF")
	if assert.NotNil(t, e) {
		assert.Equal(t, 300.0, e.ContractMultiplier)
		assert.Equal(t, 0.12, e.MarginRate)
	}
}

func TestChinaFuturesIC(t *testing.T) {
	e := NewChinaFuturesEngine("IC")
	if assert.NotNil(t, e) {
		assert.Equal(t, 200.0, e.ContractMultiplier)
		assert.Equal(t, 0.12, e.MarginRate)
	}
}

func TestChinaFuturesCommission(t *testing.T) {
	e := NewChinaFuturesEngine("IF")
	if assert.NotNil(t, e) {
		order := &Order{Quantity: 1, Price: 5000}
		comm := e.CalcCommission(order)
		assert.InDelta(t, 34.5, comm, 0.01)
	}
}

func TestChinaFuturesMargin(t *testing.T) {
	e := NewChinaFuturesEngine("IF")
	if assert.NotNil(t, e) {
		pos := &Position{Size: 1, CurrentPrice: 5000}
		margin := e.CalcMargin(pos)
		assert.InDelta(t, 180000.0, margin, 0.01)
	}
}

func TestChinaFuturesPnL(t *testing.T) {
	e := NewChinaFuturesEngine("IF")
	if assert.NotNil(t, e) {
		pos := &Position{Size: 1, EntryPrice: 4000, CurrentPrice: 5000}
		pnl := e.CalcPnL(pos)
		assert.InDelta(t, 300000.0, pnl, 0.01)
	}
}

func TestChinaFuturesRoundSize(t *testing.T) {
	e := NewChinaFuturesEngine("IF")
	if assert.NotNil(t, e) {
		assert.InDelta(t, 1.0, e.RoundSize(1.0), 0.01)
		assert.InDelta(t, 0.0, e.RoundSize(0.5), 0.01)
	}
}

func TestChinaFuturesSlippage(t *testing.T) {
	e := NewChinaFuturesEngine("IF")
	if assert.NotNil(t, e) {
		price := e.ApplySlippage(&Order{Side: Buy}, &Bar{Close: 5000})
		assert.InDelta(t, 5000.2, price, 0.01)
	}
}

func TestChinaFuturesCanExecute(t *testing.T) {
	e := NewChinaFuturesEngine("IF")
	if assert.NotNil(t, e) {
		assert.True(t, e.CanExecute(&Order{Quantity: 1, Side: Buy}))
		assert.True(t, e.CanExecute(&Order{Quantity: 1, Side: Sell}))
	}
}

func TestChinaFuturesName(t *testing.T) {
	e := NewChinaFuturesEngine("IF")
	if assert.NotNil(t, e) {
		assert.Equal(t, "china_futures", e.Name())
	}
}

func TestChinaFuturesUnknownSymbol(t *testing.T) {
	e := NewChinaFuturesEngine("UNKNOWN")
	assert.Nil(t, e)
}
