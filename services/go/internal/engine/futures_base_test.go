package engine

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestFuturesBaseRoundSize(t *testing.T) {
	fb := &FuturesBase{RoundLot: 1}
	assert.InDelta(t, 1.0, fb.RoundSize(1.5), 0.01)
	assert.InDelta(t, 0.0, fb.RoundSize(0.5), 0.01)
}

func TestFuturesBaseRoundSizeMultipleLots(t *testing.T) {
	fb := &FuturesBase{RoundLot: 2}
	assert.InDelta(t, 4.0, fb.RoundSize(5.0), 0.01)
	assert.InDelta(t, 2.0, fb.RoundSize(3.0), 0.01)
	assert.InDelta(t, 0.0, fb.RoundSize(1.0), 0.01)
}

func TestFuturesBaseCommission(t *testing.T) {
	fb := &FuturesBase{
		ContractMultiplier: 300,
		CommissionRate:     0.0001,
		MinCommission:      5.0,
	}
	order := &Order{Quantity: 10}
	commission := fb.CalcCommission(order, 5000.0)
	assert.InDelta(t, 1500.0, commission, 0.01)
}

func TestFuturesBaseMinCommission(t *testing.T) {
	fb := &FuturesBase{
		ContractMultiplier: 300,
		CommissionRate:     0.0001,
		MinCommission:      5.0,
	}
	order := &Order{Quantity: 1}
	commission := fb.CalcCommission(order, 10.0)
	assert.InDelta(t, 5.0, commission, 0.01)
}

func TestFuturesBaseMargin(t *testing.T) {
	fb := &FuturesBase{
		ContractMultiplier: 300,
		MarginRate:         0.12,
	}
	pos := &Position{Size: 1, CurrentPrice: 5000.0}
	margin := fb.CalcMargin(pos)
	assert.InDelta(t, 180000.0, margin, 0.01)
}

func TestFuturesBaseMarginZeroSize(t *testing.T) {
	fb := &FuturesBase{
		ContractMultiplier: 300,
		MarginRate:         0.12,
	}
	pos := &Position{Size: 0, CurrentPrice: 5000.0}
	margin := fb.CalcMargin(pos)
	assert.InDelta(t, 0.0, margin, 0.01)
}

func TestFuturesBasePnL(t *testing.T) {
	fb := &FuturesBase{ContractMultiplier: 300}
	pos := &Position{Size: 1, EntryPrice: 4000.0, CurrentPrice: 5000.0}
	pnl := fb.CalcPnL(pos)
	assert.InDelta(t, 300000.0, pnl, 0.01)
}

func TestFuturesBasePnLShort(t *testing.T) {
	fb := &FuturesBase{ContractMultiplier: 300}
	pos := &Position{Size: -1, EntryPrice: 5000.0, CurrentPrice: 4000.0}
	pnl := fb.CalcPnL(pos)
	assert.InDelta(t, 300000.0, pnl, 0.01)
}

func TestFuturesBasePnLShortLoss(t *testing.T) {
	fb := &FuturesBase{ContractMultiplier: 300}
	pos := &Position{Size: -1, EntryPrice: 4000.0, CurrentPrice: 5000.0}
	pnl := fb.CalcPnL(pos)
	assert.InDelta(t, -300000.0, pnl, 0.01)
}

func TestFuturesBaseCanExecute(t *testing.T) {
	fb := &FuturesBase{RoundLot: 1}
	assert.True(t, fb.CanExecute(&Order{Quantity: 1}, nil))
	assert.True(t, fb.CanExecute(&Order{Quantity: 5}, nil))
}

func TestFuturesBaseCanExecuteInvalid(t *testing.T) {
	fb := &FuturesBase{RoundLot: 1}
	assert.False(t, fb.CanExecute(&Order{Quantity: 0}, nil))
	assert.False(t, fb.CanExecute(&Order{Quantity: -1}, nil))
}

func TestFuturesBaseSlippage(t *testing.T) {
	fb := &FuturesBase{PriceTick: 0.2}
	price := fb.ApplySlippage(&Order{Side: Buy}, &Bar{Close: 5000.0})
	assert.InDelta(t, 5000.2, price, 0.01)
	price = fb.ApplySlippage(&Order{Side: Sell}, &Bar{Close: 5000.0})
	assert.InDelta(t, 4999.8, price, 0.01)
}

func TestFuturesBaseName(t *testing.T) {
	fb := &FuturesBase{}
	assert.Equal(t, "futures_base", fb.Name())
}

func TestFuturesBaseCanExecuteNonRoundLot(t *testing.T) {
	fb := &FuturesBase{RoundLot: 2}
	assert.False(t, fb.CanExecute(&Order{Quantity: 3}, nil))
	assert.True(t, fb.CanExecute(&Order{Quantity: 4}, nil))
}
