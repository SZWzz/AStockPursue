package handler

import (
	"math"
	"net/http"
	"time"

	"github.com/astockpursue/go-core/internal/market"
	"github.com/gin-gonic/gin"
)

// AnalysisHandler provides portfolio analysis and statistics endpoints.
type AnalysisHandler struct {
	ds *market.DataStore
}

func NewAnalysisHandler(ds *market.DataStore) *AnalysisHandler {
	return &AnalysisHandler{ds: ds}
}

// Correlation computes pairwise correlation between symbols.
// POST /api/v1/analysis/correlation
func (h *AnalysisHandler) Correlation(c *gin.Context) {
	var req struct {
		Symbols   []string `json:"symbols" binding:"required"`
		StartDate string   `json:"start_date" binding:"required"`
		EndDate   string   `json:"end_date" binding:"required"`
		Frequency string   `json:"frequency"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	if req.Frequency == "" {
		req.Frequency = "1d"
	}

	// Load data for all symbols
	series := make(map[string][]float64)
	for _, sym := range req.Symbols {
		bars, err := h.ds.GetBars(sym, parseDate(req.StartDate), parseDate(req.EndDate), req.Frequency)
		if err != nil || len(bars) == 0 {
			continue
		}
		closes := make([]float64, len(bars))
		for i, b := range bars {
			closes[i] = b.Close
		}
		series[sym] = closes
	}

	// Compute pairwise correlations
	pairs := make([]gin.H, 0)
	symbols := req.Symbols
	for i := 0; i < len(symbols); i++ {
		for j := i + 1; j < len(symbols); j++ {
			a, b := symbols[i], symbols[j]
			sa, okA := series[a]
			sb, okB := series[b]
			if !okA || !okB {
				continue
			}
			corr := pearsonCorrelation(sa, sb)
			pairs = append(pairs, gin.H{
				"pair":        []string{a, b},
				"correlation": math.Round(corr*10000) / 10000,
			})
		}
	}

	c.JSON(http.StatusOK, gin.H{
		"symbols":       req.Symbols,
		"correlations":  pairs,
		"pairs_count":   len(pairs),
	})
}

// Drawdown computes maximum drawdown for a symbol over a period.
// GET /api/v1/analysis/drawdown?symbol=000001&start=2026-01-01&end=2026-06-01
func (h *AnalysisHandler) Drawdown(c *gin.Context) {
	symbol := c.Query("symbol")
	startStr := c.Query("start")
	endStr := c.Query("end")
	freq := c.DefaultQuery("freq", "1d")

	if symbol == "" || startStr == "" || endStr == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "symbol, start, end required"})
		return
	}

	bars, err := h.ds.GetBars(symbol, parseDate(startStr), parseDate(endStr), freq)
	if err != nil || len(bars) == 0 {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "no data for " + symbol})
		return
	}

	closes := make([]float64, len(bars))
	for i, b := range bars {
		closes[i] = b.Close
	}

	maxDD, maxDDStart, maxDDEnd := computeDrawdown(closes)
	returns := computeReturns(closes)
	vol := stdDev(returns) * math.Sqrt(252)

	c.JSON(http.StatusOK, gin.H{
		"symbol":          symbol,
		"bars":            len(bars),
		"start_price":     math.Round(closes[0]*100) / 100,
		"end_price":       math.Round(closes[len(closes)-1]*100) / 100,
		"total_return_pct": math.Round((closes[len(closes)-1]/closes[0]-1)*10000) / 100,
		"max_drawdown_pct": math.Round(maxDD*10000) / 100,
		"max_dd_start":    maxDDStart,
		"max_dd_end":      maxDDEnd,
		"annual_volatility": math.Round(vol*10000) / 100,
	})
}

// Attribution performs simple factor attribution on a portfolio.
// POST /api/v1/analysis/attribution
func (h *AnalysisHandler) Attribution(c *gin.Context) {
	var req struct {
		BacktestID string `json:"backtest_id"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// Stub: Python gRPC analysis not yet wired
	c.JSON(http.StatusOK, gin.H{
		"message": "Full attribution analysis available via Python gRPC (coming soon). Use Python MCP tool `factor_analysis` for now.",
		"backtest_id": req.BacktestID,
	})
}

// StressTest runs a simple stress scenario.
// POST /api/v1/analysis/stress-test
func (h *AnalysisHandler) StressTest(c *gin.Context) {
	var req struct {
		Symbols      []string `json:"symbols" binding:"required"`
		ScenarioPct  float64  `json:"scenario_pct"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	if req.ScenarioPct == 0 {
		req.ScenarioPct = -20 // default: 20% market crash
	}

	scenarios := map[string]float64{
		"market_crash": req.ScenarioPct,
		"moderate_drop": req.ScenarioPct / 2,
		"mild_drop": req.ScenarioPct / 4,
	}

	type result struct {
		Scenario string  `json:"scenario"`
		Symbol   string  `json:"symbol"`
		ImpactPct float64 `json:"impact_pct"`
	}
	var results []result
	for _, sym := range req.Symbols {
		for name, pct := range scenarios {
			results = append(results, result{
				Scenario:  name,
				Symbol:    sym,
				ImpactPct: pct,
			})
		}
	}

	c.JSON(http.StatusOK, gin.H{
		"scenarios": results,
		"count":     len(results),
	})
}

// ── Math helpers ──────────────────────────────────────────────────

func pearsonCorrelation(x, y []float64) float64 {
	n := min(len(x), len(y))
	if n < 2 {
		return 0
	}
	x = x[:n]
	y = y[:n]

	mx, my := mean(x), mean(y)
	var sx, sy, sxy float64
	for i := 0; i < n; i++ {
		dx := x[i] - mx
		dy := y[i] - my
		sx += dx * dx
		sy += dy * dy
		sxy += dx * dy
	}
	if sx == 0 || sy == 0 {
		return 0
	}
	return sxy / math.Sqrt(sx*sy)
}

func computeDrawdown(prices []float64) (maxDD float64, startIdx, endIdx int) {
	peak := prices[0]
	peakIdx := 0
	for i, p := range prices {
		if p > peak {
			peak = p
			peakIdx = i
		}
		dd := (peak - p) / peak
		if dd > maxDD {
			maxDD = dd
			startIdx = peakIdx
			endIdx = i
		}
	}
	return
}

func computeReturns(prices []float64) []float64 {
	r := make([]float64, len(prices)-1)
	for i := 1; i < len(prices); i++ {
		r[i-1] = prices[i]/prices[i-1] - 1
	}
	return r
}

func mean(v []float64) float64 {
	s := 0.0
	for _, x := range v {
		s += x
	}
	return s / float64(len(v))
}

func stdDev(v []float64) float64 {
	m := mean(v)
	s := 0.0
	for _, x := range v {
		d := x - m
		s += d * d
	}
	return math.Sqrt(s / float64(len(v)))
}

func parseDate(s string) time.Time {
	t, _ := time.Parse("2006-01-02", s)
	return t
}
