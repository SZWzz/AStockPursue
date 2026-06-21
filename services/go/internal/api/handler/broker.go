package handler

import (
	"context"
	"fmt"
	"net/http"
	"time"

	"github.com/astockpursue/go-core/internal/broker"
	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5/pgxpool"
)

// BrokerHandler provides broker account endpoints.
type BrokerHandler struct {
	binance broker.Broker
	okx     broker.Broker
	brokers map[string]broker.Broker
	db      *pgxpool.Pool
}

// NewBrokerHandler creates a handler with optional broker connections.
// Pass nil for brokers that are not configured.
func NewBrokerHandler(binance, okx broker.Broker, db *pgxpool.Pool) *BrokerHandler {
	h := &BrokerHandler{binance: binance, okx: okx, db: db, brokers: make(map[string]broker.Broker)}
	if binance != nil {
		h.brokers["binance"] = binance
	}
	if okx != nil {
		h.brokers["okx"] = okx
	}
	return h
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

// Connect tests and connects to a broker.
// POST /api/v1/broker/connect
func (h *BrokerHandler) Connect(c *gin.Context) {
	var req struct{ BrokerID string `json:"broker_id"` }
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	b, ok := h.brokers[req.BrokerID]
	if !ok {
		c.JSON(http.StatusNotFound, gin.H{"error": "broker not found: " + req.BrokerID, "available": broker.List()})
		return
	}

	ctx, cancel := context.WithTimeout(c.Request.Context(), 5*time.Second)
	defer cancel()

	if err := b.TestConnection(ctx); err != nil {
		c.JSON(http.StatusBadGateway, gin.H{"status": "failed", "broker_id": req.BrokerID, "error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"status": "connected", "broker_id": req.BrokerID})
}

// Disconnect marks a broker as disconnected (broker instances are long-lived; clear credentials to fully disconnect).
// POST /api/v1/broker/disconnect
func (h *BrokerHandler) Disconnect(c *gin.Context) {
	var req struct{ BrokerID string `json:"broker_id"` }
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if _, ok := h.brokers[req.BrokerID]; !ok {
		c.JSON(http.StatusNotFound, gin.H{"error": "broker not found: " + req.BrokerID, "available": broker.List()})
		return
	}

	// Broker instances are long-lived; to fully disconnect, clear stored credentials.
	c.JSON(http.StatusOK, gin.H{"status": "disconnected", "broker_id": req.BrokerID, "note": "Broker interface has no Close(); clear credentials to fully disconnect"})
}

// SaveCredentials stores broker API credentials in user_settings JSONB.
// POST /api/v1/broker/credentials
func (h *BrokerHandler) SaveCredentials(c *gin.Context) {
	var req struct {
		BrokerID  string `json:"broker_id"`
		APIKey    string `json:"api_key"`
		APISecret string `json:"api_secret"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if h.db != nil {
		_, err := h.db.Exec(c.Request.Context(),
			`INSERT INTO user_settings (user_id, settings) VALUES (1, $1)
			 ON CONFLICT (user_id) DO UPDATE SET settings = user_settings.settings || $1, updated_at = now()`,
			fmt.Sprintf(`{"broker_credentials":{"%s":{"api_key":"%s","api_secret":"%s"}}}`,
				req.BrokerID, req.APIKey, req.APISecret))
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}
	}

	c.JSON(http.StatusOK, gin.H{"status": "credentials_saved", "broker_id": req.BrokerID})
}
