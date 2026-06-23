package handler

import (
	"context"
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/astockpursue/go-core/internal/engine"
)

// ArenaHandler provides arena endpoints for strategy competition evaluation.
type ArenaHandler struct {
	db     *pgxpool.Pool
	engine *engine.ArenaEngine
}

// NewArenaHandler creates a new ArenaHandler.
func NewArenaHandler(db *pgxpool.Pool, eng *engine.ArenaEngine) *ArenaHandler {
	return &ArenaHandler{db: db, engine: eng}
}

// Submit POST /api/v1/arena/submit
func (h *ArenaHandler) Submit(c *gin.Context) {
	userID, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "authentication required"})
		return
	}

	var req struct {
		StrategyName string                 `json:"strategy_name" binding:"required"`
		StrategyCode string                 `json:"strategy_code" binding:"required"`
		Parameters   map[string]any `json:"parameters"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if h.db == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "database unavailable"})
		return
	}

	// Rate limit: 3 submissions per week per user
	var weeklyCount int
	err := h.db.QueryRow(context.Background(),
		`SELECT COUNT(*) FROM arena_submissions
		 WHERE user_id = $1 AND submitted_at >= date_trunc('week', NOW())`,
		userID,
	).Scan(&weeklyCount)
	if err == nil && weeklyCount >= 3 {
		c.JSON(http.StatusTooManyRequests, gin.H{
			"error":            "weekly submission limit reached (3/week)",
			"submissions_used": weeklyCount,
		})
		return
	}

	var submissionID string
	err = h.db.QueryRow(context.Background(),
		`INSERT INTO arena_submissions (user_id, strategy_name, strategy_code, parameters)
		 VALUES ($1, $2, $3, $4) RETURNING id`,
		userID, req.StrategyName, req.StrategyCode, req.Parameters,
	).Scan(&submissionID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to create submission"})
		return
	}

	c.JSON(http.StatusCreated, gin.H{
		"submission_id": submissionID,
		"status":        "pending",
	})
}

// ListSubmissions GET /api/v1/arena/submissions
func (h *ArenaHandler) ListSubmissions(c *gin.Context) {
	userID, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "authentication required"})
		return
	}

	if h.db == nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to query submissions"})
		return
	}

	rows, err := h.db.Query(context.Background(),
		`SELECT id, strategy_name, status, submitted_at, completed_at, error_message
		 FROM arena_submissions WHERE user_id = $1
		 ORDER BY submitted_at DESC LIMIT 20`,
		userID,
	)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to query submissions"})
		return
	}
	defer rows.Close()

	type SubmissionRow struct {
		ID           string  `json:"id"`
		StrategyName string  `json:"strategy_name"`
		Status       string  `json:"status"`
		SubmittedAt  string  `json:"submitted_at"`
		CompletedAt  *string `json:"completed_at"`
		ErrorMessage *string `json:"error_message"`
	}

	subs := make([]SubmissionRow, 0)
	for rows.Next() {
		var s SubmissionRow
		rows.Scan(&s.ID, &s.StrategyName, &s.Status, &s.SubmittedAt, &s.CompletedAt, &s.ErrorMessage)
		subs = append(subs, s)
	}

	c.JSON(http.StatusOK, gin.H{"submissions": subs})
}

// Rankings GET /api/v1/arena/rankings
func (h *ArenaHandler) Rankings(c *gin.Context) {
	if h.db == nil {
		c.JSON(http.StatusOK, gin.H{"rankings": []interface{}{}})
		return
	}

	week := c.DefaultQuery("week", "")

	query := `SELECT r.rank, s.strategy_name, r.sharpe_ratio, r.annual_return,
	          r.max_drawdown, r.win_rate, r.alpha, r.beta, r.total_trades,
	          s.user_id, r.submission_id
	          FROM arena_rankings r
	          JOIN arena_submissions s ON s.id = r.submission_id
	          WHERE ($1 = '' OR r.week = $1)
	          ORDER BY r.rank ASC LIMIT 20`

	rows, err := h.db.Query(context.Background(), query, week)
	if err != nil {
		c.JSON(http.StatusOK, gin.H{"rankings": []interface{}{}})
		return
	}
	defer rows.Close()

	type RankingRow struct {
		Rank         int     `json:"rank"`
		StrategyName string  `json:"strategy_name"`
		SharpeRatio  float64 `json:"sharpe_ratio"`
		AnnualReturn float64 `json:"annual_return"`
		MaxDrawdown  float64 `json:"max_drawdown"`
		WinRate      float64 `json:"win_rate"`
		Alpha        float64 `json:"alpha"`
		Beta         float64 `json:"beta"`
		TotalTrades  int     `json:"total_trades"`
		UserID       int     `json:"user_id"`
		SubmissionID string  `json:"submission_id"`
	}

	rankings := make([]RankingRow, 0)
	for rows.Next() {
		var r RankingRow
		rows.Scan(&r.Rank, &r.StrategyName, &r.SharpeRatio, &r.AnnualReturn,
			&r.MaxDrawdown, &r.WinRate, &r.Alpha, &r.Beta, &r.TotalTrades,
			&r.UserID, &r.SubmissionID)
		rankings = append(rankings, r)
	}

	c.JSON(http.StatusOK, gin.H{"rankings": rankings})
}
