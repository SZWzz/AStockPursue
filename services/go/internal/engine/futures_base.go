package engine

import (
	"math"
)

type FuturesBase struct {
	ContractMultiplier float64
	MarginRate         float64
	CommissionRate     float64
	MinCommission      float64
	PriceTick          float64
	RoundLot           float64
	PriceLimitPct      float64
}

func (f *FuturesBase) Name() string {
	return "futures_base"
}

func (f *FuturesBase) RoundSize(size float64) float64 {
	return math.Floor(size/f.RoundLot) * f.RoundLot
}

func (f *FuturesBase) CalcCommission(order *Order, price float64) float64 {
	turnover := order.Quantity * price * f.ContractMultiplier
	comm := turnover * f.CommissionRate
	if comm < f.MinCommission {
		return f.MinCommission
	}
	return comm
}

func (f *FuturesBase) CalcMargin(pos *Position) float64 {
	turnover := math.Abs(pos.Size) * pos.CurrentPrice * f.ContractMultiplier
	return turnover * f.MarginRate
}

func (f *FuturesBase) CalcPnL(pos *Position) float64 {
	if pos.Size >= 0 {
		return (pos.CurrentPrice - pos.EntryPrice) * pos.Size * f.ContractMultiplier
	}
	return (pos.EntryPrice - pos.CurrentPrice) * math.Abs(pos.Size) * f.ContractMultiplier
}

func (f *FuturesBase) ApplySlippage(order *Order, bar interface{}) float64 {
	b := bar.(*Bar)
	if order.Side == Buy {
		return b.Close + f.PriceTick
	}
	return b.Close - f.PriceTick
}

func (f *FuturesBase) CanExecute(order *Order, positions map[string]*Position) bool {
	if order.Quantity <= 0 {
		return false
	}
	if f.RoundLot > 0 && math.Mod(order.Quantity, f.RoundLot) != 0 {
		return false
	}
	return true
}
