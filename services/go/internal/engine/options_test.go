package engine

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func newTestOptions() *OptionsEngine {
	return &OptionsEngine{CommPerContract: 0.65, ExerciseFee: 5.00, AssignmentFee: 5.00, Slippage: 0.01, MarginRateShort: 0.20}
}

func TestOptionsRoundSize(t *testing.T) {
	e := newTestOptions()
	assert.Equal(t, 1.0, e.RoundSize(1))
	assert.Equal(t, 0.0, e.RoundSize(0.5))
}

func TestOptionsCommission(t *testing.T) {
	e := newTestOptions()
	order := &Order{Quantity: 10}
	assert.InDelta(t, 6.50, e.CalcCommission(order), 0.01)
}

func TestOptionsPnL(t *testing.T) {
	e := newTestOptions()
	pos := &Position{Size: 1, EntryPrice: 5, CurrentPrice: 8}
	assert.InDelta(t, 300.0, e.CalcPnL(pos), 0.01)
}

func TestOptionsMarginLong(t *testing.T) {
	e := newTestOptions()
	pos := &Position{Size: 1, CurrentPrice: 5}
	assert.Equal(t, 0.0, e.CalcMargin(pos))
}

func TestOptionsMarginShort(t *testing.T) {
	e := newTestOptions()
	pos := &Position{Size: -1, CurrentPrice: 5}
	assert.InDelta(t, 600.0, e.CalcMargin(pos), 0.01)
}

func TestOptionsCanExecute(t *testing.T) {
	e := newTestOptions()
	assert.True(t, e.CanExecute(&Order{Quantity: 1, Side: Buy}))
	assert.True(t, e.CanExecute(&Order{Quantity: 1, Side: Sell}))
}

func TestOptionsSlippage(t *testing.T) {
	e := newTestOptions()
	price := e.ApplySlippage(&Order{Side: Buy}, &Bar{Close: 100})
	assert.InDelta(t, 100.01, price, 0.001)
}

func TestOptionsName(t *testing.T) {
	e := newTestOptions()
	assert.Equal(t, "options", e.Name())
}

func TestBSCallPrice(t *testing.T) {
	price := BSCallPrice(100, 100, 1, 0.05, 0.2)
	assert.InDelta(t, 10.45, price, 0.5)
}
