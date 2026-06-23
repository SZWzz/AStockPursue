package handler

import (
	"crypto/rand"
	"encoding/hex"
	"net/http"
	"strings"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
)

// ChatMessage represents a single message in the conversation.
type ChatMessage struct {
	Role      string `json:"role"` // user, assistant
	Content   string `json:"content"`
	Timestamp string `json:"timestamp"`
}

// ChatSession stores conversation history for one user session.
type ChatSession struct {
	ID        string        `json:"id"`
	UserID    int           `json:"user_id"`
	Messages  []ChatMessage `json:"messages"`
	CreatedAt time.Time     `json:"created_at"`
	UpdatedAt time.Time     `json:"updated_at"`
}

// AgentHandler manages strategy advisor chat sessions.
type AgentHandler struct {
	mu       sync.RWMutex
	sessions map[string]*ChatSession // session_id → session
}

// NewAgentHandler creates a new AgentHandler.
func NewAgentHandler() *AgentHandler {
	return &AgentHandler{
		sessions: make(map[string]*ChatSession),
	}
}

// Chat POST /api/v1/agent/chat
func (h *AgentHandler) Chat(c *gin.Context) {
	userID, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "authentication required"})
		return
	}

	var req struct {
		Message   string `json:"message" binding:"required"`
		SessionID string `json:"session_id"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	uid, _ := userID.(int)

	h.mu.Lock()
	session, ok := h.sessions[req.SessionID]
	if !ok || session == nil {
		id := generateSessionID()
		session = &ChatSession{
			ID:        id,
			UserID:    uid,
			Messages:  make([]ChatMessage, 0),
			CreatedAt: time.Now(),
		}
		h.sessions[id] = session
	}
	h.mu.Unlock()

	// Add user message
	session.Messages = append(session.Messages, ChatMessage{
		Role:      "user",
		Content:   req.Message,
		Timestamp: time.Now().Format(time.RFC3339),
	})

	// Generate AI response
	aiReply := generateAIReply(req.Message, session.Messages)
	stage := detectStage(aiReply)

	session.Messages = append(session.Messages, ChatMessage{
		Role:      "assistant",
		Content:   aiReply,
		Timestamp: time.Now().Format(time.RFC3339),
	})
	session.UpdatedAt = time.Now()

	c.JSON(http.StatusOK, gin.H{
		"session_id": session.ID,
		"reply":      aiReply,
		"stage":      stage,
	})
}

// ListSessions GET /api/v1/agent/sessions
func (h *AgentHandler) ListSessions(c *gin.Context) {
	userID, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "authentication required"})
		return
	}
	uid, _ := userID.(int)

	h.mu.RLock()
	defer h.mu.RUnlock()

	type SessionSummary struct {
		ID           string `json:"id"`
		MessageCount int    `json:"message_count"`
		LastMessage  string `json:"last_message"`
		UpdatedAt    string `json:"updated_at"`
	}

	sessions := make([]SessionSummary, 0)
	for _, s := range h.sessions {
		if s.UserID != uid {
			continue
		}
		lastMsg := ""
		if len(s.Messages) > 0 {
			lastMsg = s.Messages[len(s.Messages)-1].Content
			if len(lastMsg) > 100 {
				lastMsg = lastMsg[:100] + "..."
			}
		}
		sessions = append(sessions, SessionSummary{
			ID:           s.ID,
			MessageCount: len(s.Messages),
			LastMessage:  lastMsg,
			UpdatedAt:    s.UpdatedAt.Format(time.RFC3339),
		})
	}

	if sessions == nil {
		sessions = make([]SessionSummary, 0)
	}

	c.JSON(http.StatusOK, gin.H{"sessions": sessions})
}

// GetSession GET /api/v1/agent/sessions/:id
func (h *AgentHandler) GetSession(c *gin.Context) {
	sessionID := c.Param("id")

	h.mu.RLock()
	session, ok := h.sessions[sessionID]
	h.mu.RUnlock()

	if !ok {
		c.JSON(http.StatusNotFound, gin.H{"error": "session not found"})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"id":       session.ID,
		"messages": session.Messages,
	})
}

// DeleteSession DELETE /api/v1/agent/sessions/:id
func (h *AgentHandler) DeleteSession(c *gin.Context) {
	sessionID := c.Param("id")

	h.mu.Lock()
	delete(h.sessions, sessionID)
	h.mu.Unlock()

	c.JSON(http.StatusOK, gin.H{"deleted": true})
}

func generateSessionID() string {
	b := make([]byte, 8)
	rand.Read(b)
	return hex.EncodeToString(b)
}

// generateAIReply produces a context-aware AI response based on user message and conversation history.
func generateAIReply(msg string, history []ChatMessage) string {
	lower := strings.ToLower(msg)

	// --- Confirmation keywords → generate strategy summary ---
	if lower == "yes" || lower == "ok" || strings.Contains(lower, "好") || strings.Contains(lower, "可以") || strings.Contains(lower, "确认") {
		return buildStrategySummary(history)
	}

	// --- Adjustment keywords ---
	if strings.Contains(lower, "adjust") || strings.Contains(lower, "调整") {
		return "好的，你想调整哪些参数？止损比例、持仓数量、交易频率还是策略风格？"
	}

	// --- Specific style keywords (checked before generic "策略") ---
	if strings.Contains(lower, "trend") || strings.Contains(lower, "趋势") {
		return "趋势跟踪策略已选择。请告诉我你的止损比例？"
	}
	if strings.Contains(lower, "mean") || strings.Contains(lower, "均值") {
		return "均值回归策略已选择。请告诉我你的止损比例？"
	}
	if strings.Contains(lower, "momentum") || strings.Contains(lower, "动量") {
		return "动量策略已选择。请告诉我你的止损比例？"
	}

	// --- Stop loss percentage (before generic "止损" keyword) ---
	if strings.Contains(lower, "3%") || strings.Contains(lower, "5%") || strings.Contains(lower, "10%") {
		return "止损比例已确认。接下来请告诉我最大持仓数量？"
	}

	// --- Stop loss ---
	if strings.Contains(lower, "止损") || strings.Contains(lower, "stop") {
		return "好的，我会调整止损参数。请告诉我新的止损比例是多少？比如3%、5%、还是10%？"
	}

	// --- Position count number (specific) ---
	if strings.Contains(lower, "只") {
		return "持仓数量已确认。接下来请选择交易频率：每日(daily)、每小时(hourly)、还是每周(weekly)？"
	}

	// --- Position count (generic) ---
	if strings.Contains(lower, "持仓") || strings.Contains(lower, "position") {
		return "明白了，你想设置持仓数量。请告诉我最多同时持有几只股票？比如3只、5只、还是10只？"
	}

	// --- Frequency ---
	if strings.Contains(lower, "频率") || strings.Contains(lower, "frequency") {
		return "好的，请选择交易频率：每日(daily)、每小时(hourly)、还是每周(weekly)？"
	}

	// --- Generic style / strategy question ---
	if strings.Contains(lower, "style") || strings.Contains(lower, "风格") || strings.Contains(lower, "策略") {
		return "请选择策略风格：趋势跟踪(trend)、均值回归(mean_reversion)、还是动量策略(momentum)？"
	}

	// --- Position count number ---
	if strings.Contains(lower, "只") {
		return "持仓数量已确认。接下来请选择交易频率：每日(daily)、每小时(hourly)、还是每周(weekly)？"
	}

	// --- Frequency selection ---
	if strings.Contains(lower, "daily") || strings.Contains(lower, "每日") {
		return "交易频率已设置为每日。请回复'确认'来生成完整的策略摘要。"
	}
	if strings.Contains(lower, "hourly") || strings.Contains(lower, "每小时") {
		return "交易频率已设置为每小时。请回复'确认'来生成完整的策略摘要。"
	}
	if strings.Contains(lower, "weekly") || strings.Contains(lower, "每周") {
		return "交易频率已设置为每周。请回复'确认'来生成完整的策略摘要。"
	}

	// --- Default fallback ---
	return "我理解你想创建一个策略。请告诉我更多细节：你想做什么风格的策略？趋势跟踪、均值回归、还是动量策略？"
}

// buildStrategySummary generates a strategy summary from conversation history.
func buildStrategySummary(history []ChatMessage) string {
	var style, stopLoss, positions, frequency string

	for _, m := range history {
		lower := strings.ToLower(m.Content)

		if strings.Contains(lower, "trend") || strings.Contains(lower, "趋势") {
			style = "趋势跟踪"
		}
		if strings.Contains(lower, "mean") || strings.Contains(lower, "均值") {
			style = "均值回归"
		}
		if strings.Contains(lower, "momentum") || strings.Contains(lower, "动量") {
			style = "动量策略"
		}

		if strings.Contains(lower, "3%") {
			stopLoss = "3%"
		}
		if strings.Contains(lower, "5%") {
			stopLoss = "5%"
		}
		if strings.Contains(lower, "10%") {
			stopLoss = "10%"
		}

		if strings.Contains(lower, "3只") {
			positions = "3只"
		}
		if strings.Contains(lower, "5只") {
			positions = "5只"
		}
		if strings.Contains(lower, "10只") {
			positions = "10只"
		}

		if strings.Contains(lower, "daily") || strings.Contains(lower, "每日") {
			frequency = "每日"
		}
		if strings.Contains(lower, "hourly") || strings.Contains(lower, "每小时") {
			frequency = "每小时"
		}
		if strings.Contains(lower, "weekly") || strings.Contains(lower, "每周") {
			frequency = "每周"
		}
	}

	styleStr := style
	if styleStr == "" {
		styleStr = "未指定"
	}
	slStr := stopLoss
	if slStr == "" {
		slStr = "未指定"
	}
	posStr := positions
	if posStr == "" {
		posStr = "未指定"
	}
	freqStr := frequency
	if freqStr == "" {
		freqStr = "未指定"
	}

	return "策略摘要：\n- 策略风格： " + styleStr + "\n- 止损比例： " + slStr + "\n- 持仓数量： " + posStr + "\n- 交易频率： " + freqStr + "\n\n以上是你的策略配置。如需调整，请回复'调整'。"
}

// detectStage infers the current conversation stage from the AI reply.
func detectStage(reply string) string {
	lower := strings.ToLower(reply)

	if strings.Contains(lower, "策略摘要") {
		return "summary"
	}
	if strings.Contains(lower, "止损") || strings.Contains(lower, "stop") {
		return "stop_loss"
	}
	if strings.Contains(lower, "持仓") || strings.Contains(lower, "position") {
		return "positions"
	}
	if strings.Contains(lower, "频率") || strings.Contains(lower, "frequency") {
		return "frequency"
	}
	if strings.Contains(lower, "调整") || strings.Contains(lower, "adjust") {
		return "adjust"
	}
	if strings.Contains(lower, "风格") || strings.Contains(lower, "策略") || strings.Contains(lower, "trend") || strings.Contains(lower, "mean") || strings.Contains(lower, "momentum") || strings.Contains(lower, "趋势") || strings.Contains(lower, "均值") || strings.Contains(lower, "动量") {
		return "style"
	}

	return "greeting"
}
