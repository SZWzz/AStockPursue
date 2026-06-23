package handler

import (
	"context"
	"encoding/json"
	"log"
	"net/http"
	"time"

	"github.com/astockpursue/go-core/internal/broker"
	"github.com/astockpursue/go-core/internal/crypto"
	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5/pgxpool"
)

// BrokerHandler provides broker account endpoints.
type BrokerHandler struct {
	binance          broker.Broker
	okx              broker.Broker
	brokers          map[string]broker.Broker
	db               *pgxpool.Pool
	passwordVerifier func(userID int, password string) bool
	revealLimiter    *RateLimiter // 3 reveal attempts per minute per IP
}

// NewBrokerHandler creates a handler with optional broker connections.
// Pass nil for brokers that are not configured.
func NewBrokerHandler(binance, okx broker.Broker, db *pgxpool.Pool) *BrokerHandler {
	h := &BrokerHandler{
		binance:       binance,
		okx:           okx,
		db:            db,
		brokers:       make(map[string]broker.Broker),
		revealLimiter: NewRateLimiter(time.Minute, 3),
	}
	if binance != nil {
		h.brokers["binance"] = binance
	}
	if okx != nil {
		h.brokers["okx"] = okx
	}
	return h
}

// SetPasswordVerifier sets the function used to verify user passwords
// when revealing full credentials.
func (h *BrokerHandler) SetPasswordVerifier(v func(userID int, password string) bool) {
	h.passwordVerifier = v
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

	userID := h.getUserID(c)
	if userID == 0 {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "user not authenticated"})
		return
	}

	if h.db != nil {
		encryptedSecret, err := crypto.Encrypt(req.APISecret)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to encrypt credentials"})
			return
		}

		credential := map[string]interface{}{
			"api_key":    req.APIKey,
			"api_secret": encryptedSecret,
		}
		brokerCreds := map[string]interface{}{
			req.BrokerID: credential,
		}
		settings := map[string]interface{}{
			"broker_credentials": brokerCreds,
		}
		body, err := json.Marshal(settings)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to marshal credentials"})
			return
		}

		_, err = h.db.Exec(c.Request.Context(),
			`INSERT INTO user_settings (user_id, settings) VALUES ($1, $2)
			 ON CONFLICT (user_id) DO UPDATE SET settings = user_settings.settings || $2, updated_at = now()`,
			userID, string(body))
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}
	}

	c.JSON(http.StatusOK, gin.H{"status": "credentials_saved", "broker_id": req.BrokerID})
}

// maskString masks a sensitive string for safe display.
// Shows first 3 and last 4 characters, replacing the middle with "****".
func maskString(s string) string {
	if len(s) <= 8 {
		return "****"
	}
	return s[:3] + "-****" + s[len(s)-4:]
}

// GetCredentials retrieves masked broker API credentials from user_settings.
// GET /api/v1/broker/credentials
func (h *BrokerHandler) GetCredentials(c *gin.Context) {
	userID := h.getUserID(c)
	if userID == 0 {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "user not authenticated"})
		return
	}

	if h.db == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "database not available"})
		return
	}

	var settingsJSON []byte
	err := h.db.QueryRow(c.Request.Context(),
		`SELECT settings FROM user_settings WHERE user_id = $1`, userID,
	).Scan(&settingsJSON)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "no settings found"})
		return
	}

	var settings map[string]interface{}
	if err := json.Unmarshal(settingsJSON, &settings); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to read settings"})
		return
	}

	if creds, ok := settings["broker_credentials"].(map[string]interface{}); ok {
		for brokerID, v := range creds {
			if cred, ok := v.(map[string]interface{}); ok {
				// Mask API key
				if apiKey, ok := cred["api_key"].(string); ok {
					cred["api_key"] = maskString(apiKey)
				}
				// Mask API secret
				if apiSecret, ok := cred["api_secret"].(string); ok {
					cred["api_secret"] = maskString(apiSecret)
				}
				_ = brokerID
			}
		}
	}

	c.JSON(http.StatusOK, settings["broker_credentials"])
}

// RevealCredentials decrypts and returns full broker API credentials.
// Requires current password re-verification.
// POST /api/v1/broker/credentials/reveal
func (h *BrokerHandler) RevealCredentials(c *gin.Context) {
	userID := h.getUserID(c)
	if userID == 0 {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "user not authenticated"})
		return
	}

	// Rate limit: 3 reveal attempts per minute per IP (prevents brute-force)
	clientIP := c.ClientIP()
	if !h.revealLimiter.Allow(clientIP) {
		c.JSON(http.StatusTooManyRequests, gin.H{"error": "too many reveal attempts, try again later"})
		return
	}

	var req struct {
		CurrentPassword string `json:"current_password" binding:"required"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "current_password is required"})
		return
	}

	// Verify password — requires access to AuthHandler's password verification
	// For now, check against user settings or use auth handler reference
	// The caller must provide a password verifier function
	if h.passwordVerifier == nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "password verification not configured"})
		return
	}

	if !h.passwordVerifier(userID, req.CurrentPassword) {
		c.JSON(http.StatusForbidden, gin.H{"error": "incorrect password"})
		return
	}

	if h.db == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "database not available"})
		return
	}

	var settingsJSON []byte
	err := h.db.QueryRow(c.Request.Context(),
		`SELECT settings FROM user_settings WHERE user_id = $1`, userID,
	).Scan(&settingsJSON)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "no settings found"})
		return
	}

	var settings map[string]interface{}
	if err := json.Unmarshal(settingsJSON, &settings); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to read settings"})
		return
	}

	if creds, ok := settings["broker_credentials"].(map[string]interface{}); ok {
		for brokerID, v := range creds {
			if cred, ok := v.(map[string]interface{}); ok {
				if encryptedSecret, ok := cred["api_secret"].(string); ok {
					decrypted, err := crypto.Decrypt(encryptedSecret)
					if err != nil {
						continue
					}
					cred["api_secret"] = decrypted
				}
			}
			_ = brokerID
		}
	}

	log.Printf("audit: user_id=%d revealed full broker credentials", userID)
	c.JSON(http.StatusOK, settings["broker_credentials"])
}

func (h *BrokerHandler) getUserID(c *gin.Context) int {
	if uid, exists := c.Get("user_id"); exists {
		return uid.(int)
	}
	return 0 // Will cause 401 in calling handler
}
