// Package nodes provides built-in workflow node implementations for the
// AStockPursue Go workflow engine.  Each node wraps a research service
// (or provides a mock placeholder) and self-registers via init().
package nodes

import (
	"context"
	"fmt"
	"math"
	"time"

	"github.com/astockpursue/go-core/internal/research"
	"github.com/astockpursue/go-core/internal/workflow"
)

// ---------------------------------------------------------------------------
// 1. FinancialsNode — wraps FinancialsService.Analyze
// ---------------------------------------------------------------------------

// FinancialsNode exposes fundamental financial metrics (revenue, profit,
// margins, ratios) for a given A-share symbol via the FinancialsService.
type FinancialsNode struct {
	id      string
	service *research.FinancialsService
}

func (n *FinancialsNode) ID() string      { return n.id }
func (n *FinancialsNode) NodeType() string { return "financials" }
func (n *FinancialsNode) Category() string { return "research" }

func (n *FinancialsNode) InputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "symbol", Type: workflow.PortParams, Required: true},
	}
}

func (n *FinancialsNode) OutputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "result", Type: workflow.PortParams},
	}
}

func (n *FinancialsNode) ParamSchema() []workflow.ParamDef { return nil }

func (n *FinancialsNode) Execute(ctx context.Context, inputs map[string]any, params map[string]any) (map[string]any, error) {
	symbol, ok := inputs["symbol"].(string)
	if !ok {
		return nil, fmt.Errorf("financials: symbol must be a string, got %T", inputs["symbol"])
	}
	return n.service.Analyze(ctx, symbol, nil)
}

func (n *FinancialsNode) Validate() error { return nil }

// ---------------------------------------------------------------------------
// 2. GeopoliticsNode — wraps GeopoliticsService.Analyze
// ---------------------------------------------------------------------------

// GeopoliticsNode provides geopolitical risk assessments across 10
// pre-configured GDELT-tracked topics (US-China trade, Taiwan Strait,
// South China Sea, etc.).
type GeopoliticsNode struct {
	id      string
	service *research.GeopoliticsService
}

func (n *GeopoliticsNode) ID() string      { return n.id }
func (n *GeopoliticsNode) NodeType() string { return "geopolitics" }
func (n *GeopoliticsNode) Category() string { return "research" }

func (n *GeopoliticsNode) InputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "symbol", Type: workflow.PortParams, Required: false},
	}
}

func (n *GeopoliticsNode) OutputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "result", Type: workflow.PortParams},
	}
}

func (n *GeopoliticsNode) ParamSchema() []workflow.ParamDef { return nil }

func (n *GeopoliticsNode) Execute(ctx context.Context, inputs map[string]any, params map[string]any) (map[string]any, error) {
	symbol, _ := inputs["symbol"].(string)
	return n.service.Analyze(ctx, symbol, nil)
}

func (n *GeopoliticsNode) Validate() error { return nil }

// ---------------------------------------------------------------------------
// 3. NorthboundNode — wraps NorthboundService.Analyze
// ---------------------------------------------------------------------------

// NorthboundNode tracks northbound capital flows (Stock Connect) for a given
// A-share symbol — daily/weekly/monthly net inflow, cumulative net buy,
// top-10 active stocks, and sector distribution.
type NorthboundNode struct {
	id      string
	service *research.NorthboundService
}

func (n *NorthboundNode) ID() string      { return n.id }
func (n *NorthboundNode) NodeType() string { return "northbound" }
func (n *NorthboundNode) Category() string { return "research" }

func (n *NorthboundNode) InputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "symbol", Type: workflow.PortParams, Required: true},
	}
}

func (n *NorthboundNode) OutputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "result", Type: workflow.PortParams},
	}
}

func (n *NorthboundNode) ParamSchema() []workflow.ParamDef { return nil }

func (n *NorthboundNode) Execute(ctx context.Context, inputs map[string]any, params map[string]any) (map[string]any, error) {
	symbol, ok := inputs["symbol"].(string)
	if !ok {
		return nil, fmt.Errorf("northbound: symbol must be a string, got %T", inputs["symbol"])
	}
	return n.service.Analyze(ctx, symbol, nil)
}

func (n *NorthboundNode) Validate() error { return nil }

// ---------------------------------------------------------------------------
// 4. NewsNode — wraps NewsService.Analyze
// ---------------------------------------------------------------------------

// NewsNode aggregates multi-source news with sentiment analysis for a given
// A-share symbol.  Returns recent articles, overall sentiment, sentiment
// change, key topics, and source count.
type NewsNode struct {
	id      string
	service *research.NewsService
}

func (n *NewsNode) ID() string      { return n.id }
func (n *NewsNode) NodeType() string { return "news" }
func (n *NewsNode) Category() string { return "research" }

func (n *NewsNode) InputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "symbol", Type: workflow.PortParams, Required: true},
	}
}

func (n *NewsNode) OutputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "result", Type: workflow.PortParams},
	}
}

func (n *NewsNode) ParamSchema() []workflow.ParamDef { return nil }

func (n *NewsNode) Execute(ctx context.Context, inputs map[string]any, params map[string]any) (map[string]any, error) {
	symbol, ok := inputs["symbol"].(string)
	if !ok {
		return nil, fmt.Errorf("news: symbol must be a string, got %T", inputs["symbol"])
	}
	return n.service.Analyze(ctx, symbol, nil)
}

func (n *NewsNode) Validate() error { return nil }

// ---------------------------------------------------------------------------
// 5. SentimentNode — wraps NewsService.Analyze, returns sentiment-only subset
// ---------------------------------------------------------------------------

// SentimentNode returns a sentiment-focused subset of the news analysis:
// overall_sentiment (-1..+1), sentiment_change, and key_topics.  It wraps
// NewsService.Analyze under the hood but filters the output to sentiment
// fields only.
type SentimentNode struct {
	id      string
	service *research.NewsService
}

func (n *SentimentNode) ID() string      { return n.id }
func (n *SentimentNode) NodeType() string { return "sentiment" }
func (n *SentimentNode) Category() string { return "research" }

func (n *SentimentNode) InputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "symbol", Type: workflow.PortParams, Required: true},
	}
}

func (n *SentimentNode) OutputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "result", Type: workflow.PortParams},
	}
}

func (n *SentimentNode) ParamSchema() []workflow.ParamDef { return nil }

func (n *SentimentNode) Execute(ctx context.Context, inputs map[string]any, params map[string]any) (map[string]any, error) {
	symbol, ok := inputs["symbol"].(string)
	if !ok {
		return nil, fmt.Errorf("sentiment: symbol must be a string, got %T", inputs["symbol"])
	}
	full, err := n.service.Analyze(ctx, symbol, nil)
	if err != nil {
		return nil, err
	}
	// Return sentiment-specific subset
	result := make(map[string]any)
	if v, ok := full["overall_sentiment"]; ok {
		result["overall_sentiment"] = v
	}
	if v, ok := full["sentiment_change"]; ok {
		result["sentiment_change"] = v
	}
	if v, ok := full["key_topics"]; ok {
		result["key_topics"] = v
	}
	return result, nil
}

func (n *SentimentNode) Validate() error { return nil }

// ---------------------------------------------------------------------------
// 6. AnalystEstimatesNode — placeholder (service not yet built)
// ---------------------------------------------------------------------------

// AnalystEstimatesNode returns mock analyst consensus estimates for a given
// A-share symbol.  The real AnalystEstimatesService is planned but not yet
// implemented; this node provides structure and mock data for flow testing.
type AnalystEstimatesNode struct {
	id string
}

func (n *AnalystEstimatesNode) ID() string      { return n.id }
func (n *AnalystEstimatesNode) NodeType() string { return "analyst_estimates" }
func (n *AnalystEstimatesNode) Category() string { return "research" }

func (n *AnalystEstimatesNode) InputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "symbol", Type: workflow.PortParams, Required: true},
	}
}

func (n *AnalystEstimatesNode) OutputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "result", Type: workflow.PortParams},
	}
}

func (n *AnalystEstimatesNode) ParamSchema() []workflow.ParamDef { return nil }

func (n *AnalystEstimatesNode) Execute(ctx context.Context, inputs map[string]any, params map[string]any) (map[string]any, error) {
	symbol, ok := inputs["symbol"].(string)
	if !ok {
		return nil, fmt.Errorf("analyst_estimates: symbol must be a string, got %T", inputs["symbol"])
	}
	return mockAnalystEstimates(symbol), nil
}

func (n *AnalystEstimatesNode) Validate() error { return nil }

// mockAnalystEstimates returns placeholder analyst consensus data for the
// given symbol.  Values are calibrated to realistic A-share analyst estimate
// ranges.
func mockAnalystEstimates(symbol string) map[string]any {
	seed := hashStr(symbol)
	now := time.Now().Format(time.RFC3339)

	return map[string]any{
		"symbol":             symbol,
		"consensus_target":   round2(18.0 + seed*15),
		"consensus_eps":      round2(0.85 + seed*0.6),
		"consensus_revenue":  round2(5.2e9 + seed*3e9),
		"num_analysts":       int(8 + seed*12),
		"strong_buy":         int(2 + seed*4),
		"buy":                int(3 + seed*5),
		"hold":               int(2 + seed*3),
		"sell":               int(math.Max(0, seed*2)),
		"target_high":        round2(18.0 + seed*15 + 5),
		"target_low":         round2(18.0 + seed*15 - 5),
		"revision_trend":     round2(seed*0.1 - 0.02),
		"updated_at":         now,
	}
}

// ---------------------------------------------------------------------------
// 7. InsiderTradesNode — placeholder (returns mock insider transaction data)
// ---------------------------------------------------------------------------

// InsiderTradesNode returns mock insider (executive / large shareholder)
// transaction data for a given A-share symbol.  The real InsiderTradesService
// is planned but not yet implemented; this node provides structure and mock
// data for flow testing.
type InsiderTradesNode struct {
	id string
}

func (n *InsiderTradesNode) ID() string      { return n.id }
func (n *InsiderTradesNode) NodeType() string { return "insider_trades" }
func (n *InsiderTradesNode) Category() string { return "research" }

func (n *InsiderTradesNode) InputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "symbol", Type: workflow.PortParams, Required: true},
	}
}

func (n *InsiderTradesNode) OutputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "result", Type: workflow.PortParams},
	}
}

func (n *InsiderTradesNode) ParamSchema() []workflow.ParamDef { return nil }

func (n *InsiderTradesNode) Execute(ctx context.Context, inputs map[string]any, params map[string]any) (map[string]any, error) {
	symbol, ok := inputs["symbol"].(string)
	if !ok {
		return nil, fmt.Errorf("insider_trades: symbol must be a string, got %T", inputs["symbol"])
	}
	return mockInsiderTrades(symbol), nil
}

func (n *InsiderTradesNode) Validate() error { return nil }

// mockInsiderTrades returns placeholder insider transaction data for the
// given symbol.  Values include recent buy/sell transactions by executives
// and large shareholders, and net insider activity metrics.
func mockInsiderTrades(symbol string) map[string]any {
	seed := hashStr(symbol)
	now := time.Now().Format(time.RFC3339)
	thirtyDaysAgo := time.Now().Add(-30 * 24 * time.Hour).Format(time.RFC3339)
	sixtyDaysAgo := time.Now().Add(-60 * 24 * time.Hour).Format(time.RFC3339)

	netBuy := seed*5e7 - 1e7

	trades := []map[string]any{
		{
			"insider_name":   "张三",
			"insider_title":  "董事长",
			"trade_type":     "buy",
			"shares":         int(50000 + seed*200000),
			"avg_price":      round2(15.0 + seed*10),
			"trade_value":    round2(750000 + seed*3e6),
			"trade_date":     thirtyDaysAgo,
			"holding_change": round2(0.5 + seed*1.5),
		},
		{
			"insider_name":   "李四",
			"insider_title":  "财务总监",
			"trade_type":     "sell",
			"shares":         int(10000 + seed*50000),
			"avg_price":      round2(15.0 + seed*10 + 1),
			"trade_value":    round2(150000 + seed*750000),
			"trade_date":     sixtyDaysAgo,
			"holding_change": round2(-0.3 - seed*0.5),
		},
		{
			"insider_name":   "王五",
			"insider_title":  "副总经理",
			"trade_type":     "buy",
			"shares":         int(20000 + seed*80000),
			"avg_price":      round2(15.0 + seed*10 - 0.5),
			"trade_value":    round2(300000 + seed*1.2e6),
			"trade_date":     thirtyDaysAgo,
			"holding_change": round2(0.2 + seed*0.8),
		},
	}

	return map[string]any{
		"symbol":          symbol,
		"recent_trades":   trades,
		"net_buy_30d":     round2(netBuy),
		"net_buy_90d":     round2(netBuy * 1.5),
		"buy_count":       int(2 + seed*4),
		"sell_count":      int(1 + seed*2),
		"insider_sentiment": func() string {
			if netBuy > 0 {
				return "bullish"
			}
			return "bearish"
		}(),
		"updated_at": now,
	}
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

// hashStr returns a deterministic pseudo-random float in [-0.5, 0.5) derived
// from the given string.  It uses a simple multiplicative hash.
func hashStr(s string) float64 {
	var h uint64
	for _, c := range s {
		h = h*31 + uint64(c)
	}
	return float64(h%100)/100.0 - 0.5
}

// round2 rounds a float64 to 2 decimal places.
func round2(v float64) float64 {
	return math.Round(v*100) / 100
}

// ---------------------------------------------------------------------------
// Self-registration via init()
// ---------------------------------------------------------------------------

func init() {
	workflow.DefaultRegistry.Register("financials", func(id string, params map[string]any) (workflow.BaseNode, error) {
		return &FinancialsNode{id: id, service: nil}, nil // service wired later
	})

	workflow.DefaultRegistry.Register("geopolitics", func(id string, params map[string]any) (workflow.BaseNode, error) {
		return &GeopoliticsNode{id: id, service: nil}, nil // service wired later
	})

	workflow.DefaultRegistry.Register("northbound", func(id string, params map[string]any) (workflow.BaseNode, error) {
		return &NorthboundNode{id: id, service: nil}, nil // service wired later
	})

	workflow.DefaultRegistry.Register("news", func(id string, params map[string]any) (workflow.BaseNode, error) {
		return &NewsNode{id: id, service: nil}, nil // service wired later
	})

	workflow.DefaultRegistry.Register("sentiment", func(id string, params map[string]any) (workflow.BaseNode, error) {
		return &SentimentNode{id: id, service: nil}, nil // service wired later
	})

	workflow.DefaultRegistry.Register("analyst_estimates", func(id string, params map[string]any) (workflow.BaseNode, error) {
		return &AnalystEstimatesNode{id: id}, nil
	})

	workflow.DefaultRegistry.Register("insider_trades", func(id string, params map[string]any) (workflow.BaseNode, error) {
		return &InsiderTradesNode{id: id}, nil
	})
}
