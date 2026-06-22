package handler

import (
	"net/http"
	"time"

	"github.com/astockpursue/go-core/internal/market"
	"github.com/gin-gonic/gin"
)

// MarketHandler provides market data endpoints for the frontend.
type MarketHandler struct {
	ds *market.DataStore
}

func NewMarketHandler(ds *market.DataStore) *MarketHandler {
	return &MarketHandler{ds: ds}
}

// GetBars fetches OHLCV bars for a symbol and date range.
// GET /api/v1/market/bars?symbol=000001&start=2026-01-01&end=2026-01-10&freq=1d
func (h *MarketHandler) GetBars(c *gin.Context) {
	symbol := market.NormalizeSymbol(c.Query("symbol"))
	startStr := c.Query("start")
	endStr := c.Query("end")
	freq := c.DefaultQuery("freq", "1d")

	if symbol == "" || startStr == "" || endStr == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "symbol, start, end required"})
		return
	}

	start, err := time.Parse("2006-01-02", startStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid start date, use YYYY-MM-DD"})
		return
	}
	end, err := time.Parse("2006-01-02", endStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid end date, use YYYY-MM-DD"})
		return
	}
	if !end.After(start) {
		c.JSON(http.StatusBadRequest, gin.H{"error": "end must be after start"})
		return
	}

	bars, err := h.ds.GetBars(symbol, start, end, freq)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"symbol": symbol, "frequency": freq, "bars": bars, "count": len(bars)})
}

// ListSymbols returns commonly-used symbols grouped by market.
// TODO: query symbols from DB/data provider when available
// GET /api/v1/market/symbols
func (h *MarketHandler) ListSymbols(c *gin.Context) {
	symbols := map[string][]string{
		"a_share":  {"000001", "600000", "600519", "300750", "000858", "601318"},
		"us_equity": {"AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA"},
		"hk_equity": {"0700", "9988", "0941", "2318"},
		"crypto":   {"BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"},
	}
	c.JSON(http.StatusOK, gin.H{"markets": symbols})
}
