package engine

import "math"

const (
	ChinaACommissionRate  = 0.0003
	ChinaAStampDutyRate   = 0.001
	ChinaAMinCommission   = 5.0
	ChinaARoundLot        = 100.0
	ChinaAPriceLimitPct   = 0.10
)

type ChinaAEngine struct{}

func (e *ChinaAEngine) Name() string { return "china_a" }

func (e *ChinaAEngine) CanExecute(order *Order) bool {
	return true
}

func (e *ChinaAEngine) RoundSize(size float64) float64 {
	return math.Floor(size/ChinaARoundLot) * ChinaARoundLot
}

func (e *ChinaAEngine) CalcCommission(order *Order) float64 {
	turnover := order.Quantity * order.Price
	comm := turnover * ChinaACommissionRate
	if comm < ChinaAMinCommission {
		comm = ChinaAMinCommission
	}
	if order.Side == Sell {
		stamp := turnover * ChinaAStampDutyRate
		comm += stamp
	}
	return comm
}

func (e *ChinaAEngine) ApplySlippage(order *Order, bar interface{}) float64 {
	b := bar.(*Bar)
	price := b.Close
	if order.Side == Buy {
		price *= 1.001
	} else {
		price *= 0.999
	}
	return math.Round(price*100) / 100
}

func (e *ChinaAEngine) CalcMargin(position *Position) float64 {
	return 0
}

func (e *ChinaAEngine) CalcPnL(position *Position) float64 {
	return position.Size * (position.CurrentPrice - position.EntryPrice)
}
