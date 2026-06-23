package engine

import (
	"time"
)

// MonitorEngine calculates drift metrics between live trading and backtest expectations.
type MonitorEngine struct{}

// NewMonitorEngine creates a new MonitorEngine.
func NewMonitorEngine() *MonitorEngine {
	return &MonitorEngine{}
}

// DriftResult holds the computed drift/slippage/factor-decay metrics.
type DriftResult struct {
	StrategyID               int       `json:"strategy_id"`
	BarTime                  time.Time `json:"bar_time"`
	LiveCumulativeReturn     float64   `json:"live_cumulative_return"`
	BacktestExpectedReturn   float64   `json:"backtest_expected_return"`
	DriftPct                 float64   `json:"drift_pct"`
	SlippageRatio            float64   `json:"slippage_ratio"`
	MaxDrawdownCurrent       float64   `json:"max_drawdown_current"`
	MaxDrawdownHistorical    float64   `json:"max_drawdown_historical"`
	FactorICCurrent          float64   `json:"factor_ic_current"`
	FactorICDaysBelowThreshold int     `json:"factor_ic_days_below_threshold"`
	AlertLevel               string    `json:"alert_level"` // OK, WARNING, CRITICAL, EMERGENCY
}

// AlertRule defines thresholds for different alert levels.
type AlertRule struct {
	DriftWarningPct      float64 // >20% drift → WARNING
	SlippageWarningRatio float64 // >2x slippage → WARNING
	FactorICWarningDays  int     // >=5 days IC<0.01 → CRITICAL
	FactorICThreshold    float64 // IC threshold for decay detection

	DriftEmergencyPct float64 // >200% drift → EMERGENCY (configurable)
}

// DefaultAlertRule returns the production alert thresholds.
func DefaultAlertRule() AlertRule {
	return AlertRule{
		DriftWarningPct:      0.20,
		SlippageWarningRatio: 2.0,
		FactorICWarningDays:  5,
		FactorICThreshold:    0.01,
		DriftEmergencyPct:    2.0,
	}
}

// ComputeDrift calculates monitoring drift metrics from live and backtest stats.
func (e *MonitorEngine) ComputeDrift(strategyID int, live, backtest *DriftInput) *DriftResult {
	result := &DriftResult{
		StrategyID:               strategyID,
		BarTime:                  time.Now(),
		LiveCumulativeReturn:     live.CumulativeReturn,
		BacktestExpectedReturn:   backtest.CumulativeReturn,
		MaxDrawdownCurrent:       live.MaxDrawdown,
		MaxDrawdownHistorical:    backtest.MaxDrawdown,
		FactorICCurrent:          live.FactorIC,
		FactorICDaysBelowThreshold: live.FactorICDaysBelow,
		SlippageRatio:            live.AvgSlippage / maxFloat(backtest.AvgSlippage, 0.001),
	}

	// Compute drift percentage
	if backtest.CumulativeReturn != 0 {
		result.DriftPct = (live.CumulativeReturn - backtest.CumulativeReturn) / absFloat(backtest.CumulativeReturn)
	}

	// Determine alert level
	result.AlertLevel = e.computeAlertLevel(result, DefaultAlertRule())

	return result
}

func (e *MonitorEngine) computeAlertLevel(r *DriftResult, rule AlertRule) string {
	// EMERGENCY: max drawdown breaches historical
	if r.MaxDrawdownCurrent < r.MaxDrawdownHistorical && r.MaxDrawdownHistorical < 0 {
		drawdownBreach := r.MaxDrawdownCurrent / r.MaxDrawdownHistorical
		if drawdownBreach > 1.5 { // 50% worse than historical
			return "EMERGENCY"
		}
	}

	// CRITICAL: factor IC decay
	if r.FactorICDaysBelowThreshold >= rule.FactorICWarningDays {
		return "CRITICAL"
	}

	// WARNING: drift or slippage
	driftAbs := absFloat(r.DriftPct)
	if driftAbs > rule.DriftWarningPct || r.SlippageRatio > rule.SlippageWarningRatio {
		return "WARNING"
	}

	return "OK"
}

// DriftInput holds the input data for drift computation.
type DriftInput struct {
	CumulativeReturn  float64
	MaxDrawdown       float64
	AvgSlippage       float64
	FactorIC          float64
	FactorICDaysBelow int
}

func maxFloat(a, b float64) float64 {
	if a > b {
		return a
	}
	return b
}

func absFloat(f float64) float64 {
	if f < 0 {
		return -f
	}
	return f
}
