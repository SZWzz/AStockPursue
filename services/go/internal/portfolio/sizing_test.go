package portfolio

import (
	"testing"

	"github.com/astockpursue/go-core/internal/engine"
)

func TestEqualWeightSizer(t *testing.T) {
	sizer := NewEqualWeightSizer()
	portfolio := &engine.Portfolio{Cash: 100000, Equity: 100000, Positions: make(map[string]*engine.Position)}

	weights := map[string]float64{"000001.SZ": 0.5, "000002.SZ": 0.3, "000003.SZ": 0.2}
	prices := map[string]float64{"000001.SZ": 50.0, "000002.SZ": 30.0, "000003.SZ": 20.0}

	sizes := sizer.Size(portfolio, weights, prices)

	if len(sizes) != 3 {
		t.Fatalf("expected 3 sizes, got %d", len(sizes))
	}
	// Total allocation should not exceed cash
	totalAlloc := 0.0
	for sym, qty := range sizes {
		totalAlloc += qty * prices[sym]
	}
	if totalAlloc > portfolio.Cash*1.01 { // allow 1% float tolerance
		t.Errorf("total allocation %.2f exceeds cash %.2f", totalAlloc, portfolio.Cash)
	}
}

func TestKellySizer(t *testing.T) {
	sizer := NewKellySizer(0.5) // half-Kelly
	portfolio := &engine.Portfolio{Cash: 100000, Equity: 100000, Positions: make(map[string]*engine.Position)}

	weights := map[string]float64{"BTC-USDT": 0.6}
	prices := map[string]float64{"BTC-USDT": 50000.0}

	sizes := sizer.Size(portfolio, weights, prices)

	if len(sizes) != 1 {
		t.Fatalf("expected 1 size, got %d", len(sizes))
	}
	if sizes["BTC-USDT"] <= 0 {
		t.Error("expected positive allocation")
	}
}
