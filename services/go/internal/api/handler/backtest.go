package handler

import (
	"fmt"
	"net/http"
	"sync"
	"time"

	"github.com/astockpursue/go-core/internal/engine"
	"github.com/astockpursue/go-core/internal/market"
	"github.com/gin-gonic/gin"
)

type BacktestRequest struct {
	Symbols    []string `json:"symbols" binding:"required"`
	StartDate  string   `json:"start_date" binding:"required"`
	EndDate    string   `json:"end_date" binding:"required"`
	Frequency  string   `json:"frequency" binding:"required"`
	InitialCash float64 `json:"initial_cash" binding:"required"`
}

type BacktestStore struct {
	mu      sync.RWMutex
	results map[string]*engine.BacktestResult
	counter int
}

func NewBacktestStore() *BacktestStore {
	return &BacktestStore{results: make(map[string]*engine.BacktestResult)}
}

type BacktestHandler struct {
	store   *BacktestStore
	ds      *market.DataStore
	factory *engine.EngineFactory
}

func NewBacktestHandler(store *BacktestStore, ds *market.DataStore, factory *engine.EngineFactory) *BacktestHandler {
	return &BacktestHandler{store: store, ds: ds, factory: factory}
}

func (h *BacktestHandler) Run(c *gin.Context) {
	var req BacktestRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	start, err := time.Parse("2006-01-02", req.StartDate)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid start_date, use YYYY-MM-DD"})
		return
	}
	end, err := time.Parse("2006-01-02", req.EndDate)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid end_date, use YYYY-MM-DD"})
		return
	}

	p := &engine.Pipeline{
		Engine:   h.factory.ForSymbol(req.Symbols[0]),
		Portfolio: &engine.Portfolio{
			Cash:      req.InitialCash,
			Equity:    req.InitialCash,
			Positions: make(map[string]*engine.Position),
		},
		Signal:   engine.NewNoopSignalAdapter(),
		Risk:     engine.NewRiskManager(engine.RiskConfig{}),
		LastBars: make(map[string]interface{}),
	}

	runner := engine.NewBacktestRunner(p, h.ds)
	result, err := runner.Run(req.Symbols, start, end, req.Frequency)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	id := h.store.save(result)
	c.JSON(http.StatusOK, gin.H{"id": id, "result": result})
}

func (h *BacktestHandler) GetResult(c *gin.Context) {
	id := c.Param("id")
	result, ok := h.store.get(id)
	if !ok {
		c.JSON(http.StatusNotFound, gin.H{"error": "backtest result not found"})
		return
	}
	c.JSON(http.StatusOK, gin.H{"id": id, "result": result})
}

func (h *BacktestHandler) ListResults(c *gin.Context) {
	ids := h.store.list()
	c.JSON(http.StatusOK, gin.H{"ids": ids})
}

func (s *BacktestStore) save(result *engine.BacktestResult) string {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.counter++
	id := formatInt(s.counter)
	s.results[id] = result
	return id
}

func (s *BacktestStore) get(id string) (*engine.BacktestResult, bool) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	r, ok := s.results[id]
	return r, ok
}

func (s *BacktestStore) list() []string {
	s.mu.RLock()
	defer s.mu.RUnlock()
	ids := make([]string, 0, len(s.results))
	for id := range s.results {
		ids = append(ids, id)
	}
	return ids
}

func formatInt(n int) string {
	return fmt.Sprintf("%d", n)
}
