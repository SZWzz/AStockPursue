package handler

import (
	"net/http"

	"github.com/astockpursue/go-core/internal/engine"
	"github.com/astockpursue/go-core/internal/market"
	"github.com/astockpursue/go-core/internal/papertrade"
	"github.com/gin-gonic/gin"
)

// PaperTradingHandler manages paper trading run endpoints.
type PaperTradingHandler struct {
	engine *papertrade.Engine
}

// NewPaperTradingHandler creates a new PaperTradingHandler.
func NewPaperTradingHandler(ds *market.DataStore, factory *engine.EngineFactory) *PaperTradingHandler {
	return &PaperTradingHandler{
		engine: papertrade.NewEngine(ds, factory),
	}
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
