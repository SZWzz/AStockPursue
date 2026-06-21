package handler

import (
	"context"
	"net/http"
	"strconv"
	"time"

	"github.com/astockpursue/go-core/internal/research"
	"github.com/gin-gonic/gin"
)

// ResearchHandler exposes HTTP endpoints for multi-source research analysis
// (financials, geopolitics, northbound flows, news sentiment).
type ResearchHandler struct {
	services map[string]research.Service
}

// NewResearchHandler creates a ResearchHandler with the given service map.
// Keys should be the service type names: "financials", "geopolitics",
// "northbound", "news". A nil map or missing services are handled gracefully
// at runtime by returning a 400 error.
func NewResearchHandler(services map[string]research.Service) *ResearchHandler {
	if services == nil {
		services = make(map[string]research.Service)
	}
	return &ResearchHandler{services: services}
}

// Analyze performs research analysis for a given symbol.
//
//	GET /api/v1/research/:type?symbol=600519
//
// Supported types: financials, geopolitics, northbound, news.
// For geopolitics, the symbol query parameter is optional (analysis is global).
func (h *ResearchHandler) Analyze(c *gin.Context) {
	svcType := c.Param("type")
	symbol := c.Query("symbol")

	svc, ok := h.services[svcType]
	if !ok {
		c.JSON(http.StatusBadRequest, gin.H{
			"error":           "unsupported research type: " + svcType,
			"supported_types": []string{"financials", "geopolitics", "northbound", "news"},
		})
		return
	}

	if svcType != "geopolitics" && symbol == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "symbol query parameter is required for " + svcType})
		return
	}

	ctx, cancel := context.WithTimeout(c.Request.Context(), 10*time.Second)
	defer cancel()

	result, err := svc.Analyze(ctx, symbol, nil)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"type": svcType,
		"data": result,
	})
}

// History returns cached historical data points for a symbol and research type.
//
//	GET /api/v1/research/:type/:symbol/history?days=30
//
// The days parameter controls how many days of history to return (default 30,
// max 365). For geopolitics, symbol can be any value (it is ignored by the
// underlying service).
func (h *ResearchHandler) History(c *gin.Context) {
	svcType := c.Param("type")
	symbol := c.Param("symbol")

	svc, ok := h.services[svcType]
	if !ok {
		c.JSON(http.StatusBadRequest, gin.H{
			"error":           "unsupported research type: " + svcType,
			"supported_types": []string{"financials", "geopolitics", "northbound", "news"},
		})
		return
	}

	daysStr := c.DefaultQuery("days", "30")
	days, err := strconv.Atoi(daysStr)
	if err != nil || days < 1 || days > 365 {
		c.JSON(http.StatusBadRequest, gin.H{"error": "days must be an integer between 1 and 365"})
		return
	}

	ctx, cancel := context.WithTimeout(c.Request.Context(), 10*time.Second)
	defer cancel()

	history, err := svc.History(ctx, symbol, days)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"type":   svcType,
		"symbol": symbol,
		"days":   days,
		"data":   history,
		"count":  len(history),
	})
}
