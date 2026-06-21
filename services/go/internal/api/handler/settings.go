package handler

import (
	"encoding/json"
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5/pgxpool"
)

// UserSettings holds per-user configuration.
type UserSettings struct {
	Theme          string            `json:"theme"`
	Language       string            `json:"language"`
	DefaultSymbols []string          `json:"default_symbols"`
	DefaultFreq    string            `json:"default_frequency"`
	DataSources    map[string]string `json:"data_sources"`
	LLMProvider    string            `json:"llm_provider"`
	LLMModel       string            `json:"llm_model"`
	LLMAPIKey      string            `json:"llm_api_key,omitempty"`
	Notifications  bool              `json:"notifications"`
	RiskLimits     RiskLimits        `json:"risk_limits"`
}

type RiskLimits struct {
	MaxPositionPct float64 `json:"max_position_pct"`
	StopLossPct    float64 `json:"stop_loss_pct"`
	TakeProfitPct  float64 `json:"take_profit_pct"`
	DailyLossLimit float64 `json:"daily_loss_limit"`
}

// SettingsHandler manages user configuration persistently via PostgreSQL.
type SettingsHandler struct {
	db       *pgxpool.Pool
	defaults *UserSettings
}

func NewSettingsHandler(db *pgxpool.Pool) *SettingsHandler {
	return &SettingsHandler{
		db: db,
		defaults: &UserSettings{
			Theme:       "dark",
			Language:    "zh",
			DefaultFreq: "1d",
			LLMProvider: "openai",
			LLMModel:    "gpt-4",
			DataSources: make(map[string]string),
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
	userID := h.getUserID(c)

	if h.db == nil {
		c.JSON(http.StatusOK, h.cloneDefaults())
		return
	}

	var settingsJSON []byte
	err := h.db.QueryRow(c.Request.Context(),
		`SELECT settings FROM user_settings WHERE user_id = $1`, userID,
	).Scan(&settingsJSON)
	if err != nil {
		// Return defaults clone
		c.JSON(http.StatusOK, h.cloneDefaults())
		return
	}

	var s UserSettings
	if err := json.Unmarshal(settingsJSON, &s); err != nil {
		c.JSON(http.StatusOK, h.cloneDefaults())
		return
	}
	if s.DataSources == nil {
		s.DataSources = make(map[string]string)
	}
	c.JSON(http.StatusOK, s)
}

// Update replaces settings for the authenticated user.
// PUT /api/v1/settings
func (h *SettingsHandler) Update(c *gin.Context) {
	userID := h.getUserID(c)

	var req UserSettings
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	if req.DataSources == nil {
		req.DataSources = make(map[string]string)
	}

	if h.db == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "database not available"})
		return
	}

	settingsJSON, err := json.Marshal(req)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	_, err = h.db.Exec(c.Request.Context(),
		`INSERT INTO user_settings (user_id, settings, updated_at)
		 VALUES ($1, $2, now())
		 ON CONFLICT (user_id) DO UPDATE SET settings = $2, updated_at = now()`,
		userID, settingsJSON,
	)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"user_id": userID, "saved": true})
}

// Reset restores default settings.
// DELETE /api/v1/settings
func (h *SettingsHandler) Reset(c *gin.Context) {
	userID := h.getUserID(c)

	if h.db != nil {
		if _, err := h.db.Exec(c.Request.Context(),
			`DELETE FROM user_settings WHERE user_id = $1`, userID); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to reset settings"})
			return
		}
	}

	c.JSON(http.StatusOK, gin.H{"user_id": userID, "reset": true})
}

func (h *SettingsHandler) getUserID(c *gin.Context) int {
	if u, ok := c.Get("username"); ok {
		// For now, all users map to user_id 1
		_ = u
	}
	return 1
}

func (h *SettingsHandler) cloneDefaults() *UserSettings {
	clone := *h.defaults
	clone.DataSources = make(map[string]string)
	return &clone
}
