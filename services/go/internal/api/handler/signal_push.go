package handler

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"

	"github.com/astockpursue/go-core/internal/notify"
	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5/pgxpool"
)

// SignalPushHandler manages signal push subscription settings and test pushes.
type SignalPushHandler struct {
	db    *pgxpool.Pool
	notif *notify.Manager
}

// NewSignalPushHandler creates a new SignalPushHandler.
func NewSignalPushHandler(db *pgxpool.Pool, notif *notify.Manager) *SignalPushHandler {
	return &SignalPushHandler{db: db, notif: notif}
}

// PushSubscription represents the user's push subscription configuration.
type PushSubscription struct {
	Enabled  bool                       `json:"enabled"`
	Channels map[string]json.RawMessage `json:"channels"`
}

// GetSubscriptionStatus returns the current signal push subscription for the authenticated user.
// GET /api/v1/signals/subscription/status
func (h *SignalPushHandler) GetSubscriptionStatus(c *gin.Context) {
	userID, err := h.getUserID(c)
	if err != nil {
		c.JSON(http.StatusUnauthorized, gin.H{"error": err.Error()})
		return
	}

	if h.db == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "database unavailable"})
		return
	}

	var enabled bool
	var channels []byte
	err = h.db.QueryRow(context.Background(),
		"SELECT signal_push_enabled, push_channels FROM user_settings WHERE user_id = $1",
		userID,
	).Scan(&enabled, &channels)

	if err != nil {
		c.JSON(http.StatusOK, PushSubscription{Enabled: false, Channels: map[string]json.RawMessage{}})
		return
	}

	var chMap map[string]json.RawMessage
	if len(channels) > 0 {
		json.Unmarshal(channels, &chMap)
	}
	if chMap == nil {
		chMap = map[string]json.RawMessage{}
	}

	c.JSON(http.StatusOK, PushSubscription{Enabled: enabled, Channels: chMap})
}

// UpdateSubscription updates the signal push subscription for the authenticated user.
// PUT /api/v1/signals/subscription
func (h *SignalPushHandler) UpdateSubscription(c *gin.Context) {
	userID, err := h.getUserID(c)
	if err != nil {
		c.JSON(http.StatusUnauthorized, gin.H{"error": err.Error()})
		return
	}

	var req PushSubscription
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if h.db == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "database unavailable"})
		return
	}

	if req.Channels == nil {
		req.Channels = map[string]json.RawMessage{}
	}

	channelsJSON, err := json.Marshal(req.Channels)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to marshal channels: " + err.Error()})
		return
	}

	_, err = h.db.Exec(c.Request.Context(),
		`INSERT INTO user_settings (user_id, signal_push_enabled, push_channels)
		 VALUES ($1, $2, $3)
		 ON CONFLICT (user_id) DO UPDATE SET signal_push_enabled = $2, push_channels = $3, updated_at = now()`,
		userID, req.Enabled, channelsJSON,
	)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, req)
}

// TestPush sends a test notification through the configured push channels.
// POST /api/v1/signals/subscription/test
func (h *SignalPushHandler) TestPush(c *gin.Context) {
	userID, err := h.getUserID(c)
	if err != nil {
		c.JSON(http.StatusUnauthorized, gin.H{"error": err.Error()})
		return
	}

	var req struct {
		Channel string          `json:"channel" binding:"required"`
		Config  json.RawMessage `json:"config"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if h.notif == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "notification manager unavailable"})
		return
	}

	// Build a test message with channel metadata
	metadata := map[string]string{
		"channel": req.Channel,
		"user_id": fmt.Sprintf("%d", userID),
	}
	if len(req.Config) > 0 {
		metadata["config"] = string(req.Config)
	}
	_ = userID // used for logging / future audit

	msg := &notify.Message{
		Level:    notify.LevelInfo,
		Title:    "信号推送测试",
		Body:     "这是一条来自AStockPursue平台的信号推送测试消息。",
		Metadata: metadata,
	}

	h.notif.Send(msg)

	c.JSON(http.StatusOK, gin.H{
		"status":  "sent",
		"channel": req.Channel,
		"message": "test push enqueued",
	})
}

// getUserID extracts the authenticated user ID from the Gin context.
func (h *SignalPushHandler) getUserID(c *gin.Context) (int, error) {
	uid, exists := c.Get("user_id")
	if !exists {
		return 0, fmt.Errorf("authentication required")
	}
	id, ok := uid.(int)
	if !ok {
		return 0, fmt.Errorf("invalid user id type")
	}
	return id, nil
}
