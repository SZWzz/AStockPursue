package engine

import (
	"math"
)

type CryptoEngine struct {
	MakerFee          float64
	TakerFee          float64
	Slippage          float64
	Leverage          float64
	MaintenanceMargin float64
	Precision         map[string]float64
}

func (e *CryptoEngine) Name() string { return "crypto" }

func (e *CryptoEngine) CanExecute(order *Order) bool {
	return order.Quantity > 0
}

func (e *CryptoEngine) RoundSize(size float64) float64 {
	return math.Floor(size*1000) / 1000
}

func (e *CryptoEngine) CalcCommission(order *Order) float64 {
	rate := e.TakerFee
	if order.Type == Limit {
		rate = e.MakerFee
	}
	return order.Quantity * order.Price * rate
}

func (e *CryptoEngine) ApplySlippage(order *Order, bar interface{}) float64 {
	b := bar.(*Bar)
	if order.Side == Buy {
		return b.Close * (1 + e.Slippage)
	}
	return b.Close * (1 - e.Slippage)
}

func (e *CryptoEngine) CalcMargin(pos *Position) float64 {
	return math.Abs(pos.Size) * pos.CurrentPrice / e.Leverage
}

func (e *CryptoEngine) CalcPnL(pos *Position) float64 {
	if pos.Size >= 0 {
		return (pos.CurrentPrice - pos.EntryPrice) * pos.Size
	}
	return (pos.EntryPrice - pos.CurrentPrice) * math.Abs(pos.Size)
}

func (e *CryptoEngine) LiquidationPrice(pos *Position) float64 {
	if pos.Size >= 0 {
		return pos.EntryPrice * (1 - 1/e.Leverage + e.MaintenanceMargin)
	}
	return pos.EntryPrice * (1 + 1/e.Leverage - e.MaintenanceMargin)
}
