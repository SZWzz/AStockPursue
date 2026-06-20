package portfolio

import (
	"testing"

	"github.com/astockpursue/go-core/internal/engine"
)

func TestMarginCalculator(t *testing.T) {
	calc := &MarginCalculator{Leverage: 10, MaintMargin: 0.005}

	pos := &engine.Position{Symbol: "BTC-USDT", Size: 1.0, EntryPrice: 50000, CurrentPrice: 51000}
	required := calc.Required(pos)

	if required <= 0 {
		t.Error("required margin should be positive")
	}
	// Required margin should be position_value / leverage
	expectedRequired := 1.0 * 51000 / 10
	if required != expectedRequired {
		t.Errorf("required margin = %.2f, want %.2f", required, expectedRequired)
	}
}

func TestMarginCallLevel(t *testing.T) {
	calc := &MarginCalculator{Leverage: 10, MaintMargin: 0.005}

	// Equity is below maintenance margin → call
	equity := 2000.0
	required := 5000.0
	if !calc.CallLevel(equity, required) {
		t.Error("expected margin call when equity < maintenance")
	}

	// Equity is well above → no call
	equity = 20000.0
	if calc.CallLevel(equity, required) {
		t.Error("expected no margin call when equity is sufficient")
	}
}

func TestMarginAvailable(t *testing.T) {
	calc := &MarginCalculator{Leverage: 10, MaintMargin: 0.005}

	portfolio := &engine.Portfolio{Cash: 50000, Equity: 50000, Positions: make(map[string]*engine.Position)}
	available := calc.Available(portfolio)

	if available <= 0 {
		t.Error("available margin should be positive")
	}
	// Available = equity * leverage
	expected := 50000.0 * 10
	if available != expected {
		t.Errorf("available = %.2f, want %.2f", available, expected)
	}
}
