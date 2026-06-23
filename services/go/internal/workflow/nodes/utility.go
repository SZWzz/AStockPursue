// Package nodes provides built-in workflow node implementations for the
// AStockPursue Go workflow engine.  This file contains utility nodes:
// scaling, arithmetic, scheduling, alerting, branching, and merging.
package nodes

import (
	"context"
	"fmt"
	"math"
	"strconv"
	"strings"
	"time"

	"github.com/astockpursue/go-core/internal/workflow"
	"github.com/google/uuid"
)

// ---------------------------------------------------------------------------
// 1. scale — normalises a series using min-max or z-score
// ---------------------------------------------------------------------------

// ScaleNode normalises an input float64 series using the chosen method
// (minmax or zscore).
type ScaleNode struct {
	id string
}

func (n *ScaleNode) ID() string      { return n.id }
func (n *ScaleNode) NodeType() string { return "scale" }
func (n *ScaleNode) Category() string { return "utility" }

func (n *ScaleNode) InputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "series", Type: workflow.PortSeries, Required: true},
	}
}

func (n *ScaleNode) OutputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "scaled", Type: workflow.PortSeries, Required: true},
	}
}

func (n *ScaleNode) ParamSchema() []workflow.ParamDef {
	return []workflow.ParamDef{
		{Name: "method", Type: "string", Default: "minmax", Description: "Scaling method: minmax or zscore"},
		{Name: "range_min", Type: "float", Default: 0.0, Description: "Target range minimum (minmax only)"},
		{Name: "range_max", Type: "float", Default: 1.0, Description: "Target range maximum (minmax only)"},
	}
}

func (n *ScaleNode) Execute(ctx context.Context, inputs workflow.NodeParams, params workflow.NodeParams) (workflow.NodeOutputs, error) {
	series, ok := inputs["series"].([]float64)
	if !ok {
		return nil, fmt.Errorf("scale: series must be []float64, got %T", inputs["series"])
	}
	if len(series) == 0 {
		return workflow.NodeOutputs{"scaled": []float64{}}, nil
	}

	method := "minmax"
	if m, ok := params["method"].(string); ok && m != "" {
		method = m
	}

	switch method {
	case "zscore":
		return scaleZScore(series)
	default: // minmax
		rangeMin := 0.0
		rangeMax := 1.0
		if v, ok := params["range_min"].(float64); ok {
			rangeMin = v
		}
		if v, ok := params["range_max"].(float64); ok {
			rangeMax = v
		}
		return scaleMinMax(series, rangeMin, rangeMax)
	}
}

func (n *ScaleNode) Validate() error { return nil }

// scaleMinMax rescales series linearly into [rangeMin, rangeMax].
func scaleMinMax(series []float64, rangeMin, rangeMax float64) (workflow.NodeOutputs, error) {
	min, max := series[0], series[0]
	for _, v := range series {
		if v < min {
			min = v
		}
		if v > max {
			max = v
		}
	}

	scaled := make([]float64, len(series))
	if max-min == 0 {
		// Flat series — map every value to the midpoint of the target range.
		mid := (rangeMin + rangeMax) / 2
		for i := range series {
			scaled[i] = mid
		}
	} else {
		span := rangeMax - rangeMin
		for i, v := range series {
			scaled[i] = rangeMin + (v-min)/(max-min)*span
		}
	}
	return workflow.NodeOutputs{"scaled": scaled}, nil
}

// scaleZScore standardises series to mean=0, std=1.
func scaleZScore(series []float64) (workflow.NodeOutputs, error) {
	n := float64(len(series))
	var sum, sumSq float64
	for _, v := range series {
		sum += v
		sumSq += v * v
	}
	mean := sum / n
	variance := (sumSq / n) - (mean * mean)
	std := math.Sqrt(variance)

	scaled := make([]float64, len(series))
	if std == 0 {
		for i := range series {
			scaled[i] = 0
		}
	} else {
		for i, v := range series {
			scaled[i] = (v - mean) / std
		}
	}
	return workflow.NodeOutputs{"scaled": scaled}, nil
}

// ---------------------------------------------------------------------------
// 2. arithmetic — performs basic arithmetic between two floats
// ---------------------------------------------------------------------------

// ArithmeticNode applies a configurable binary operation (add, sub, mul, div)
// to two input float64 values.
type ArithmeticNode struct {
	id string
}

func (n *ArithmeticNode) ID() string      { return n.id }
func (n *ArithmeticNode) NodeType() string { return "arithmetic" }
func (n *ArithmeticNode) Category() string { return "utility" }

func (n *ArithmeticNode) InputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "a", Type: workflow.PortAny, Required: true},
		{Name: "b", Type: workflow.PortAny, Required: true},
	}
}

func (n *ArithmeticNode) OutputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "result", Type: workflow.PortAny, Required: true},
	}
}

func (n *ArithmeticNode) ParamSchema() []workflow.ParamDef {
	return []workflow.ParamDef{
		{Name: "op", Type: "string", Default: "add", Description: "Operation: add, sub, mul, div"},
	}
}

func (n *ArithmeticNode) Execute(ctx context.Context, inputs workflow.NodeParams, params workflow.NodeParams) (workflow.NodeOutputs, error) {
	a, err := toFloat64(inputs["a"])
	if err != nil {
		return nil, fmt.Errorf("arithmetic: a must be numeric, got %T", inputs["a"])
	}
	b, err := toFloat64(inputs["b"])
	if err != nil {
		return nil, fmt.Errorf("arithmetic: b must be numeric, got %T", inputs["b"])
	}

	op := "add"
	if o, ok := params["op"].(string); ok && o != "" {
		op = o
	}

	var result float64
	switch op {
	case "add":
		result = a + b
	case "sub":
		result = a - b
	case "mul":
		result = a * b
	case "div":
		if b == 0 {
			return nil, fmt.Errorf("arithmetic: division by zero")
		}
		result = a / b
	default:
		return nil, fmt.Errorf("arithmetic: unknown op %q", op)
	}

	return workflow.NodeOutputs{"result": result}, nil
}

func (n *ArithmeticNode) Validate() error { return nil }

// toFloat64 converts an input value to float64, supporting float64, int,
// and json.Number types.
func toFloat64(v any) (float64, error) {
	switch val := v.(type) {
	case float64:
		return val, nil
	case int:
		return float64(val), nil
	case int64:
		return float64(val), nil
	case string:
		return strconv.ParseFloat(val, 64)
	default:
		return 0, fmt.Errorf("cannot convert %T to float64", v)
	}
}

// ---------------------------------------------------------------------------
// 3. schedule — mock schedule node that computes next cron-like trigger
// ---------------------------------------------------------------------------

// ScheduleNode represents a scheduled trigger that fires according to a
// cron expression. The next_run is computed from a simple 5-field cron
// parser; trigger_count is a mock counter.
type ScheduleNode struct {
	id string
}

func (n *ScheduleNode) ID() string      { return n.id }
func (n *ScheduleNode) NodeType() string { return "schedule" }
func (n *ScheduleNode) Category() string { return "schedule" }

func (n *ScheduleNode) InputPorts() []workflow.PortDef { return nil }

func (n *ScheduleNode) OutputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "next_run", Type: workflow.PortAny, Required: true},
		{Name: "trigger_count", Type: workflow.PortAny, Required: true},
	}
}

func (n *ScheduleNode) ParamSchema() []workflow.ParamDef {
	return []workflow.ParamDef{
		{Name: "cron", Type: "string", Default: "0 9 * * 1-5", Description: "Cron expression (5 fields: min hour dom mon dow)"},
		{Name: "timezone", Type: "string", Default: "Asia/Shanghai", Description: "IANA timezone identifier"},
	}
}

func (n *ScheduleNode) Execute(ctx context.Context, inputs workflow.NodeParams, params workflow.NodeParams) (workflow.NodeOutputs, error) {
	cronExpr := "0 9 * * 1-5"
	if c, ok := params["cron"].(string); ok && c != "" {
		cronExpr = c
	}

	tzName := "Asia/Shanghai"
	if tz, ok := params["timezone"].(string); ok && tz != "" {
		tzName = tz
	}
	loc, err := time.LoadLocation(tzName)
	if err != nil {
		loc = time.UTC
	}

	now := time.Now().In(loc)
	next := nextCronTime(cronExpr, now)

	return workflow.NodeOutputs{
		"next_run":      next.Format(time.RFC3339),
		"trigger_count": 0, // mock; real counter requires persistent state
	}, nil
}

func (n *ScheduleNode) Validate() error { return nil }

// nextCronTime computes the next time after `from` that matches the given
// 5-field cron expression (minute hour day-of-month month day-of-week).
// Supports * (wildcard), specific values, comma-separated lists, and
// range expressions (e.g. 1-5).  Step syntax (/N) is not implemented.
func nextCronTime(expr string, from time.Time) time.Time {
	fields := strings.Fields(expr)
	if len(fields) != 5 {
		return from.Add(time.Minute)
	}

	// Parse each field into a set of valid values.
	minSet := parseCronField(fields[0], 0, 59)
	hourSet := parseCronField(fields[1], 0, 23)
	domSet := parseCronField(fields[2], 1, 31)
	monSet := parseCronField(fields[3], 1, 12)
	dowSet := parseCronField(fields[4], 0, 6)

	// Start search from the next full minute.
	t := from.Truncate(time.Minute).Add(time.Minute)

	// Bound search to one year to avoid infinite loops.
	deadline := from.AddDate(1, 0, 0)

	for t.Before(deadline) {
		if !monSet[int(t.Month())] {
			t = time.Date(t.Year(), t.Month()+1, 1, 0, 0, 0, 0, t.Location())
			continue
		}
		if !domSet[t.Day()] {
			t = t.AddDate(0, 0, 1)
			t = time.Date(t.Year(), t.Month(), t.Day(), 0, 0, 0, 0, t.Location())
			continue
		}
		if !dowSet[int(t.Weekday())] {
			t = t.AddDate(0, 0, 1)
			t = time.Date(t.Year(), t.Month(), t.Day(), 0, 0, 0, 0, t.Location())
			continue
		}
		if !hourSet[t.Hour()] {
			t = t.Add(time.Hour)
			t = time.Date(t.Year(), t.Month(), t.Day(), t.Hour(), 0, 0, 0, t.Location())
			continue
		}
		if !minSet[t.Minute()] {
			t = t.Add(time.Minute)
			continue
		}
		// All fields match
		return t
	}

	return from.Add(time.Minute)
}

// parseCronField parses a single cron field into a set of valid integer
// values within [minVal, maxVal].  Supports * (wildcard), N (literal),
// A,B (comma list), and A-B (range).
func parseCronField(field string, minVal, maxVal int) map[int]bool {
	set := make(map[int]bool)

	if field == "*" {
		for i := minVal; i <= maxVal; i++ {
			set[i] = true
		}
		return set
	}

	parts := strings.Split(field, ",")
	for _, part := range parts {
		part = strings.TrimSpace(part)
		if part == "" {
			continue
		}
		if strings.Contains(part, "-") {
			// Range: A-B
			bounds := strings.SplitN(part, "-", 2)
			if len(bounds) != 2 {
				continue
			}
			lo, err1 := strconv.Atoi(strings.TrimSpace(bounds[0]))
			hi, err2 := strconv.Atoi(strings.TrimSpace(bounds[1]))
			if err1 != nil || err2 != nil {
				continue
			}
			if lo < minVal {
				lo = minVal
			}
			if hi > maxVal {
				hi = maxVal
			}
			for i := lo; i <= hi; i++ {
				set[i] = true
			}
		} else {
			// Single value (could be with /N step but we ignore step)
			n, err := strconv.Atoi(part)
			if err != nil {
				continue
			}
			if n >= minVal && n <= maxVal {
				set[n] = true
			}
		}
	}

	// If nothing was parsed, default to wildcard.
	if len(set) == 0 {
		for i := minVal; i <= maxVal; i++ {
			set[i] = true
		}
	}
	return set
}

// ---------------------------------------------------------------------------
// 4. alert — triggers an alert based on a boolean condition
// ---------------------------------------------------------------------------

// AlertNode evaluates a boolean condition and, if true, generates an alert
// with the configured severity level and a unique alert ID.
type AlertNode struct {
	id string
}

func (n *AlertNode) ID() string      { return n.id }
func (n *AlertNode) NodeType() string { return "alert" }
func (n *AlertNode) Category() string { return "notify" }

func (n *AlertNode) InputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "condition", Type: workflow.PortAny, Required: true},
		{Name: "message", Type: workflow.PortAny, Required: true},
	}
}

func (n *AlertNode) OutputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "triggered", Type: workflow.PortAny, Required: true},
		{Name: "alert_id", Type: workflow.PortAny, Required: true},
	}
}

func (n *AlertNode) ParamSchema() []workflow.ParamDef {
	return []workflow.ParamDef{
		{Name: "level", Type: "string", Default: "info", Description: "Alert level: info, warning, error"},
	}
}

func (n *AlertNode) Execute(ctx context.Context, inputs workflow.NodeParams, params workflow.NodeParams) (workflow.NodeOutputs, error) {
	condition, ok := inputs["condition"].(bool)
	if !ok {
		return nil, fmt.Errorf("alert: condition must be bool, got %T", inputs["condition"])
	}

	message, _ := inputs["message"].(string)

	level := "info"
	if l, ok := params["level"].(string); ok && l != "" {
		level = l
	}

	if condition {
		alertID := uuid.New().String()
		_ = message
		_ = level
		return workflow.NodeOutputs{
			"triggered": true,
			"alert_id":  alertID,
		}, nil
	}
	return workflow.NodeOutputs{
		"triggered": false,
		"alert_id":  "",
	}, nil
}

func (n *AlertNode) Validate() error { return nil }

// ---------------------------------------------------------------------------
// 5. branch — routes execution flow based on a boolean condition
// ---------------------------------------------------------------------------

// BranchNode acts as a control-flow gate: it passes the incoming boolean
// condition through one of two output ports (true_branch or false_branch).
type BranchNode struct {
	id string
}

func (n *BranchNode) ID() string      { return n.id }
func (n *BranchNode) NodeType() string { return "branch" }
func (n *BranchNode) Category() string { return "control" }

func (n *BranchNode) InputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "condition", Type: workflow.PortAny, Required: true},
	}
}

func (n *BranchNode) OutputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "true_branch", Type: workflow.PortAny, Required: true},
		{Name: "false_branch", Type: workflow.PortAny, Required: true},
	}
}

func (n *BranchNode) ParamSchema() []workflow.ParamDef { return nil }

func (n *BranchNode) Execute(ctx context.Context, inputs workflow.NodeParams, params workflow.NodeParams) (workflow.NodeOutputs, error) {
	condition, ok := inputs["condition"].(bool)
	if !ok {
		return nil, fmt.Errorf("branch: condition must be bool, got %T", inputs["condition"])
	}

	return workflow.NodeOutputs{
		"true_branch":  condition,
		"false_branch": !condition,
	}, nil
}

func (n *BranchNode) Validate() error { return nil }

// ---------------------------------------------------------------------------
// 6. merge — merges two branches into a single output
// ---------------------------------------------------------------------------

// MergeNode combines two input values (branch_a, branch_b) into a single
// output.  It uses branch_a when available, falling back to branch_b.
type MergeNode struct {
	id string
}

func (n *MergeNode) ID() string      { return n.id }
func (n *MergeNode) NodeType() string { return "merge" }
func (n *MergeNode) Category() string { return "control" }

func (n *MergeNode) InputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "branch_a", Type: workflow.PortAny, Required: false},
		{Name: "branch_b", Type: workflow.PortAny, Required: false},
	}
}

func (n *MergeNode) OutputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "merged", Type: workflow.PortAny, Required: true},
	}
}

func (n *MergeNode) ParamSchema() []workflow.ParamDef { return nil }

func (n *MergeNode) Execute(ctx context.Context, inputs workflow.NodeParams, params workflow.NodeParams) (workflow.NodeOutputs, error) {
	// Prefer branch_a over branch_b; if neither is set, return nil.
	if a, ok := inputs["branch_a"]; ok {
		return workflow.NodeOutputs{"merged": a}, nil
	}
	if b, ok := inputs["branch_b"]; ok {
		return workflow.NodeOutputs{"merged": b}, nil
	}
	return workflow.NodeOutputs{"merged": nil}, nil
}

func (n *MergeNode) Validate() error { return nil }

// ---------------------------------------------------------------------------
// Self-registration via init()
// ---------------------------------------------------------------------------

func init() {
	workflow.DefaultRegistry.RegisterWithCategory("scale", func(id string, params workflow.NodeParams) (workflow.BaseNode, error) {
		return &ScaleNode{id: id}, nil
	}, "utility")

	workflow.DefaultRegistry.RegisterWithCategory("arithmetic", func(id string, params workflow.NodeParams) (workflow.BaseNode, error) {
		return &ArithmeticNode{id: id}, nil
	}, "utility")

	workflow.DefaultRegistry.RegisterWithCategory("schedule", func(id string, params workflow.NodeParams) (workflow.BaseNode, error) {
		return &ScheduleNode{id: id}, nil
	}, "schedule")

	workflow.DefaultRegistry.RegisterWithCategory("alert", func(id string, params workflow.NodeParams) (workflow.BaseNode, error) {
		return &AlertNode{id: id}, nil
	}, "notify")

	workflow.DefaultRegistry.RegisterWithCategory("branch", func(id string, params workflow.NodeParams) (workflow.BaseNode, error) {
		return &BranchNode{id: id}, nil
	}, "control")

	workflow.DefaultRegistry.RegisterWithCategory("merge", func(id string, params workflow.NodeParams) (workflow.BaseNode, error) {
		return &MergeNode{id: id}, nil
	}, "control")
}
