package engine

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestChinaACommission(t *testing.T) {
	e := &ChinaAEngine{}
	order := &Order{Quantity: 100, Price: 10.0, Side: Buy}
	commission := e.CalcCommission(order)
	assert.Equal(t, 5.0, commission)
}

func TestChinaACommissionLarge(t *testing.T) {
	e := &ChinaAEngine{}
	order := &Order{Quantity: 10000, Price: 10.0, Side: Buy}
	commission := e.CalcCommission(order)
	assert.InDelta(t, 30.0, commission, 0.01)
}

func TestChinaAStampDuty(t *testing.T) {
	e := &ChinaAEngine{}
	order := &Order{Quantity: 1000, Price: 10.0, Side: Sell}
	commission := e.CalcCommission(order)
	// Commission min 5 (万三, 10000*0.0003=3 < 5) + stamp duty 10 (千一, 10000*0.001=10)
	assert.InDelta(t, 15.0, commission, 0.01)
}

func TestChinaARoundSize(t *testing.T) {
	e := &ChinaAEngine{}
	assert.Equal(t, 100.0, e.RoundSize(101))
	assert.Equal(t, 100.0, e.RoundSize(199))
	assert.Equal(t, 200.0, e.RoundSize(200))
}

func TestChinaACanExecute(t *testing.T) {
	e := &ChinaAEngine{}
	assert.True(t, e.CanExecute(&Order{Side: Buy, Type: Market}))
}

func TestChinaASlippageBuy(t *testing.T) {
	e := &ChinaAEngine{}
	price := e.ApplySlippage(&Order{Side: Buy}, &Bar{Close: 10.0})
	assert.InDelta(t, 10.01, price, 0.001)
}

func TestChinaASlippageSell(t *testing.T) {
	e := &ChinaAEngine{}
	price := e.ApplySlippage(&Order{Side: Sell}, &Bar{Close: 10.0})
	assert.InDelta(t, 9.99, price, 0.001)
}

func TestChinaAPnL(t *testing.T) {
	e := &ChinaAEngine{}
	pnl := e.CalcPnL(&Position{Size: 100, EntryPrice: 10.0, CurrentPrice: 11.0})
	assert.InDelta(t, 100.0, pnl, 0.01)
}

func TestChinaAMargin(t *testing.T) {
	e := &ChinaAEngine{}
	assert.Equal(t, 0.0, e.CalcMargin(&Position{}))
}

func TestChinaACommissionZeroQuantity(t *testing.T) {
	e := &ChinaAEngine{}
	order := &Order{Quantity: 0, Price: 10.0, Side: Buy}
	commission := e.CalcCommission(order)
	assert.Equal(t, 0.0, commission)
}
