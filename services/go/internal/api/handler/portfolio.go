package handler

import (
	"net/http"

	"github.com/astockpursue/go-core/internal/engine"
	"github.com/gin-gonic/gin"
)

// PortfolioHandler provides portfolio status and analysis endpoints.
type PortfolioHandler struct {
	runner *engine.LiveTradingRunner
}

func NewPortfolioHandler(runner *engine.LiveTradingRunner) *PortfolioHandler {
	return &PortfolioHandler{runner: runner}
}

// GetStatus returns the current portfolio state.
// GET /api/v1/portfolio
func (h *PortfolioHandler) GetStatus(c *gin.Context) {
	p := h.runner.Portfolio()
	positions := make([]gin.H, 0, len(p.Positions))
	totalValue := p.Cash
	for _, pos := range p.Positions {
		marketValue := pos.Size * pos.CurrentPrice
		totalValue += marketValue
		positions = append(positions, gin.H{
			"symbol":        pos.Symbol,
			"size":          pos.Size,
			"entry_price":   pos.EntryPrice,
			"current_price": pos.CurrentPrice,
			"market_value":  marketValue,
			"unrealized_pnl": pos.UnrealizedPnL(),
			"side":          pos.Side(),
		})
	}

	c.JSON(http.StatusOK, gin.H{
		"cash":            p.Cash,
		"equity":          p.Equity,
		"total_value":     totalValue,
		"position_count":  len(positions),
		"positions":       positions,
		"trading_status":  h.runner.Status(),
	})
}
