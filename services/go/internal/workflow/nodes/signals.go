// Package nodes provides built-in workflow node implementations for the
// AStockPursue Go workflow engine.  This file contains signal-generation and
// technical-indicator nodes.
package nodes

import (
	"context"
	"fmt"
	"math"

	"github.com/astockpursue/go-core/internal/workflow"
)

// ---------------------------------------------------------------------------
// 1. cross_over — detects when a fast line crosses above/below a slow line
// ---------------------------------------------------------------------------

// CrossOverNode detects cross-over events (golden cross / death cross)
// between two series and emits a buy/sell/hold signal along with the
// crossover price level.
type CrossOverNode struct {
	id string
}

func (n *CrossOverNode) ID() string           { return n.id }
func (n *CrossOverNode) NodeType() string      { return "cross_over" }
func (n *CrossOverNode) Category() string      { return "signal" }
func (n *CrossOverNode) ParamSchema() []workflow.ParamDef { return nil }
func (n *CrossOverNode) Validate() error       { return nil }

func (n *CrossOverNode) InputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "fast", Type: workflow.PortSeries, Required: true},
		{Name: "slow", Type: workflow.PortSeries, Required: true},
	}
}

func (n *CrossOverNode) OutputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "signal", Type: workflow.PortAny, Required: true},
		{Name: "crossover_point", Type: workflow.PortAny, Required: true},
	}
}

func (n *CrossOverNode) Execute(ctx context.Context, inputs workflow.NodeParams, params workflow.NodeParams) (workflow.NodeOutputs, error) {
	fast, ok := inputs["fast"].([]float64)
	if !ok {
		return nil, fmt.Errorf("cross_over: fast must be []float64, got %T", inputs["fast"])
	}
	slow, ok := inputs["slow"].([]float64)
	if !ok {
		return nil, fmt.Errorf("cross_over: slow must be []float64, got %T", inputs["slow"])
	}

	// Truncate to the shorter series length.
	minLen := len(fast)
	if len(slow) < minLen {
		minLen = len(slow)
	}
	if minLen < 2 {
		return workflow.NodeOutputs{"signal": "hold", "crossover_point": 0.0}, nil
	}

	fPrev, fCurr := fast[minLen-2], fast[minLen-1]
	sPrev, sCurr := slow[minLen-2], slow[minLen-1]

	signal := "hold"
	point := fCurr
	switch {
	case fPrev <= sPrev && fCurr > sCurr:
		signal = "buy" // fast crosses above slow (golden cross)
	case fPrev >= sPrev && fCurr < sCurr:
		signal = "sell" // fast crosses below slow (death cross)
	}
	return workflow.NodeOutputs{"signal": signal, "crossover_point": point}, nil
}

// ---------------------------------------------------------------------------
// 2. cross_signal — generates buy/sell signals from a pair of series
// ---------------------------------------------------------------------------

// CrossSignalNode compares two series element-by-element and emits a signal
// array (buy / sell / hold at each position) plus the last signal.
type CrossSignalNode struct {
	id string
}

func (n *CrossSignalNode) ID() string           { return n.id }
func (n *CrossSignalNode) NodeType() string      { return "cross_signal" }
func (n *CrossSignalNode) Category() string      { return "signal" }
func (n *CrossSignalNode) ParamSchema() []workflow.ParamDef { return nil }
func (n *CrossSignalNode) Validate() error       { return nil }

func (n *CrossSignalNode) InputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "series_a", Type: workflow.PortSeries, Required: true},
		{Name: "series_b", Type: workflow.PortSeries, Required: true},
	}
}

func (n *CrossSignalNode) OutputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "signals", Type: workflow.PortAny, Required: true},
		{Name: "last_signal", Type: workflow.PortAny, Required: true},
	}
}

func (n *CrossSignalNode) Execute(ctx context.Context, inputs workflow.NodeParams, params workflow.NodeParams) (workflow.NodeOutputs, error) {
	a, ok := inputs["series_a"].([]float64)
	if !ok {
		return nil, fmt.Errorf("cross_signal: series_a must be []float64, got %T", inputs["series_a"])
	}
	b, ok := inputs["series_b"].([]float64)
	if !ok {
		return nil, fmt.Errorf("cross_signal: series_b must be []float64, got %T", inputs["series_b"])
	}

	minLen := len(a)
	if len(b) < minLen {
		minLen = len(b)
	}
	signals := make([]string, minLen)
	if minLen > 0 {
		signals[0] = "hold"
	}
	for i := 1; i < minLen; i++ {
		switch {
		case a[i-1] <= b[i-1] && a[i] > b[i]:
			signals[i] = "buy"
		case a[i-1] >= b[i-1] && a[i] < b[i]:
			signals[i] = "sell"
		default:
			signals[i] = "hold"
		}
	}

	last := "hold"
	if minLen > 0 {
		last = signals[minLen-1]
	}
	return workflow.NodeOutputs{"signals": signals, "last_signal": last}, nil
}

// ---------------------------------------------------------------------------
// 3. entry_signal — generates entry signal from boolean conditions
// ---------------------------------------------------------------------------

// EntrySignalNode evaluates a set of named boolean conditions using the
// configured logic (AND / OR) and produces a buy signal with the configured
// confidence level when conditions are met.
type EntrySignalNode struct {
	id string
}

func (n *EntrySignalNode) ID() string      { return n.id }
func (n *EntrySignalNode) NodeType() string { return "entry_signal" }
func (n *EntrySignalNode) Category() string { return "signal" }

func (n *EntrySignalNode) InputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "conditions", Type: workflow.PortAny, Required: true},
	}
}

func (n *EntrySignalNode) OutputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "signal", Type: workflow.PortAny, Required: true},
		{Name: "confidence", Type: workflow.PortAny, Required: true},
	}
}

func (n *EntrySignalNode) ParamSchema() []workflow.ParamDef {
	return []workflow.ParamDef{
		{Name: "logic", Type: "string", Default: "AND", Description: "Combination logic: AND (all true) or OR (any true)"},
		{Name: "confidence", Type: "float", Default: 0.8, Description: "Confidence level (0-1) when signal triggered"},
	}
}

func (n *EntrySignalNode) Execute(ctx context.Context, inputs workflow.NodeParams, params workflow.NodeParams) (workflow.NodeOutputs, error) {
	conditions, ok := inputs["conditions"].(map[string]bool)
	if !ok {
		// Accept map[string]any with bool values as a fallback.
		raw, ok2 := inputs["conditions"].(map[string]any)
		if !ok2 {
			return nil, fmt.Errorf("entry_signal: conditions must be map[string]bool, got %T", inputs["conditions"])
		}
		conditions = make(map[string]bool, len(raw))
		for k, v := range raw {
			bv, ok3 := v.(bool)
			if !ok3 {
				return nil, fmt.Errorf("entry_signal: condition %q must be bool, got %T", k, v)
			}
			conditions[k] = bv
		}
	}

	logic := "AND"
	if l, ok := params["logic"].(string); ok && l != "" {
		logic = l
	}

	confidence := 0.8
	if c, ok := params["confidence"].(float64); ok {
		confidence = c
	}

	triggered := false
	switch logic {
	case "OR":
		for _, v := range conditions {
			if v {
				triggered = true
				break
			}
		}
	default: // AND
		triggered = len(conditions) > 0
		for _, v := range conditions {
			if !v {
				triggered = false
				break
			}
		}
	}

	if triggered {
		return workflow.NodeOutputs{"signal": "buy", "confidence": confidence}, nil
	}
	return workflow.NodeOutputs{"signal": "hold", "confidence": 0.0}, nil
}

func (n *EntrySignalNode) Validate() error { return nil }

// ---------------------------------------------------------------------------
// 4. bollinger — Bollinger Bands indicator
// ---------------------------------------------------------------------------

// BollingerNode computes Bollinger Bands (upper, middle, lower) together
// with bandwidth and %b from an input price series.
type BollingerNode struct {
	id string
}

func (n *BollingerNode) ID() string      { return n.id }
func (n *BollingerNode) NodeType() string { return "bollinger" }
func (n *BollingerNode) Category() string { return "indicator" }

func (n *BollingerNode) InputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "series", Type: workflow.PortSeries, Required: true},
	}
}

func (n *BollingerNode) OutputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "upper", Type: workflow.PortSeries, Required: true},
		{Name: "middle", Type: workflow.PortSeries, Required: true},
		{Name: "lower", Type: workflow.PortSeries, Required: true},
		{Name: "bandwidth", Type: workflow.PortSeries, Required: true},
		{Name: "pct_b", Type: workflow.PortSeries, Required: true},
	}
}

func (n *BollingerNode) ParamSchema() []workflow.ParamDef {
	return []workflow.ParamDef{
		{Name: "period", Type: "int", Default: 20, Description: "Moving average period"},
		{Name: "std_dev", Type: "float", Default: 2.0, Description: "Number of standard deviations for bands"},
	}
}

func (n *BollingerNode) Execute(ctx context.Context, inputs workflow.NodeParams, params workflow.NodeParams) (workflow.NodeOutputs, error) {
	series, ok := inputs["series"].([]float64)
	if !ok {
		return nil, fmt.Errorf("bollinger: series must be []float64, got %T", inputs["series"])
	}

	period := 20
	if p, ok := params["period"].(float64); ok {
		period = int(p)
	} else if p, ok := params["period"].(int); ok {
		period = p
	}
	if period < 1 {
		period = 1
	}

	k := 2.0
	if kf, ok := params["std_dev"].(float64); ok {
		k = kf
	}

	nVals := len(series)
	middle := computeSMA(series, period)
	upper := make([]float64, nVals)
	lower := make([]float64, nVals)
	bandwidth := make([]float64, nVals)
	pctB := make([]float64, nVals)

	for i := 0; i < nVals; i++ {
		if i < period-1 || math.IsNaN(middle[i]) {
			upper[i] = math.NaN()
			lower[i] = math.NaN()
			bandwidth[i] = math.NaN()
			pctB[i] = math.NaN()
			continue
		}
		// Rolling standard deviation over [i-period+1 .. i].
		std := rollingStdDev(series, i, period, middle[i])
		upper[i] = middle[i] + k*std
		lower[i] = middle[i] - k*std
		if middle[i] != 0 {
			bandwidth[i] = (upper[i] - lower[i]) / middle[i]
		} else {
			bandwidth[i] = 0
		}
		if upper[i]-lower[i] != 0 {
			pctB[i] = (series[i] - lower[i]) / (upper[i] - lower[i])
		} else {
			pctB[i] = 0.5
		}
	}

	return workflow.NodeOutputs{
		"upper":     upper,
		"middle":    middle,
		"lower":     lower,
		"bandwidth": bandwidth,
		"pct_b":     pctB,
	}, nil
}

func (n *BollingerNode) Validate() error { return nil }

// ---------------------------------------------------------------------------
// 5. sma — Simple Moving Average
// ---------------------------------------------------------------------------

// SMANode computes a simple (equal-weighted) moving average over a sliding
// window of the input series.
type SMANode struct {
	id string
}

func (n *SMANode) ID() string      { return n.id }
func (n *SMANode) NodeType() string { return "sma" }
func (n *SMANode) Category() string { return "indicator" }

func (n *SMANode) InputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "series", Type: workflow.PortSeries, Required: true},
	}
}

func (n *SMANode) OutputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "sma", Type: workflow.PortSeries, Required: true},
	}
}

func (n *SMANode) ParamSchema() []workflow.ParamDef {
	return []workflow.ParamDef{
		{Name: "period", Type: "int", Default: 14, Description: "Moving average period"},
	}
}

func (n *SMANode) Execute(ctx context.Context, inputs workflow.NodeParams, params workflow.NodeParams) (workflow.NodeOutputs, error) {
	series, ok := inputs["series"].([]float64)
	if !ok {
		return nil, fmt.Errorf("sma: series must be []float64, got %T", inputs["series"])
	}
	period := extractIntParam(params, "period", 14)
	if period < 1 {
		period = 1
	}
	return workflow.NodeOutputs{"sma": computeSMA(series, period)}, nil
}

func (n *SMANode) Validate() error { return nil }

// ---------------------------------------------------------------------------
// 6. ema — Exponential Moving Average
// ---------------------------------------------------------------------------

// EMANode computes an exponentially-weighted moving average, giving more
// weight to recent observations.
type EMANode struct {
	id string
}

func (n *EMANode) ID() string      { return n.id }
func (n *EMANode) NodeType() string { return "ema" }
func (n *EMANode) Category() string { return "indicator" }

func (n *EMANode) InputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "series", Type: workflow.PortSeries, Required: true},
	}
}

func (n *EMANode) OutputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "ema", Type: workflow.PortSeries, Required: true},
	}
}

func (n *EMANode) ParamSchema() []workflow.ParamDef {
	return []workflow.ParamDef{
		{Name: "period", Type: "int", Default: 14, Description: "EMA period (smoothing factor = 2/(period+1))"},
	}
}

func (n *EMANode) Execute(ctx context.Context, inputs workflow.NodeParams, params workflow.NodeParams) (workflow.NodeOutputs, error) {
	series, ok := inputs["series"].([]float64)
	if !ok {
		return nil, fmt.Errorf("ema: series must be []float64, got %T", inputs["series"])
	}
	period := extractIntParam(params, "period", 14)
	if period < 1 {
		period = 1
	}
	return workflow.NodeOutputs{"ema": computeEMA(series, period)}, nil
}

func (n *EMANode) Validate() error { return nil }

// ---------------------------------------------------------------------------
// 7. std_dev — Standard Deviation
// ---------------------------------------------------------------------------

// StdDevNode computes the rolling population standard deviation over a
// sliding window of the input series.
type StdDevNode struct {
	id string
}

func (n *StdDevNode) ID() string      { return n.id }
func (n *StdDevNode) NodeType() string { return "std_dev" }
func (n *StdDevNode) Category() string { return "indicator" }

func (n *StdDevNode) InputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "series", Type: workflow.PortSeries, Required: true},
	}
}

func (n *StdDevNode) OutputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "std_dev", Type: workflow.PortAny, Required: true},
		{Name: "values", Type: workflow.PortSeries, Required: true},
	}
}

func (n *StdDevNode) ParamSchema() []workflow.ParamDef {
	return []workflow.ParamDef{
		{Name: "period", Type: "int", Default: 20, Description: "Rolling window period"},
	}
}

func (n *StdDevNode) Execute(ctx context.Context, inputs workflow.NodeParams, params workflow.NodeParams) (workflow.NodeOutputs, error) {
	series, ok := inputs["series"].([]float64)
	if !ok {
		return nil, fmt.Errorf("std_dev: series must be []float64, got %T", inputs["series"])
	}
	period := extractIntParam(params, "period", 20)
	if period < 1 {
		period = 1
	}

	nVals := len(series)
	values := make([]float64, nVals)
	lastStd := 0.0
	for i := 0; i < nVals; i++ {
		if i < period-1 {
			values[i] = math.NaN()
			continue
		}
		mean := 0.0
		for j := i - period + 1; j <= i; j++ {
			mean += series[j]
		}
		mean /= float64(period)

		var sumSq float64
		for j := i - period + 1; j <= i; j++ {
			d := series[j] - mean
			sumSq += d * d
		}
		std := math.Sqrt(sumSq / float64(period))
		values[i] = std
		lastStd = std
	}

	return workflow.NodeOutputs{"std_dev": lastStd, "values": values}, nil
}

func (n *StdDevNode) Validate() error { return nil }

// ---------------------------------------------------------------------------
// 8. delta — Price change / delta
// ---------------------------------------------------------------------------

// DeltaNode computes the absolute and percentage change in a series over
// a configurable lag period.
type DeltaNode struct {
	id string
}

func (n *DeltaNode) ID() string      { return n.id }
func (n *DeltaNode) NodeType() string { return "delta" }
func (n *DeltaNode) Category() string { return "indicator" }

func (n *DeltaNode) InputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "series", Type: workflow.PortSeries, Required: true},
	}
}

func (n *DeltaNode) OutputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "delta", Type: workflow.PortSeries, Required: true},
		{Name: "pct_change", Type: workflow.PortSeries, Required: true},
	}
}

func (n *DeltaNode) ParamSchema() []workflow.ParamDef {
	return []workflow.ParamDef{
		{Name: "period", Type: "int", Default: 1, Description: "Lag period for difference calculation"},
	}
}

func (n *DeltaNode) Execute(ctx context.Context, inputs workflow.NodeParams, params workflow.NodeParams) (workflow.NodeOutputs, error) {
	series, ok := inputs["series"].([]float64)
	if !ok {
		return nil, fmt.Errorf("delta: series must be []float64, got %T", inputs["series"])
	}
	period := extractIntParam(params, "period", 1)
	if period < 1 {
		period = 1
	}

	nVals := len(series)
	delta := make([]float64, nVals)
	pctChange := make([]float64, nVals)

	for i := 0; i < nVals; i++ {
		if i < period {
			delta[i] = 0
			pctChange[i] = 0
			continue
		}
		delta[i] = series[i] - series[i-period]
		if series[i-period] != 0 {
			pctChange[i] = delta[i] / series[i-period]
		} else {
			pctChange[i] = 0
		}
	}

	return workflow.NodeOutputs{"delta": delta, "pct_change": pctChange}, nil
}

func (n *DeltaNode) Validate() error { return nil }

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

// computeSMA returns the simple moving average over the given period.
// The first period-1 elements are math.NaN().
func computeSMA(series []float64, period int) []float64 {
	n := len(series)
	result := make([]float64, n)
	for i := 0; i < n; i++ {
		if i < period-1 {
			result[i] = math.NaN()
			continue
		}
		var sum float64
		for j := i - period + 1; j <= i; j++ {
			sum += series[j]
		}
		result[i] = sum / float64(period)
	}
	return result
}

// computeEMA returns the exponential moving average over the given period.
// The first period-1 elements are math.NaN(); EMA initialises with SMA at
// index period-1.
func computeEMA(series []float64, period int) []float64 {
	n := len(series)
	result := make([]float64, n)
	if n == 0 {
		return result
	}

	multiplier := 2.0 / float64(period+1)

	// Seed with SMA at the first valid index.
	var sum float64
	for i := 0; i < n; i++ {
		if i < period-1 {
			result[i] = math.NaN()
			sum += series[i]
			continue
		}
		if i == period-1 {
			sum += series[i]
			result[i] = sum / float64(period)
		} else {
			result[i] = (series[i]-result[i-1])*multiplier + result[i-1]
		}
	}
	return result
}

// rollingStdDev computes the population standard deviation of series over
// the window [idx-period+1 .. idx] around the given mean.
func rollingStdDev(series []float64, idx, period int, mean float64) float64 {
	var sumSq float64
	for j := idx - period + 1; j <= idx; j++ {
		d := series[j] - mean
		sumSq += d * d
	}
	return math.Sqrt(sumSq / float64(period))
}

// extractIntParam reads an int parameter from params, trying float64 first
// (JSON unmarshalling convention) then int.
func extractIntParam(params workflow.NodeParams, key string, defaultVal int) int {
	if v, ok := params[key]; ok {
		switch val := v.(type) {
		case float64:
			return int(val)
		case int:
			return val
		}
	}
	return defaultVal
}

// ---------------------------------------------------------------------------
// Self-registration via init()
// ---------------------------------------------------------------------------

func init() {
	// Signal nodes
	workflow.DefaultRegistry.RegisterWithCategory("cross_over", func(id string, params workflow.NodeParams) (workflow.BaseNode, error) {
		return &CrossOverNode{id: id}, nil
	}, "signal")

	workflow.DefaultRegistry.RegisterWithCategory("cross_signal", func(id string, params workflow.NodeParams) (workflow.BaseNode, error) {
		return &CrossSignalNode{id: id}, nil
	}, "signal")

	workflow.DefaultRegistry.RegisterWithCategory("entry_signal", func(id string, params workflow.NodeParams) (workflow.BaseNode, error) {
		return &EntrySignalNode{id: id}, nil
	}, "signal")

	// Indicator nodes
	workflow.DefaultRegistry.RegisterWithCategory("bollinger", func(id string, params workflow.NodeParams) (workflow.BaseNode, error) {
		return &BollingerNode{id: id}, nil
	}, "indicator")

	workflow.DefaultRegistry.RegisterWithCategory("sma", func(id string, params workflow.NodeParams) (workflow.BaseNode, error) {
		return &SMANode{id: id}, nil
	}, "indicator")

	workflow.DefaultRegistry.RegisterWithCategory("ema", func(id string, params workflow.NodeParams) (workflow.BaseNode, error) {
		return &EMANode{id: id}, nil
	}, "indicator")

	workflow.DefaultRegistry.RegisterWithCategory("std_dev", func(id string, params workflow.NodeParams) (workflow.BaseNode, error) {
		return &StdDevNode{id: id}, nil
	}, "indicator")

	workflow.DefaultRegistry.RegisterWithCategory("delta", func(id string, params workflow.NodeParams) (workflow.BaseNode, error) {
		return &DeltaNode{id: id}, nil
	}, "indicator")
}
