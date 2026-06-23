package handler

import (
	"encoding/json"
	"net/http"
	"os"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5/pgxpool"
)

// StrategyTemplate represents a strategy template from templates.json.
type StrategyTemplate struct {
	Key            string                 `json:"key"`
	Name           string                 `json:"name"`
	NameEn         string                 `json:"name_en"`
	Description    string                 `json:"description"`
	DescriptionEn  string                 `json:"description_en"`
	Category       string                 `json:"category"`
	Difficulty     string                 `json:"difficulty"`
	Markets        []string               `json:"markets"`
	DefaultParams  map[string]any `json:"default_params"`
	Tags           []string               `json:"tags"`
}

// MarketplaceStrategy represents a row from vt_strategy_marketplace.
type MarketplaceStrategy struct {
	ID               string    `json:"id"`
	UserID           int       `json:"user_id"`
	Title            string    `json:"title"`
	Description      string    `json:"description"`
	Code             string    `json:"code"`
	Market           string    `json:"market"`
	AssetClass       string    `json:"asset_class"`
	Category         string    `json:"category"`
	Tags             []string  `json:"tags"`
	BacktestSharpe   *float64  `json:"backtest_sharpe"`
	BacktestReturn   *float64  `json:"backtest_return"`
	BacktestDrawdown *float64  `json:"backtest_drawdown"`
	InstallsCount    int       `json:"installs_count"`
	RatingSum        int       `json:"rating_sum"`
	RatingCount      int       `json:"rating_count"`
	IsPublic         bool      `json:"is_public"`
	CreatedAt        time.Time `json:"created_at"`
	UpdatedAt        time.Time `json:"updated_at"`
}

// MarketplaceHandler provides marketplace endpoints.
type MarketplaceHandler struct {
	db           *pgxpool.Pool
	templatePath string
}

// NewMarketplaceHandler creates a new MarketplaceHandler.
func NewMarketplaceHandler(db *pgxpool.Pool) *MarketplaceHandler {
	return &MarketplaceHandler{
		db:           db,
		templatePath: "../python/src/lab/templates.json",
	}
}

// ListTemplates reads templates.json and returns the list.
// GET /api/v1/marketplace/templates
func (h *MarketplaceHandler) ListTemplates(c *gin.Context) {
	data, err := os.ReadFile(h.templatePath)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to read templates"})
		return
	}

	var templates []StrategyTemplate
	if err := json.Unmarshal(data, &templates); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to parse templates"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"templates": templates, "count": len(templates)})
}

// ListStrategies returns paginated strategies from vt_strategy_marketplace.
// GET /api/v1/marketplace/strategies?page=1&limit=20&sort_by=rating|installs|recent
func (h *MarketplaceHandler) ListStrategies(c *gin.Context) {
	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	limit, _ := strconv.Atoi(c.DefaultQuery("limit", "20"))
	sortBy := c.DefaultQuery("sort_by", "recent")

	if page < 1 {
		page = 1
	}
	if limit < 1 || limit > 100 {
		limit = 20
	}

	offset := (page - 1) * limit

	var orderClause string
	switch sortBy {
	case "rating":
		orderClause = "ORDER BY rating_count DESC, rating_sum DESC"
	case "installs":
		orderClause = "ORDER BY installs_count DESC"
	default:
		orderClause = "ORDER BY created_at DESC"
	}

	if h.db == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "database not available"})
		return
	}

	query := `SELECT id, user_id, title, description, code, market, asset_class, category,
		        tags, backtest_sharpe, backtest_return, backtest_drawdown,
		        installs_count, rating_sum, rating_count, is_public, created_at, updated_at
		 FROM vt_strategy_marketplace
		 WHERE is_public = true ` + orderClause + ` LIMIT $1 OFFSET $2`

	rows, err := h.db.Query(c.Request.Context(), query, limit, offset)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	defer rows.Close()

	strategies := make([]MarketplaceStrategy, 0)
	for rows.Next() {
		var s MarketplaceStrategy
		if err := rows.Scan(&s.ID, &s.UserID, &s.Title, &s.Description, &s.Code,
			&s.Market, &s.AssetClass, &s.Category, &s.Tags,
			&s.BacktestSharpe, &s.BacktestReturn, &s.BacktestDrawdown,
			&s.InstallsCount, &s.RatingSum, &s.RatingCount, &s.IsPublic,
			&s.CreatedAt, &s.UpdatedAt); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}
		strategies = append(strategies, s)
	}

	var total int
	err = h.db.QueryRow(c.Request.Context(),
		`SELECT COUNT(*) FROM vt_strategy_marketplace WHERE is_public = true`,
	).Scan(&total)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"strategies": strategies,
		"page":       page,
		"limit":      limit,
		"total":      total,
	})
}

// GetStrategy returns a single strategy by ID.
// GET /api/v1/marketplace/strategies/:id
func (h *MarketplaceHandler) GetStrategy(c *gin.Context) {
	id := c.Param("id")

	if h.db == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "database not available"})
		return
	}

	var s MarketplaceStrategy
	err := h.db.QueryRow(c.Request.Context(),
		`SELECT id, user_id, title, description, code, market, asset_class, category,
		        tags, backtest_sharpe, backtest_return, backtest_drawdown,
		        installs_count, rating_sum, rating_count, is_public, created_at, updated_at
		 FROM vt_strategy_marketplace WHERE id = $1`, id,
	).Scan(&s.ID, &s.UserID, &s.Title, &s.Description, &s.Code,
		&s.Market, &s.AssetClass, &s.Category, &s.Tags,
		&s.BacktestSharpe, &s.BacktestReturn, &s.BacktestDrawdown,
		&s.InstallsCount, &s.RatingSum, &s.RatingCount, &s.IsPublic,
		&s.CreatedAt, &s.UpdatedAt)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "strategy not found"})
		return
	}

	c.JSON(http.StatusOK, s)
}

// CreateStrategy creates a new marketplace strategy entry.
// POST /api/v1/marketplace/strategies
func (h *MarketplaceHandler) CreateStrategy(c *gin.Context) {
	userID := h.getUserID(c)
	if userID == 0 {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "user not authenticated"})
		return
	}

	var req struct {
		Name           string          `json:"name" binding:"required"`
		TemplateID     string          `json:"template_id" binding:"required"`
		Params         json.RawMessage `json:"params"`
		BacktestResult json.RawMessage `json:"backtest_result"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	description := "Template: " + req.TemplateID
	code := string(req.Params)
	if code == "" || code == "null" {
		code = "{}"
	}

	var sharpe, returnPct, drawdown *float64
	if len(req.BacktestResult) > 0 {
		var br struct {
			Sharpe       *float64 `json:"sharpe"`
			SharpeRatio  *float64 `json:"sharpe_ratio"`
			Return       *float64 `json:"return"`
			TotalReturn  *float64 `json:"total_return"`
			Drawdown     *float64 `json:"drawdown"`
			MaxDrawdown  *float64 `json:"max_drawdown"`
		}
		if err := json.Unmarshal(req.BacktestResult, &br); err == nil {
			sharpe = br.Sharpe
			if sharpe == nil {
				sharpe = br.SharpeRatio
			}
			returnPct = br.Return
			if returnPct == nil {
				returnPct = br.TotalReturn
			}
			drawdown = br.Drawdown
			if drawdown == nil {
				drawdown = br.MaxDrawdown
			}
		}
	}

	if h.db == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "database not available"})
		return
	}

	var s MarketplaceStrategy
	err := h.db.QueryRow(c.Request.Context(),
		`INSERT INTO vt_strategy_marketplace (user_id, title, description, code, backtest_sharpe, backtest_return, backtest_drawdown)
		 VALUES ($1, $2, $3, $4, $5, $6, $7)
		 RETURNING id, user_id, title, description, code, market, asset_class, category,
		           tags, backtest_sharpe, backtest_return, backtest_drawdown,
		           installs_count, rating_sum, rating_count, is_public, created_at, updated_at`,
		userID, req.Name, description, code, sharpe, returnPct, drawdown,
	).Scan(&s.ID, &s.UserID, &s.Title, &s.Description, &s.Code,
		&s.Market, &s.AssetClass, &s.Category, &s.Tags,
		&s.BacktestSharpe, &s.BacktestReturn, &s.BacktestDrawdown,
		&s.InstallsCount, &s.RatingSum, &s.RatingCount, &s.IsPublic,
		&s.CreatedAt, &s.UpdatedAt)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusCreated, s)
}

// RateStrategy rates a strategy (1-5). Upserts the rating.
// POST /api/v1/marketplace/strategies/:id/rate
func (h *MarketplaceHandler) RateStrategy(c *gin.Context) {
	userID := h.getUserID(c)
	if userID == 0 {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "user not authenticated"})
		return
	}

	strategyID := c.Param("id")

	var req struct {
		Rating int `json:"rating" binding:"required,min=1,max=5"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if req.Rating < 1 || req.Rating > 5 {
		c.JSON(http.StatusBadRequest, gin.H{"error": "rating must be between 1 and 5"})
		return
	}

	if h.db == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "database not available"})
		return
	}

	// Upsert the rating
	_, err := h.db.Exec(c.Request.Context(),
		`INSERT INTO vt_strategy_ratings (strategy_id, user_id, rating)
		 VALUES ($1, $2, $3)
		 ON CONFLICT (strategy_id, user_id) DO UPDATE SET rating = $3, created_at = now()`,
		strategyID, userID, req.Rating,
	)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	// Recalculate rating_sum and rating_count for the strategy
	_, err = h.db.Exec(c.Request.Context(),
		`UPDATE vt_strategy_marketplace
		 SET rating_sum = (SELECT COALESCE(SUM(rating), 0) FROM vt_strategy_ratings WHERE strategy_id = $1),
		     rating_count = (SELECT COUNT(*) FROM vt_strategy_ratings WHERE strategy_id = $1),
		     updated_at = now()
		 WHERE id = $1`,
		strategyID,
	)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"status": "rated", "rating": req.Rating})
}

// InstallStrategy increments the install count for a strategy.
// POST /api/v1/marketplace/strategies/:id/install
func (h *MarketplaceHandler) InstallStrategy(c *gin.Context) {
	strategyID := c.Param("id")

	if h.db == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "database not available"})
		return
	}

	tag, err := h.db.Exec(c.Request.Context(),
		`UPDATE vt_strategy_marketplace
		 SET installs_count = installs_count + 1, updated_at = now()
		 WHERE id = $1`,
		strategyID,
	)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if tag.RowsAffected() == 0 {
		c.JSON(http.StatusNotFound, gin.H{"error": "strategy not found"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"status": "installed"})
}

func (h *MarketplaceHandler) getUserID(c *gin.Context) int {
	if uid, exists := c.Get("user_id"); exists {
		return uid.(int)
	}
	return 0
}
