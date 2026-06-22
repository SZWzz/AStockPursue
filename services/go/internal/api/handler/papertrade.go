package handler

import (
	"net/http"

	"github.com/astockpursue/go-core/internal/engine"
	"github.com/astockpursue/go-core/internal/market"
	"github.com/astockpursue/go-core/internal/papertrade"
	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5/pgxpool"
)

// PaperTradingHandler manages paper trading run endpoints.
type PaperTradingHandler struct {
	engine        *papertrade.Engine
	backtestRepo  BacktestRepository
	paperEngine   *papertrade.Engine
}

// NewPaperTradingHandler creates a new PaperTradingHandler.
func NewPaperTradingHandler(ds *market.DataStore, factory *engine.EngineFactory, db *pgxpool.Pool) *PaperTradingHandler {
	paperEngine := papertrade.NewEngine(ds, factory, db)
	return &PaperTradingHandler{
		engine:      paperEngine,
		paperEngine: paperEngine,
	}
}

// SetBacktestRepo sets the backtest repository for promotion support.
func (h *PaperTradingHandler) SetBacktestRepo(repo BacktestRepository) {
	h.backtestRepo = repo
}

// Engine returns the underlying papertrade engine (used for promotion wiring).
func (h *PaperTradingHandler) Engine() *papertrade.Engine {
	return h.engine
}

// CreateRun creates a new paper trading configuration.
// POST /api/v1/paper-trading
func (h *PaperTradingHandler) CreateRun(c *gin.Context) {
	var req struct {
		Name        string   `json:"name" binding:"required"`
		Symbols     []string `json:"symbols" binding:"required"`
		Frequency   string   `json:"frequency"`
		InitialCash float64  `json:"initial_cash"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	run, err := h.engine.Create(req.Name, req.Symbols, req.Frequency, req.InitialCash)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusCreated, run)
}

// ListRuns returns all paper trading runs.
// GET /api/v1/paper-trading
func (h *PaperTradingHandler) ListRuns(c *gin.Context) {
	runs := h.engine.List()
	c.JSON(http.StatusOK, gin.H{"runs": runs, "count": len(runs)})
}

// GetRun returns a single paper trading run by ID.
// GET /api/v1/paper-trading/:id
func (h *PaperTradingHandler) GetRun(c *gin.Context) {
	run := h.engine.Get(c.Param("id"))
	if run == nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "run not found"})
		return
	}
	c.JSON(http.StatusOK, run)
}

// StartRun starts a paper trading run.
// POST /api/v1/paper-trading/:id/start
func (h *PaperTradingHandler) StartRun(c *gin.Context) {
	if err := h.engine.Start(c.Param("id")); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"id": c.Param("id"), "status": "running"})
}

// StopRun stops a running paper trading session.
// POST /api/v1/paper-trading/:id/stop
func (h *PaperTradingHandler) StopRun(c *gin.Context) {
	if err := h.engine.Stop(c.Param("id")); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"id": c.Param("id"), "status": "stopped"})
}

// DeleteRun removes a paper trading run.
// DELETE /api/v1/paper-trading/:id
func (h *PaperTradingHandler) DeleteRun(c *gin.Context) {
	if err := h.engine.Delete(c.Param("id")); err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"id": c.Param("id"), "deleted": true})
}

// PromoteToPaper creates a paper trading run from a backtest result.
// POST /api/v1/backtest/:id/promote-to-paper
func (h *PaperTradingHandler) PromoteToPaper(c *gin.Context) {
	id := c.Param("id")
	if h.backtestRepo == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "backtest repository not configured"})
		return
	}

	result, err := h.backtestRepo.Get(c.Request.Context(), id)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "backtest result not found: " + id})
		return
	}

	run, err := h.engine.Create(
		"Promoted from backtest "+id,
		result.Symbols,
		result.Frequency,
		result.InitialCash,
	)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusCreated, gin.H{
		"paper_run": run,
		"source":    "backtest",
		"source_id": id,
	})
}
