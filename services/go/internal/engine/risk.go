package engine

import "math"

type RiskConfig struct {
	StopLossPercent    float64
	TakeProfitPercent  float64
	TrailingStopPercent float64
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

func (r *RiskManager) CheckExits(portfolio *Portfolio, bar interface{}) []*Order {
	b := bar.(*Bar)
	var orders []*Order
	for symbol, pos := range portfolio.Positions {
		if pos.Symbol != b.Symbol {
			continue
		}
		pos.CurrentPrice = b.Close
		pnlPct := (b.Close - pos.EntryPrice) / pos.EntryPrice * 100

		if b.Close > r.HighWaterMarks[symbol] {
			r.HighWaterMarks[symbol] = b.Close
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
				trailDrop := (high - b.Close) / high * 100
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
