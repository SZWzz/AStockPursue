package engine

import "math"

const OptionsMultiplier = 100.0

type OptionsEngine struct {
	CommPerContract float64
	ExerciseFee     float64
	AssignmentFee   float64
	Slippage        float64
	MarginRateShort float64
}

func (e *OptionsEngine) Name() string { return "options" }

func (e *OptionsEngine) CanExecute(order *Order) bool {
	return order.Quantity > 0
}

func (e *OptionsEngine) RoundSize(size float64) float64 {
	return math.Floor(size)
}

func (e *OptionsEngine) CalcCommission(order *Order) float64 {
	return order.Quantity * e.CommPerContract
}

func (e *OptionsEngine) ApplySlippage(order *Order, bar interface{}) float64 {
	b := bar.(*Bar)
	if order.Side == Buy {
		return b.Close + e.Slippage
	}
	return b.Close - e.Slippage
}

func (e *OptionsEngine) CalcMargin(pos *Position) float64 {
	if pos.Size >= 0 {
		return 0
	}
	notional := math.Abs(pos.Size) * OptionsMultiplier * pos.CurrentPrice
	return notional*e.MarginRateShort + notional
}

func (e *OptionsEngine) CalcPnL(pos *Position) float64 {
	notional := math.Abs(pos.Size) * OptionsMultiplier
	if pos.Size >= 0 {
		return (pos.CurrentPrice - pos.EntryPrice) * notional
	}
	return (pos.EntryPrice - pos.CurrentPrice) * notional
}

// Black-Scholes call price
func BSCallPrice(S, K, T, r, sigma float64) float64 {
	if T <= 0 {
		return math.Max(0, S-K)
	}
	d1 := (math.Log(S/K) + (r+sigma*sigma/2)*T) / (sigma * math.Sqrt(T))
	d2 := d1 - sigma*math.Sqrt(T)
	return S*NormCDF(d1) - K*math.Exp(-r*T)*NormCDF(d2)
}

// Black-Scholes put price
func BSPutPrice(S, K, T, r, sigma float64) float64 {
	if T <= 0 {
		return math.Max(0, K-S)
	}
	d1 := (math.Log(S/K) + (r+sigma*sigma/2)*T) / (sigma * math.Sqrt(T))
	d2 := d1 - sigma*math.Sqrt(T)
	return K*math.Exp(-r*T)*NormCDF(-d2) - S*NormCDF(-d1)
}

// Standard normal CDF using math.Erfc
func NormCDF(x float64) float64 {
	return 0.5 * math.Erfc(-x/math.Sqrt2)
}
