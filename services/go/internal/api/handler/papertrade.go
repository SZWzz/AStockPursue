package handler

import (
	"net/http"
	"sync"
	"time"

	"github.com/astockpursue/go-core/internal/engine"
	"github.com/astockpursue/go-core/internal/market"
	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
)

// PaperTradingRun represents an active or completed paper trading session.
type PaperTradingRun struct {
	ID          string                  `json:"id"`
	Name        string                  `json:"name"`
	Symbols     []string                `json:"symbols"`
	Frequency   string                  `json:"frequency"`
	InitialCash float64                 `json:"initial_cash"`
	Status      string                  `json:"status"` // "running", "stopped", "error"
	CreatedAt   time.Time               `json:"created_at"`
	Runner      *engine.LiveTradingRunner `json:"-"`
}

// PaperTradingHandler manages paper trading runs.
type PaperTradingHandler struct {
	mu   sync.RWMutex
	runs map[string]*PaperTradingRun
	ds   *market.DataStore
	factory *engine.EngineFactory
}

func NewPaperTradingHandler(ds *market.DataStore, factory *engine.EngineFactory) *PaperTradingHandler {
	return &PaperTradingHandler{
		runs:    make(map[string]*PaperTradingRun),
		ds:      ds,
		factory: factory,
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
	if req.Frequency == "" {
		req.Frequency = "1d"
	}
	if req.InitialCash <= 0 {
		req.InitialCash = 100000
	}

	// Build pipeline for this run
	pipeline := &engine.Pipeline{
		Engine:    h.factory.ForSymbol(req.Symbols[0]),
		Portfolio: &engine.Portfolio{
			Cash:      req.InitialCash,
			Equity:    req.InitialCash,
			Positions: make(map[string]*engine.Position),
		},
		Signal:   engine.NewSignalAdapter("localhost:8902", 10*time.Second),
		Risk:     engine.NewRiskManager(engine.RiskConfig{}),
		LastBars: make(map[string]interface{}),
	}

	runner := engine.NewLiveTradingRunner(pipeline, 1*time.Minute)
	runner.WithFetcher(&dsFetcher{ds: h.ds}, req.Symbols, req.Frequency)

	run := &PaperTradingRun{
		ID:          uuid.New().String(),
		Name:        req.Name,
		Symbols:     req.Symbols,
		Frequency:   req.Frequency,
		InitialCash: req.InitialCash,
		Status:      "stopped",
		CreatedAt:   time.Now(),
		Runner:      runner,
	}

	h.mu.Lock()
	h.runs[run.ID] = run
	h.mu.Unlock()

	c.JSON(http.StatusCreated, run)
}

// ListRuns returns all paper trading runs.
// GET /api/v1/paper-trading
func (h *PaperTradingHandler) ListRuns(c *gin.Context) {
	h.mu.RLock()
	defer h.mu.RUnlock()

	runs := make([]*PaperTradingRun, 0, len(h.runs))
	for _, r := range h.runs {
		runs = append(runs, r)
	}
	c.JSON(http.StatusOK, gin.H{"runs": runs, "count": len(runs)})
}

// GetRun returns a single paper trading run by ID.
// GET /api/v1/paper-trading/:id
func (h *PaperTradingHandler) GetRun(c *gin.Context) {
	id := c.Param("id")

	h.mu.RLock()
	run, ok := h.runs[id]
	h.mu.RUnlock()

	if !ok {
		c.JSON(http.StatusNotFound, gin.H{"error": "run not found"})
		return
	}
	c.JSON(http.StatusOK, run)
}

// StartRun starts a paper trading run.
// POST /api/v1/paper-trading/:id/start
func (h *PaperTradingHandler) StartRun(c *gin.Context) {
	id := c.Param("id")

	h.mu.RLock()
	run, ok := h.runs[id]
	h.mu.RUnlock()

	if !ok {
		c.JSON(http.StatusNotFound, gin.H{"error": "run not found"})
		return
	}

	if err := run.Runner.Start(); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	run.Status = "running"
	c.JSON(http.StatusOK, gin.H{"id": id, "status": "running"})
}

// StopRun stops a running paper trading session.
// POST /api/v1/paper-trading/:id/stop
func (h *PaperTradingHandler) StopRun(c *gin.Context) {
	id := c.Param("id")

	h.mu.RLock()
	run, ok := h.runs[id]
	h.mu.RUnlock()

	if !ok {
		c.JSON(http.StatusNotFound, gin.H{"error": "run not found"})
		return
	}

	if err := run.Runner.Stop(); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	run.Status = "stopped"
	c.JSON(http.StatusOK, gin.H{"id": id, "status": "stopped"})
}

// DeleteRun removes a paper trading run.
// DELETE /api/v1/paper-trading/:id
func (h *PaperTradingHandler) DeleteRun(c *gin.Context) {
	id := c.Param("id")

	h.mu.Lock()
	run, ok := h.runs[id]
	if ok {
		run.Runner.Stop()
		delete(h.runs, id)
	}
	h.mu.Unlock()

	if !ok {
		c.JSON(http.StatusNotFound, gin.H{"error": "run not found"})
		return
	}
	c.JSON(http.StatusOK, gin.H{"id": id, "deleted": true})
}

// dsFetcher adapts market.DataStore to engine.BarFetcher interface.
type dsFetcher struct {
	ds *market.DataStore
}

func (f *dsFetcher) GetBars(symbol string, start, end time.Time, freq string) ([]engine.BarData, error) {
	bars, err := f.ds.GetBars(symbol, start, end, freq)
	if err != nil {
		return nil, err
	}
	result := make([]engine.BarData, len(bars))
	for i, b := range bars {
		result[i] = engine.BarData{
			Symbol:    b.Symbol,
			Open:      b.Open,
			High:      b.High,
			Low:       b.Low,
			Close:     b.Close,
			Volume:    b.Volume,
			Timestamp: time.UnixMilli(b.Timestamp),
		}
	}
	return result, nil
}
