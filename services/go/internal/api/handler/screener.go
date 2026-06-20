package handler

import (
	"math"
	"net/http"
	"sort"
	"strings"
	"time"

	"github.com/astockpursue/go-core/internal/market"
	"github.com/gin-gonic/gin"
)

// ScreenerHandler provides stock screening and filtering endpoints.
type ScreenerHandler struct {
	ds *market.DataStore
}

func NewScreenerHandler(ds *market.DataStore) *ScreenerHandler {
	return &ScreenerHandler{ds: ds}
}

// Screen filters stocks based on technical and fundamental criteria.
// POST /api/v1/screener
func (h *ScreenerHandler) Screen(c *gin.Context) {
	var req struct {
		Symbols    []string `json:"symbols"`
		Market     string   `json:"market"` // "a_share", "us_equity", "crypto"
		MinPrice   float64  `json:"min_price"`
		MaxPrice   float64  `json:"max_price"`
		MinVolume  int64    `json:"min_volume"`
		Trend      string   `json:"trend"` // "up", "down", "any"
		Limit      int      `json:"limit"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	if len(req.Symbols) == 0 {
		req.Symbols = defaultSymbolsForMarket(req.Market)
	}
	if req.Limit <= 0 || req.Limit > 100 {
		req.Limit = 20
	}

	end := time.Now()
	start := end.Add(-90 * 24 * time.Hour) // 90-day lookback

	type screenResult struct {
		Symbol     string  `json:"symbol"`
		LastPrice  float64 `json:"last_price"`
		AvgVolume  int64   `json:"avg_volume"`
		ChangePct  float64 `json:"change_pct"`
		Volatility float64 `json:"volatility"`
		Passed     bool    `json:"passed"`
	}

	var results []screenResult
	for _, sym := range req.Symbols {
		bars, err := h.ds.GetBars(sym, start, end, "1d")
		if err != nil || len(bars) < 5 {
			continue
		}

		last := bars[len(bars)-1]
		if req.MinPrice > 0 && last.Close < req.MinPrice {
			continue
		}
		if req.MaxPrice > 0 && last.Close > req.MaxPrice {
			continue
		}

		var totalVol int64
		for _, b := range bars {
			totalVol += b.Volume
		}
		avgVol := totalVol / int64(len(bars))
		if req.MinVolume > 0 && avgVol < req.MinVolume {
			continue
		}

		// Trend check
		first := bars[0]
		changePct := (last.Close/first.Close - 1) * 100
		if req.Trend == "up" && changePct < 0 {
			continue
		}
		if req.Trend == "down" && changePct > 0 {
			continue
		}

		// Volatility
		returns := make([]float64, len(bars)-1)
		for i := 1; i < len(bars); i++ {
			returns[i-1] = (bars[i].Close/bars[i-1].Close - 1) * 100
		}
		vol := stdDevFloat(returns)

		results = append(results, screenResult{
			Symbol:     sym,
			LastPrice:  math.Round(last.Close*100) / 100,
			AvgVolume:  avgVol,
			ChangePct:  math.Round(changePct*100) / 100,
			Volatility: math.Round(vol*100) / 100,
			Passed:     true,
		})
	}

	// Sort by change_pct descending
	sort.Slice(results, func(i, j int) bool {
		return results[i].ChangePct > results[j].ChangePct
	})

	if len(results) > req.Limit {
		results = results[:req.Limit]
	}

	c.JSON(http.StatusOK, gin.H{
		"criteria": gin.H{
			"min_price": req.MinPrice, "max_price": req.MaxPrice,
			"min_volume": req.MinVolume, "trend": req.Trend,
		},
		"results": results,
		"count":   len(results),
	})
}

// TopMovers returns top gainers/losers from a watchlist.
// GET /api/v1/screener/movers?market=a_share&direction=up&limit=10
func (h *ScreenerHandler) TopMovers(c *gin.Context) {
	market := c.DefaultQuery("market", "a_share")
	direction := c.DefaultQuery("direction", "up")
	limit := 10

	symbols := defaultSymbolsForMarket(market)
	end := time.Now()
	start := end.Add(-7 * 24 * time.Hour)

	type mover struct {
		Symbol    string  `json:"symbol"`
		ChangePct float64 `json:"change_pct"`
	}

	var results []mover
	for _, sym := range symbols {
		bars, err := h.ds.GetBars(sym, start, end, "1d")
		if err != nil || len(bars) < 2 {
			continue
		}
		first := bars[0]
		last := bars[len(bars)-1]
		change := (last.Close/first.Close - 1) * 100

		if direction == "up" && change <= 0 {
			continue
		}
		if direction == "down" && change >= 0 {
			continue
		}
		results = append(results, mover{Symbol: sym, ChangePct: math.Round(change*100) / 100})
	}

	sort.Slice(results, func(i, j int) bool {
		if direction == "down" {
			return results[i].ChangePct < results[j].ChangePct
		}
		return results[i].ChangePct > results[j].ChangePct
	})

	if len(results) > limit {
		results = results[:limit]
	}

	c.JSON(http.StatusOK, gin.H{"market": market, "direction": direction, "movers": results, "count": len(results)})
}

// MarketOverview returns summary stats for major indices and sectors.
// GET /api/v1/screener/overview
func (h *ScreenerHandler) MarketOverview(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"markets": gin.H{
			"a_share":    gin.H{"status": "active", "description": "沪深京 A 股"},
			"us_equity":  gin.H{"status": "active", "description": "美股"},
			"hk_equity":  gin.H{"status": "active", "description": "港股"},
			"crypto":     gin.H{"status": "active", "description": "加密货币永续合约"},
			"futures":    gin.H{"status": "active", "description": "期货"},
		},
	})
}

func defaultSymbolsForMarket(market string) []string {
	switch strings.ToLower(market) {
	case "a_share":
		return []string{"000001", "600000", "600519", "300750", "000858", "601318", "600036", "000002", "601166", "600276", "002415", "601012"}
	case "us_equity":
		return []string{"AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "WMT"}
	case "hk_equity":
		return []string{"0700", "9988", "0941", "2318", "0005", "0388", "1299"}
	case "crypto":
		return []string{"BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT"}
	default:
		return []string{"000001", "600000", "600519", "AAPL", "TSLA", "BTCUSDT", "ETHUSDT"}
	}
}

func stdDevFloat(v []float64) float64 {
	if len(v) < 2 {
		return 0
	}
	m := 0.0
	for _, x := range v {
		m += x
	}
	m /= float64(len(v))
	s := 0.0
	for _, x := range v {
		d := x - m
		s += d * d
	}
	return math.Sqrt(s / float64(len(v)-1))
}
