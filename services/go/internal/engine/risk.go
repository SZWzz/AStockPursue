package engine

import "math"

type RiskConfig struct {
	StopLossPercent     float64
	TakeProfitPercent   float64
	TrailingStopPercent float64
	DayLossLimit        float64 `json:"day_loss_limit"`
	MaxPositionCount    int     `json:"max_position_count"`
	// TODO(P3): wire MaxCorrelation into BlockNewSignals (Pearson check)
	MaxCorrelation      float64 `json:"max_correlation"`
	// TODO(P3): wire VolatilityAdjust into position sizing (Kelly formula)
	VolatilityAdjust    bool    `json:"volatility_adjust"`
}

type RiskManager struct {
	Config         RiskConfig
	HighWaterMarks map[string]float64
}

func NewRiskManager(config RiskConfig) *RiskManager {
	return &RiskManager{
		Config:         config,
		HighWaterMarks: make(map[string]float64),
	}
}

func (r *RiskManager) CheckExits(portfolio *Portfolio, bar *Bar) []*Order {
	var orders []*Order
	for symbol, pos := range portfolio.Positions {
		if pos.Symbol != bar.Symbol {
			continue
		}
		pos.CurrentPrice = bar.Close
		pnlPct := (bar.Close - pos.EntryPrice) / pos.EntryPrice * 100

		if bar.Close > r.HighWaterMarks[symbol] {
			r.HighWaterMarks[symbol] = bar.Close
		}

		if r.Config.StopLossPercent > 0 && pnlPct <= -r.Config.StopLossPercent {
			orders = append(orders, &Order{
				Symbol: symbol, Side: Sell, Type: Market,
				Quantity: math.Abs(pos.Size), Status: OrderPending,
			})
			delete(r.HighWaterMarks, symbol)
			continue
		}

		if r.Config.TakeProfitPercent > 0 && pnlPct >= r.Config.TakeProfitPercent {
			orders = append(orders, &Order{
				Symbol: symbol, Side: Sell, Type: Market,
				Quantity: math.Abs(pos.Size), Status: OrderPending,
			})
			delete(r.HighWaterMarks, symbol)
			continue
		}

		if r.Config.TrailingStopPercent > 0 {
			high := r.HighWaterMarks[symbol]
			if high > pos.EntryPrice {
				trailDrop := (high - bar.Close) / high * 100
				if trailDrop >= r.Config.TrailingStopPercent {
					orders = append(orders, &Order{
						Symbol: symbol, Side: Sell, Type: Market,
						Quantity: math.Abs(pos.Size), Status: OrderPending,
					})
					delete(r.HighWaterMarks, symbol)
				}
			}
		}
	}
	return orders
}

func (rm *RiskManager) BlockNewSignals(pf *Portfolio) bool {
	if rm.Config.DayLossLimit > 0 {
		currentEquity := pf.TotalEquity()
		if pf.InitialEquity-currentEquity >= rm.Config.DayLossLimit {
			return true
		}
	}
	if rm.Config.MaxPositionCount > 0 {
		activeCount := 0
		for _, pos := range pf.Positions {
			if pos.Size > 0 {
				activeCount++
			}
		}
		if activeCount >= rm.Config.MaxPositionCount {
			return true
		}
	}
	return false
}

func (pf *Portfolio) TotalEquity() float64 {
	total := pf.Cash
	for _, pos := range pf.Positions {
		if pos.Size > 0 {
			total += pos.Size * pos.CurrentPrice
		}
	}
	return total
}
