package engine

import "math"

type ForexEngine struct {
	SpreadMajor float64
	SpreadMinor float64
	Slippage    float64
	Leverage    float64
	LotSize     float64
}

func (e *ForexEngine) Name() string { return "forex" }

func (e *ForexEngine) CanExecute(order *Order) bool {
	return order.Quantity > 0
}

func (e *ForexEngine) RoundSize(size float64) float64 {
	return math.Floor(size*100) / 100
}

func (e *ForexEngine) CalcCommission(order *Order) float64 {
	return 0
}

func (e *ForexEngine) ApplySlippage(order *Order, bar interface{}) float64 {
	b := bar.(*Bar)
	if order.Side == Buy {
		return b.Close + e.Slippage
	}
	return b.Close - e.Slippage
}

func (e *ForexEngine) CalcMargin(pos *Position) float64 {
	notional := math.Abs(pos.Size) * e.LotSize * pos.CurrentPrice
	return notional / e.Leverage
}

func (e *ForexEngine) CalcPnL(pos *Position) float64 {
	diff := pos.CurrentPrice - pos.EntryPrice
	if pos.Size < 0 {
		diff = -diff
	}
	return diff / 0.0001 * (math.Abs(pos.Size) * e.LotSize * 0.0001)
}
