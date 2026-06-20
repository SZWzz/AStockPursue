package handler

import (
	"net/http"

	"github.com/astockpursue/go-core/internal/broker"
	"github.com/gin-gonic/gin"
)

// BrokerHandler provides broker account endpoints.
type BrokerHandler struct {
	binance broker.Broker
	okx     broker.Broker
}

// NewBrokerHandler creates a handler with optional broker connections.
// Pass nil for brokers that are not configured.
func NewBrokerHandler(binance, okx broker.Broker) *BrokerHandler {
	return &BrokerHandler{binance: binance, okx: okx}
}

// GetAccount returns combined account info from all connected brokers.
// GET /api/v1/broker/account
func (h *BrokerHandler) GetAccount(c *gin.Context) {
	result := make(map[string]interface{})

	if h.binance != nil {
		if bal, err := h.binance.GetBalance(c.Request.Context()); err == nil {
			result["binance"] = gin.H{
				"balance":   bal,
				"connected": true,
			}
		}
	}
	if h.okx != nil {
		if bal, err := h.okx.GetBalance(c.Request.Context()); err == nil {
			result["okx"] = gin.H{
				"balance":   bal,
				"connected": true,
			}
		}
	}

	if len(result) == 0 {
		// Return available brokers even if not connected
		names := broker.List()
		result["available"] = names
		result["connected"] = false
	}

	c.JSON(http.StatusOK, result)
}

// GetPositions returns open positions from all connected brokers.
// GET /api/v1/broker/positions
func (h *BrokerHandler) GetPositions(c *gin.Context) {
	allPositions := make(map[string]interface{})

	if h.binance != nil {
		if pos, err := h.binance.GetPositions(c.Request.Context()); err == nil {
			allPositions["binance"] = pos
		}
	}
	if h.okx != nil {
		if pos, err := h.okx.GetPositions(c.Request.Context()); err == nil {
			allPositions["okx"] = pos
		}
	}

	c.JSON(http.StatusOK, gin.H{"positions": allPositions})
}

// GetBrokers lists all available/registered brokers.
// GET /api/v1/broker/list
func (h *BrokerHandler) GetBrokers(c *gin.Context) {
	names := broker.List()
	status := make([]gin.H, 0, len(names))
	for _, name := range names {
		status = append(status, gin.H{"name": name, "registered": true})
	}
	c.JSON(http.StatusOK, gin.H{"brokers": status})
}
