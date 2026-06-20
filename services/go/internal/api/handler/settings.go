package handler

import (
	"net/http"
	"sync"

	"github.com/gin-gonic/gin"
)

// UserSettings holds per-user configuration.
type UserSettings struct {
	Theme           string            `json:"theme"`
	Language        string            `json:"language"`
	DefaultSymbols  []string          `json:"default_symbols"`
	DefaultFreq     string            `json:"default_frequency"`
	DataSources     map[string]string `json:"data_sources"`     // source name → API key
	LLMProvider     string            `json:"llm_provider"`
	LLMModel        string            `json:"llm_model"`
	LLMAPIKey       string            `json:"llm_api_key,omitempty"`
	Notifications   bool              `json:"notifications"`
	RiskLimits      RiskLimits        `json:"risk_limits"`
}

type RiskLimits struct {
	MaxPositionPct  float64 `json:"max_position_pct"`
	StopLossPct     float64 `json:"stop_loss_pct"`
	TakeProfitPct   float64 `json:"take_profit_pct"`
	DailyLossLimit  float64 `json:"daily_loss_limit"`
}

// SettingsHandler manages user configuration.
type SettingsHandler struct {
	mu       sync.RWMutex
	settings map[string]*UserSettings // username → settings
	defaults *UserSettings
}

func NewSettingsHandler() *SettingsHandler {
	return &SettingsHandler{
		settings: make(map[string]*UserSettings),
		defaults: &UserSettings{
			Theme:          "dark",
			Language:       "zh",
			DefaultFreq:    "1d",
			LLMProvider:    "openai",
			LLMModel:       "gpt-4",
			DataSources:    make(map[string]string),
			RiskLimits: RiskLimits{
				MaxPositionPct: 0.2,
				StopLossPct:    5.0,
				TakeProfitPct:  10.0,
				DailyLossLimit: 10000,
			},
		},
	}
}

// Get returns settings for the authenticated user.
// GET /api/v1/settings
func (h *SettingsHandler) Get(c *gin.Context) {
	username := h.getUsername(c)

	h.mu.RLock()
	s, ok := h.settings[username]
	h.mu.RUnlock()

	if !ok {
		// Return defaults clone
		clone := *h.defaults
		clone.DataSources = make(map[string]string)
		c.JSON(http.StatusOK, clone)
		return
	}
	c.JSON(http.StatusOK, s)
}

// Update replaces settings for the authenticated user.
// PUT /api/v1/settings
func (h *SettingsHandler) Update(c *gin.Context) {
	username := h.getUsername(c)

	var req UserSettings
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	if req.DataSources == nil {
		req.DataSources = make(map[string]string)
	}

	h.mu.Lock()
	h.settings[username] = &req
	h.mu.Unlock()

	c.JSON(http.StatusOK, gin.H{"username": username, "saved": true})
}

// Reset restores default settings.
// DELETE /api/v1/settings
func (h *SettingsHandler) Reset(c *gin.Context) {
	username := h.getUsername(c)

	h.mu.Lock()
	delete(h.settings, username)
	h.mu.Unlock()

	c.JSON(http.StatusOK, gin.H{"username": username, "reset": true})
}

func (h *SettingsHandler) getUsername(c *gin.Context) string {
	if u, ok := c.Get("username"); ok {
		return u.(string)
	}
	return "default"
}
