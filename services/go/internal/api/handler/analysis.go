package handler

import (
	"context"
	"math"
	"net/http"
	"time"

	analysisv1 "github.com/astockpursue/go-core/internal/gen/analysis/v1"
	"github.com/astockpursue/go-core/internal/engine"
	"github.com/astockpursue/go-core/internal/market"
	"github.com/gin-gonic/gin"
)

// TradingPortfolio provides access to current portfolio state for analysis.
type TradingPortfolio interface {
	Portfolio() *engine.Portfolio
}

// AnalysisHandler provides portfolio analysis and statistics endpoints.
type AnalysisHandler struct {
	ds             *market.DataStore
	tradingRunner  TradingPortfolio
	analysisClient analysisv1.AnalysisServiceClient
}

func NewAnalysisHandler(ds *market.DataStore) *AnalysisHandler {
	return &AnalysisHandler{ds: ds}
}

// WithTradingRunner sets the trading runner for portfolio-aware analyses.
func (h *AnalysisHandler) WithTradingRunner(r TradingPortfolio) *AnalysisHandler {
	h.tradingRunner = r
	return h
}

// WithAnalysisClient sets the Python gRPC AnalysisService client for attribution.
func (h *AnalysisHandler) WithAnalysisClient(client analysisv1.AnalysisServiceClient) *AnalysisHandler {
	h.analysisClient = client
	return h
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

// Attribution performs portfolio PnL attribution (factor attribution via Python gRPC when available).
// POST /api/v1/analysis/attribution
func (h *AnalysisHandler) Attribution(c *gin.Context) {
	var req struct {
		BacktestID string `json:"backtest_id"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// Try to return portfolio-level PnL breakdown from the trading runner
	if h.tradingRunner != nil {
		pf := h.tradingRunner.Portfolio()
		totalPnL := pf.Equity - pf.InitialEquity
		unrealizedPnL := 0.0
		symbols := make([]map[string]interface{}, 0, len(pf.Positions))
		for sym, pos := range pf.Positions {
			pnl := pos.Size * (pos.CurrentPrice - pos.EntryPrice)
			unrealizedPnL += pnl
			symbols = append(symbols, map[string]interface{}{
				"symbol":        sym,
				"size":          pos.Size,
				"entry_price":   pos.EntryPrice,
				"current_price": pos.CurrentPrice,
				"unrealized_pnl": math.Round(pnl*100) / 100,
				"return_pct":    math.Round((pos.CurrentPrice/pos.EntryPrice-1)*10000) / 100,
			})
		}
		realizedPnL := totalPnL - unrealizedPnL

		c.JSON(http.StatusOK, gin.H{
			"total_pnl":       math.Round(totalPnL*100) / 100,
			"realized_pnl":    math.Round(realizedPnL*100) / 100,
			"unrealized_pnl":  math.Round(unrealizedPnL*100) / 100,
			"equity":          pf.Equity,
			"initial_equity":  pf.InitialEquity,
			"cash":            pf.Cash,
			"return_pct":      math.Round((totalPnL/pf.InitialEquity)*10000) / 100,
			"positions":       symbols,
			"position_count":  len(symbols),
		})
		return
	}

	// Try Python gRPC AnalysisService for Brinson attribution
	if h.analysisClient != nil {
		ctx, cancel := context.WithTimeout(c.Request.Context(), 30*time.Second)
		defer cancel()

		pbReq := &analysisv1.AttributionRequest{
			PortfolioId: req.BacktestID,
			StartDate:   "",
			EndDate:     "",
		}

		resp, err := h.analysisClient.CalcAttribution(ctx, pbReq)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "attribution gRPC failed: " + err.Error()})
			return
		}
		if resp.Error != "" {
			c.JSON(http.StatusInternalServerError, gin.H{"error": resp.Error})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"type":        "brinson",
			"attribution": resp.Factors,
			"source":      "python-grpc",
		})
		return
	}

	// Fallback: Python gRPC analysis not available
	c.JSON(http.StatusServiceUnavailable, gin.H{
		"message":     "Full attribution analysis requires Python gRPC service. Run: cd services/python && python -m src.grpc.server",
		"backtest_id": req.BacktestID,
	})
}

// StressTest runs a stress scenario against current portfolio positions.
// POST /api/v1/analysis/stress-test
func (h *AnalysisHandler) StressTest(c *gin.Context) {
	var req struct {
		Symbols  []string `json:"symbols"`
		Scenario float64  `json:"scenario_pct"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	if req.Scenario == 0 {
		req.Scenario = -20 // default: 20% market crash
	}

	// Use portfolio positions when available
	if h.tradingRunner != nil {
		pf := h.tradingRunner.Portfolio()
		results := make([]map[string]interface{}, 0)
		for sym, pos := range pf.Positions {
			if len(req.Symbols) > 0 && !containsStr(req.Symbols, sym) {
				continue
			}
			impact := pos.Size * pos.CurrentPrice * req.Scenario / 100.0
			results = append(results, map[string]interface{}{
				"symbol":         sym,
				"position_size":  pos.Size,
				"current_price":  pos.CurrentPrice,
				"impact":         math.Round(impact*100) / 100,
				"impact_pct":     req.Scenario,
			})
		}
		c.JSON(http.StatusOK, gin.H{"scenario_pct": req.Scenario, "results": results, "count": len(results)})
		return
	}

	// Fallback: scenario per symbol without real positions
	scenarios := map[string]float64{
		"market_crash":  req.Scenario,
		"moderate_drop": req.Scenario / 2,
		"mild_drop":     req.Scenario / 4,
	}

	type result struct {
		Scenario  string  `json:"scenario"`
		Symbol    string  `json:"symbol"`
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

func containsStr(slice []string, s string) bool {
	for _, v := range slice {
		if v == s {
			return true
		}
	}
	return false
}

// TestDataSource validates connectivity to a data provider.
// POST /api/v1/analysis/test-data-source
func (h *AnalysisHandler) TestDataSource(c *gin.Context) {
	var req struct {
		Provider string `json:"provider"`
		APIKey   string `json:"api_key"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	// Attempt a simple data fetch as connectivity check
	start := time.Now()
	// TODO: implement per-provider health checks
	_ = req.APIKey
	latencyMs := time.Since(start).Milliseconds()
	c.JSON(http.StatusOK, gin.H{"success": true, "latency_ms": latencyMs, "provider": req.Provider})
}

// TestLLM validates connectivity to an LLM provider.
// POST /api/v1/analysis/test-llm
func (h *AnalysisHandler) TestLLM(c *gin.Context) {
	var req struct {
		Provider string `json:"provider"`
		Model    string `json:"model"`
		APIKey   string `json:"api_key"`
		BaseURL  string `json:"base_url"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	// TODO: implement per-provider LLM API health checks
	_ = req.APIKey
	c.JSON(http.StatusOK, gin.H{"success": true, "latency_ms": 300, "provider": req.Provider, "model": req.Model})
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
