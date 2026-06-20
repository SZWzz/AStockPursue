package portfolio

import "github.com/astockpursue/go-core/internal/engine"

// MarginCalculator computes margin requirements for leveraged positions.
type MarginCalculator struct {
	Leverage    float64 // e.g., 10x
	MaintMargin float64 // maintenance margin rate, e.g., 0.005 (0.5%)
}

// Required returns the margin required to hold a position at current prices.
func (m *MarginCalculator) Required(position *engine.Position) float64 {
	if m.Leverage <= 0 {
		m.Leverage = 1
	}
	notional := position.Size * position.CurrentPrice
	return notional / m.Leverage
}

// Available returns the total margin available based on equity and leverage.
func (m *MarginCalculator) Available(portfolio *engine.Portfolio) float64 {
	if m.Leverage <= 0 {
		m.Leverage = 1
	}
	return portfolio.Equity * m.Leverage
}

// CallLevel returns true if a margin call should be triggered.
// A call occurs when equity falls below the initial margin requirement.
func (m *MarginCalculator) CallLevel(equity float64, required float64) bool {
	if required <= 0 {
		return false
	}
	return equity < required
}
