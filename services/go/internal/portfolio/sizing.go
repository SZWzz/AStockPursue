package portfolio

import (
	"github.com/astockpursue/go-core/internal/engine"
)

// Sizer computes target position sizes from signal weights and current prices.
type Sizer interface {
	Size(portfolio *engine.Portfolio, weights map[string]float64, prices map[string]float64) map[string]float64
}

// EqualWeightSizer allocates capital proportionally to target weights.
type EqualWeightSizer struct {
	engine engine.Engine
}

func NewEqualWeightSizer() *EqualWeightSizer {
	return &EqualWeightSizer{}
}

func (s *EqualWeightSizer) Size(portfolio *engine.Portfolio, weights map[string]float64, prices map[string]float64) map[string]float64 {
	sizes := make(map[string]float64, len(weights))
	for sym, weight := range weights {
		price, ok := prices[sym]
		if !ok || price <= 0 {
			continue
		}
		targetValue := portfolio.Equity * weight
		qty := targetValue / price
		if s.engine != nil {
			qty = s.engine.RoundSize(qty)
		}
		if qty*price > portfolio.Cash {
			qty = portfolio.Cash / price
			if s.engine != nil {
				qty = s.engine.RoundSize(qty)
			}
		}
		if qty > 0 {
			sizes[sym] = qty
		}
	}
	return sizes
}

// KellySizer uses the Kelly Criterion: f* = (p*b - q) / b
// where p=win probability, b=win/loss ratio (odds), q=1-p
type KellySizer struct {
	fraction float64 // half-Kelly=0.5, full-Kelly=1.0
	pWin     float64
	winLoss  float64
}

func NewKellySizer(fraction float64) *KellySizer {
	return &KellySizer{
		fraction: fraction,
		pWin:     0.55, // default: 55% win rate
		winLoss:  1.5,  // default: 1.5:1 reward/risk
	}
}

func (s *KellySizer) Size(portfolio *engine.Portfolio, weights map[string]float64, prices map[string]float64) map[string]float64 {
	// Kelly fraction: f = (p*b - q) / b
	q := 1.0 - s.pWin
	kellyFrac := (s.pWin*s.winLoss - q) / s.winLoss
	if kellyFrac < 0 {
		kellyFrac = 0
	}
	kellyFrac *= s.fraction

	sizes := make(map[string]float64, len(weights))
	for sym, weight := range weights {
		price, ok := prices[sym]
		if !ok || price <= 0 {
			continue
		}
		targetValue := portfolio.Equity * weight * kellyFrac
		qty := targetValue / price
		if qty > 0 && qty*price <= portfolio.Cash {
			sizes[sym] = qty
		}
	}
	return sizes
}

// RiskParitySizer allocates equal volatility contributions.
type RiskParitySizer struct {
	volWindow int // lookback for volatility estimation
}

func NewRiskParitySizer(volWindow int) *RiskParitySizer {
	if volWindow <= 0 {
		volWindow = 20
	}
	return &RiskParitySizer{volWindow: volWindow}
}

func (s *RiskParitySizer) Size(portfolio *engine.Portfolio, weights map[string]float64, prices map[string]float64) map[string]float64 {
	// Equal risk contribution: weight_i ∝ 1/vol_i
	sizes := make(map[string]float64, len(weights))
	// Without vol data, fall back to equal weight
	n := float64(len(weights))
	if n == 0 {
		return sizes
	}
	for sym, price := range prices {
		if price <= 0 {
			continue
		}
		targetValue := portfolio.Equity / n
		qty := targetValue / price
		if qty > 0 && qty*price <= portfolio.Cash {
			sizes[sym] = qty
		}
	}
	return sizes
}
