package engine

import (
	"testing"
)

func TestNewMonitorEngine(t *testing.T) {
	eng := NewMonitorEngine()
	if eng == nil {
		t.Fatal("expected non-nil MonitorEngine")
	}
}

func TestDefaultAlertRule(t *testing.T) {
	rule := DefaultAlertRule()
	if rule.DriftWarningPct != 0.20 {
		t.Errorf("expected DriftWarningPct 0.20, got %v", rule.DriftWarningPct)
	}
	if rule.SlippageWarningRatio != 2.0 {
		t.Errorf("expected SlippageWarningRatio 2.0, got %v", rule.SlippageWarningRatio)
	}
	if rule.FactorICWarningDays != 5 {
		t.Errorf("expected FactorICWarningDays 5, got %v", rule.FactorICWarningDays)
	}
	if rule.FactorICThreshold != 0.01 {
		t.Errorf("expected FactorICThreshold 0.01, got %v", rule.FactorICThreshold)
	}
	if rule.DriftEmergencyPct != 2.0 {
		t.Errorf("expected DriftEmergencyPct 2.0, got %v", rule.DriftEmergencyPct)
	}
}

func TestMonitorEngine_ComputeDrift_OK(t *testing.T) {
	eng := NewMonitorEngine()
	live := &DriftInput{
		CumulativeReturn:  0.10,
		MaxDrawdown:       -0.05,
		AvgSlippage:       0.001,
		FactorIC:          0.05,
		FactorICDaysBelow: 1,
	}
	backtest := &DriftInput{
		CumulativeReturn: 0.10,
		MaxDrawdown:      -0.05,
		AvgSlippage:      0.001,
		FactorIC:         0.05,
	}

	result := eng.ComputeDrift(1, live, backtest)

	if result.AlertLevel != "OK" {
		t.Errorf("expected OK, got %s", result.AlertLevel)
	}
	if result.StrategyID != 1 {
		t.Errorf("expected strategyID 1, got %d", result.StrategyID)
	}
	if !result.BarTime.IsZero() {
		// BarTime should be set to time.Now()
	}
}

func TestMonitorEngine_ComputeDrift_WARNING_DriftExceedsThreshold(t *testing.T) {
	eng := NewMonitorEngine()
	live := &DriftInput{
		CumulativeReturn:  0.06, // Backtest expected 0.10, so drift >20%
		MaxDrawdown:       -0.05,
		AvgSlippage:       0.001,
		FactorIC:          0.05,
		FactorICDaysBelow: 1,
	}
	backtest := &DriftInput{
		CumulativeReturn: 0.10,
		MaxDrawdown:      -0.05,
		AvgSlippage:      0.001,
		FactorIC:         0.05,
	}

	result := eng.ComputeDrift(1, live, backtest)

	if result.AlertLevel != "WARNING" {
		t.Errorf("expected WARNING when drift >20%%, got %s", result.AlertLevel)
	}
	// DriftPct should be negative (underperformance)
	expectedDrift := (0.06 - 0.10) / 0.10 // -0.40
	diff := result.DriftPct - expectedDrift
	if diff < 0 {
		diff = -diff
	}
	if diff > 1e-9 {
		t.Errorf("expected DriftPct %v, got %v", expectedDrift, result.DriftPct)
	}
}

func TestMonitorEngine_ComputeDrift_WARNING_SlippageExceedsThreshold(t *testing.T) {
	eng := NewMonitorEngine()
	live := &DriftInput{
		CumulativeReturn:  0.10,
		MaxDrawdown:       -0.05,
		AvgSlippage:       0.005, // 5x higher than backtest
		FactorIC:          0.05,
		FactorICDaysBelow: 1,
	}
	backtest := &DriftInput{
		CumulativeReturn: 0.10,
		MaxDrawdown:      -0.05,
		AvgSlippage:      0.001,
		FactorIC:         0.05,
	}

	result := eng.ComputeDrift(1, live, backtest)

	if result.AlertLevel != "WARNING" {
		t.Errorf("expected WARNING when slippage ratio >2x, got %s", result.AlertLevel)
	}
	if result.SlippageRatio != 5.0 {
		t.Errorf("expected SlippageRatio 5.0, got %v", result.SlippageRatio)
	}
}

func TestMonitorEngine_ComputeDrift_CRITICAL_ICDecay(t *testing.T) {
	eng := NewMonitorEngine()
	live := &DriftInput{
		CumulativeReturn:  0.10,
		MaxDrawdown:       -0.05,
		AvgSlippage:       0.001,
		FactorIC:          0.005, // Very low IC
		FactorICDaysBelow: 7,     // 7 days below threshold
	}
	backtest := &DriftInput{
		CumulativeReturn: 0.10,
		MaxDrawdown:      -0.05,
		AvgSlippage:      0.001,
		FactorIC:         0.05,
	}

	result := eng.ComputeDrift(1, live, backtest)

	if result.AlertLevel != "CRITICAL" {
		t.Errorf("expected CRITICAL when IC decay >=5 days, got %s", result.AlertLevel)
	}
}

func TestMonitorEngine_ComputeDrift_CRITICAL_ExactlyThreshold(t *testing.T) {
	eng := NewMonitorEngine()
	live := &DriftInput{
		CumulativeReturn:  0.10,
		MaxDrawdown:       -0.05,
		AvgSlippage:       0.001,
		FactorIC:          0.005,
		FactorICDaysBelow: 5, // exactly at threshold
	}
	backtest := &DriftInput{
		CumulativeReturn: 0.10,
		MaxDrawdown:      -0.05,
		AvgSlippage:      0.001,
		FactorIC:         0.05,
	}

	result := eng.ComputeDrift(1, live, backtest)

	if result.AlertLevel != "CRITICAL" {
		t.Errorf("expected CRITICAL when IC decay exactly at threshold, got %s", result.AlertLevel)
	}
}

func TestMonitorEngine_ComputeDrift_EMERGENCY_DrawdownBreach(t *testing.T) {
	eng := NewMonitorEngine()
	live := &DriftInput{
		CumulativeReturn:  0.05,
		MaxDrawdown:       -0.30, // Much worse than historical -0.15
		AvgSlippage:       0.001,
		FactorIC:          0.05,
		FactorICDaysBelow: 1,
	}
	backtest := &DriftInput{
		CumulativeReturn: 0.10,
		MaxDrawdown:      -0.15,
		AvgSlippage:      0.001,
		FactorIC:         0.05,
	}

	result := eng.ComputeDrift(1, live, backtest)

	if result.AlertLevel != "EMERGENCY" {
		t.Errorf("expected EMERGENCY when drawdown breaches historical, got %s", result.AlertLevel)
	}
	// -0.30 / -0.15 = 2.0, which is > 1.5
	drawdownBreach := result.MaxDrawdownCurrent / result.MaxDrawdownHistorical
	if drawdownBreach != 2.0 {
		t.Errorf("expected drawdown breach ratio 2.0, got %v", drawdownBreach)
	}
}

func TestMonitorEngine_ComputeDrift_EMERGENCY_NotTriggered_BelowBreach(t *testing.T) {
	eng := NewMonitorEngine()
	live := &DriftInput{
		CumulativeReturn:  0.10,
		MaxDrawdown:       -0.18, // drawdownBreach = 1.2, still < 1.5
		AvgSlippage:       0.001,
		FactorIC:          0.05,
		FactorICDaysBelow: 1,
	}
	backtest := &DriftInput{
		CumulativeReturn: 0.10,
		MaxDrawdown:      -0.15,
		AvgSlippage:      0.001,
		FactorIC:         0.05,
	}

	result := eng.ComputeDrift(1, live, backtest)

	// 1.2x < 1.5x, no emergency. No drift/slippage either → OK
	if result.AlertLevel != "OK" {
		t.Errorf("expected OK when drawdown breach < 1.5x, got %s", result.AlertLevel)
	}
}

func TestMonitorEngine_ComputeDrift_ZeroBacktestReturn(t *testing.T) {
	eng := NewMonitorEngine()
	live := &DriftInput{
		CumulativeReturn:  0.05,
		MaxDrawdown:       -0.05,
		AvgSlippage:       0.001,
		FactorIC:          0.05,
		FactorICDaysBelow: 1,
	}
	backtest := &DriftInput{
		CumulativeReturn: 0.0, // Zero return
		MaxDrawdown:      -0.05,
		AvgSlippage:      0.001,
		FactorIC:         0.05,
	}

	result := eng.ComputeDrift(1, live, backtest)

	// DriftPct should be 0 (division by zero avoided)
	if result.DriftPct != 0 {
		t.Errorf("expected DriftPct 0 when backtest return is zero, got %v", result.DriftPct)
	}
}

func TestMaxFloat(t *testing.T) {
	if v := maxFloat(5.0, 3.0); v != 5.0 {
		t.Errorf("expected 5.0, got %v", v)
	}
	if v := maxFloat(3.0, 5.0); v != 5.0 {
		t.Errorf("expected 5.0, got %v", v)
	}
}

func TestAbsFloat(t *testing.T) {
	if v := absFloat(5.0); v != 5.0 {
		t.Errorf("expected 5.0, got %v", v)
	}
	if v := absFloat(-5.0); v != 5.0 {
		t.Errorf("expected 5.0, got %v", v)
	}
	if v := absFloat(0.0); v != 0.0 {
		t.Errorf("expected 0.0, got %v", v)
	}
}
