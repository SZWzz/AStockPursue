package engine

import "math"

type ChinaFuturesEngine struct {
	FuturesBase
	Symbol string
}

type futuresContract struct {
	Multiplier float64
	MarginRate float64
	CommRate   float64
	MinComm    float64
	PriceTick  float64
	PriceLimit float64
}

var chinaFuturesContracts = map[string]futuresContract{
	// CFFEX
	"IF": {300, 0.12, 0.000023, 0.01, 0.2, 0.10},
	"IC": {200, 0.12, 0.000023, 0.01, 0.2, 0.10},
	"IH": {300, 0.12, 0.000023, 0.01, 0.2, 0.10},
	// SHFE
	"RB": {10, 0.08, 0.0001, 5.0, 1, 0.05},
	"CU": {5, 0.10, 0.0001, 5.0, 10, 0.06},
	"AU": {1000, 0.08, 0.0001, 5.0, 0.02, 0.05},
	// DCE
	"I":  {100, 0.08, 0.0001, 5.0, 0.5, 0.04},
	"JM": {60, 0.20, 0.0001, 5.0, 0.5, 0.06},
	"C":  {10, 0.08, 0.0001, 5.0, 1, 0.04},
	// ZCE
	"CF": {5, 0.07, 0.0001, 5.0, 5, 0.04},
	"SR": {10, 0.05, 0.0001, 5.0, 1, 0.04},
	"TA": {20, 0.06, 0.0001, 5.0, 2, 0.04},
	// INE
	"SC": {1000, 0.10, 0.0001, 5.0, 0.1, 0.08},
	"NR": {10, 0.10, 0.0001, 5.0, 5, 0.08},
	// GFEX
	"SI": {10, 0.08, 0.0001, 5.0, 5, 0.08},
	"LC": {5, 0.12, 0.0001, 5.0, 50, 0.08},
}

func NewChinaFuturesEngine(symbol string) *ChinaFuturesEngine {
	c, ok := chinaFuturesContracts[symbol]
	if !ok {
		return nil
	}
	return &ChinaFuturesEngine{
		FuturesBase: FuturesBase{
			ContractMultiplier: c.Multiplier,
			MarginRate:         c.MarginRate,
			CommissionRate:     c.CommRate,
			MinCommission:      c.MinComm,
			PriceTick:          c.PriceTick,
			RoundLot:           1,
			PriceLimitPct:      c.PriceLimit,
		},
		Symbol: symbol,
	}
}

func (e *ChinaFuturesEngine) Name() string { return "china_futures" }

func (e *ChinaFuturesEngine) CalcCommission(order *Order) float64 {
	return e.FuturesBase.CalcCommission(order, order.Price)
}

func (e *ChinaFuturesEngine) CanExecute(order *Order) bool {
	if order.Quantity <= 0 {
		return false
	}
	if e.RoundLot > 0 && math.Mod(order.Quantity, e.RoundLot) != 0 {
		return false
	}
	return true
}
