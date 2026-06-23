package engine

import "math"

type GlobalEquityEngine struct {
	Market         string
	PerShareComm   float64
	CommissionRate float64
	MinCommission  float64
	StampDutyRate  float64
	Slippage       float64
	CanShort       bool
}

func (e *GlobalEquityEngine) Name() string { return "global_equity" }

func (e *GlobalEquityEngine) CanExecute(order *Order) bool {
	if order.Quantity <= 0 {
		return false
	}
	if order.Side == Sell && !e.CanShort {
		return false
	}
	return true
}

func (e *GlobalEquityEngine) RoundSize(size float64) float64 {
	return math.Floor(size)
}

func (e *GlobalEquityEngine) CalcCommission(order *Order) float64 {
	turnover := order.Quantity * order.Price
	var comm float64
	if e.Market == "US" {
		comm = order.Quantity * e.PerShareComm
		if comm < e.MinCommission {
			comm = e.MinCommission
		}
	} else {
		comm = turnover * e.CommissionRate
		if comm < e.MinCommission {
			comm = e.MinCommission
		}
		if order.Side == Sell {
			comm += turnover * e.StampDutyRate
		}
	}
	return comm
}

func (e *GlobalEquityEngine) ApplySlippage(order *Order, bar *Bar) float64 {
	if order.Side == Buy {
		return bar.Close * (1 + e.Slippage)
	}
	return bar.Close * (1 - e.Slippage)
}

func (e *GlobalEquityEngine) CalcMargin(pos *Position) float64 {
	turnover := math.Abs(pos.Size) * pos.CurrentPrice
	if pos.Size >= 0 {
		return turnover * 0.5
	}
	return turnover * 1.5
}

func (e *GlobalEquityEngine) CalcPnL(pos *Position) float64 {
	if pos.Size >= 0 {
		return (pos.CurrentPrice - pos.EntryPrice) * pos.Size
	}
	return (pos.EntryPrice - pos.CurrentPrice) * math.Abs(pos.Size)
}
