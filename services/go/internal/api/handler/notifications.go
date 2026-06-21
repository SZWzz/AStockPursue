package handler

import (
	"net/http"
	"strconv"

	"github.com/astockpursue/go-core/internal/notify"
	"github.com/gin-gonic/gin"
)

// NotificationHandler exposes HTTP endpoints for notification management and
// dispatch.
type NotificationHandler struct {
	manager *notify.Manager
}

// NewNotificationHandler creates a NotificationHandler backed by the given Manager.
func NewNotificationHandler(manager *notify.Manager) *NotificationHandler {
	return &NotificationHandler{manager: manager}
}

// ── Request types ───────────────────────────────────────────────────

type sendNotificationRequest struct {
	Level    string            `json:"level" binding:"required"`
	Title    string            `json:"title" binding:"required"`
	Body     string            `json:"body"`
	Metadata map[string]string `json:"metadata"`
}

// ── Handlers ────────────────────────────────────────────────────────

// List returns paginated notification history.
//
//	GET /api/v1/notifications?limit=50&offset=0
func (h *NotificationHandler) List(c *gin.Context) {
	limitStr := c.DefaultQuery("limit", "50")
	offsetStr := c.DefaultQuery("offset", "0")

	limit, err := strconv.Atoi(limitStr)
	if err != nil || limit < 1 || limit > 200 {
		c.JSON(http.StatusBadRequest, gin.H{"error": "limit must be an integer between 1 and 200"})
		return
	}
	offset, err := strconv.Atoi(offsetStr)
	if err != nil || offset < 0 {
		c.JSON(http.StatusBadRequest, gin.H{"error": "offset must be a non-negative integer"})
		return
	}

	notifications, err := h.manager.GetHistory(limit, offset)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	if notifications == nil {
		notifications = []*notify.Notification{}
	}

	unreadCount := 0
	for _, n := range notifications {
		if !n.IsRead {
			unreadCount++
		}
	}

	c.JSON(http.StatusOK, gin.H{
		"notifications": notifications,
		"count":         len(notifications),
		"unread_count":  unreadCount,
		"limit":         limit,
		"offset":        offset,
	})
}

// Send dispatches a notification through all registered notifiers.
//
//	POST /api/v1/notifications
func (h *NotificationHandler) Send(c *gin.Context) {
	var req sendNotificationRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	level := notify.Level(req.Level)
	switch level {
	case notify.LevelInfo, notify.LevelWarning, notify.LevelError:
		// valid
	default:
		c.JSON(http.StatusBadRequest, gin.H{
			"error":           "invalid level: " + req.Level,
			"supported_levels": []string{"info", "warning", "error"},
		})
		return
	}

	if req.Metadata == nil {
		req.Metadata = make(map[string]string)
	}

	msg := &notify.Message{
		Level:    level,
		Title:    req.Title,
		Body:     req.Body,
		Metadata: req.Metadata,
	}

	h.manager.Send(msg)

	c.JSON(http.StatusAccepted, gin.H{
		"message": "notification enqueued",
		"level":   string(level),
		"title":   req.Title,
	})
}

// MarkRead marks a notification as read.
//
//	POST /api/v1/notifications/:id/read
func (h *NotificationHandler) MarkRead(c *gin.Context) {
	id := c.Param("id")

	if err := h.manager.MarkRead(id); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"message": "notification marked as read",
		"id":      id,
	})
}
