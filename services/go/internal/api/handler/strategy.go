package handler

import (
	"encoding/json"
	"net/http"
	"time"

	"github.com/astockpursue/go-core/internal/market"
	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5/pgxpool"
)

// Strategy represents a trading strategy configuration.
type Strategy struct {
	ID        int              `json:"id"`
	UserID    int              `json:"user_id"`
	Name      string           `json:"name"`
	Code      string           `json:"code"`
	Params    json.RawMessage  `json:"params"`
	Symbols   []string         `json:"symbols"`
	CreatedAt time.Time        `json:"created_at"`
	UpdatedAt time.Time        `json:"updated_at"`
}

// StrategyHandler provides CRUD endpoints for trading strategies.
type StrategyHandler struct {
	db *pgxpool.Pool
}

// NewStrategyHandler creates a new StrategyHandler.
func NewStrategyHandler(db *pgxpool.Pool) *StrategyHandler {
	return &StrategyHandler{db: db}
}

// Create creates a new strategy.
// POST /api/v1/strategy
func (h *StrategyHandler) Create(c *gin.Context) {
	var req struct {
		Name    string          `json:"name" binding:"required"`
		Code    string          `json:"code" binding:"required"`
		Params  json.RawMessage `json:"params"`
		Symbols []string        `json:"symbols" binding:"required"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	if len(req.Symbols) == 0 {
		c.JSON(http.StatusBadRequest, gin.H{"error": "at least one symbol required"})
		return
	}

	// Normalize symbols
	for i, sym := range req.Symbols {
		req.Symbols[i] = market.NormalizeSymbol(sym)
	}

	params := json.RawMessage("{}")
	if len(req.Params) > 0 {
		params = req.Params
	}

	var s Strategy
	err := h.db.QueryRow(c.Request.Context(),
		`INSERT INTO strategies (user_id, name, code, params, symbols)
		 VALUES ($1, $2, $3, $4, $5)
		 RETURNING id, user_id, name, code, params, symbols, created_at, updated_at`,
		1, req.Name, req.Code, params, req.Symbols,
	).Scan(&s.ID, &s.UserID, &s.Name, &s.Code, &s.Params, &s.Symbols, &s.CreatedAt, &s.UpdatedAt)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusCreated, s)
}

// List returns all strategies for the current user.
// GET /api/v1/strategy
func (h *StrategyHandler) List(c *gin.Context) {
	rows, err := h.db.Query(c.Request.Context(),
		`SELECT id, user_id, name, code, params, symbols, created_at, updated_at
		 FROM strategies WHERE user_id = $1 ORDER BY updated_at DESC`, 1,
	)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	defer rows.Close()

	strategies := make([]Strategy, 0)
	for rows.Next() {
		var s Strategy
		if err := rows.Scan(&s.ID, &s.UserID, &s.Name, &s.Code, &s.Params, &s.Symbols, &s.CreatedAt, &s.UpdatedAt); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}
		strategies = append(strategies, s)
	}

	c.JSON(http.StatusOK, gin.H{"strategies": strategies, "count": len(strategies)})
}

// Get returns a single strategy by ID.
// GET /api/v1/strategy/:id
func (h *StrategyHandler) Get(c *gin.Context) {
	var s Strategy
	err := h.db.QueryRow(c.Request.Context(),
		`SELECT id, user_id, name, code, params, symbols, created_at, updated_at
		 FROM strategies WHERE id = $1 AND user_id = $2`,
		c.Param("id"), 1,
	).Scan(&s.ID, &s.UserID, &s.Name, &s.Code, &s.Params, &s.Symbols, &s.CreatedAt, &s.UpdatedAt)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "strategy not found"})
		return
	}

	c.JSON(http.StatusOK, s)
}

// Update modifies an existing strategy.
// PUT /api/v1/strategy/:id
func (h *StrategyHandler) Update(c *gin.Context) {
	var req struct {
		Name    string          `json:"name"`
		Code    string          `json:"code"`
		Params  json.RawMessage `json:"params"`
		Symbols []string        `json:"symbols"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// Normalize symbols if provided
	if len(req.Symbols) > 0 {
		for i, sym := range req.Symbols {
			req.Symbols[i] = market.NormalizeSymbol(sym)
		}
	}

	var s Strategy
	err := h.db.QueryRow(c.Request.Context(),
		`UPDATE strategies
		 SET name = COALESCE(NULLIF($1, ''), name),
		     code = COALESCE(NULLIF($2, ''), code),
		     params = COALESCE(NULLIF($3::text, '')::jsonb, params),
		     symbols = COALESCE($4, symbols),
		     updated_at = NOW()
		 WHERE id = $5 AND user_id = $6
		 RETURNING id, user_id, name, code, params, symbols, created_at, updated_at`,
		req.Name, req.Code, string(req.Params), req.Symbols, c.Param("id"), 1,
	).Scan(&s.ID, &s.UserID, &s.Name, &s.Code, &s.Params, &s.Symbols, &s.CreatedAt, &s.UpdatedAt)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "strategy not found"})
		return
	}

	c.JSON(http.StatusOK, s)
}

// Delete removes a strategy by ID.
// DELETE /api/v1/strategy/:id
func (h *StrategyHandler) Delete(c *gin.Context) {
	tag, err := h.db.Exec(c.Request.Context(),
		`DELETE FROM strategies WHERE id = $1 AND user_id = $2`,
		c.Param("id"), 1,
	)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if tag.RowsAffected() == 0 {
		c.JSON(http.StatusNotFound, gin.H{"error": "strategy not found"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"deleted": true})
}
