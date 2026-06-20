package handler

import (
	"context"
	"fmt"
	"net/http"
	"sync"
	"time"

	"github.com/astockpursue/go-core/internal/engine"
	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
)

type BacktestRepository interface {
	Save(ctx context.Context, result *engine.BacktestResult) (string, error)
	Get(ctx context.Context, id string) (*engine.BacktestResult, error)
	List(ctx context.Context) ([]string, error)
}

type BacktestRequest struct {
	Symbols     []string `json:"symbols" binding:"required"`
	StartDate   string   `json:"start_date" binding:"required"`
	EndDate     string   `json:"end_date" binding:"required"`
	Frequency   string   `json:"frequency" binding:"required"`
	InitialCash float64  `json:"initial_cash" binding:"required"`
}

type MemoryBacktestStore struct {
	mu      sync.RWMutex
	results map[string]*engine.BacktestResult
}

func NewBacktestStore() *MemoryBacktestStore {
	return &MemoryBacktestStore{results: make(map[string]*engine.BacktestResult)}
}

func (s *MemoryBacktestStore) Save(ctx context.Context, result *engine.BacktestResult) (string, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	id := uuid.New().String()
	s.results[id] = result
	return id, nil
}

func (s *MemoryBacktestStore) Get(ctx context.Context, id string) (*engine.BacktestResult, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	r, ok := s.results[id]
	if !ok {
		return nil, fmt.Errorf("backtest result not found: %s", id)
	}
	return r, nil
}

func (s *MemoryBacktestStore) List(ctx context.Context) ([]string, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	ids := make([]string, 0, len(s.results))
	for id := range s.results {
		ids = append(ids, id)
	}
	return ids, nil
}

type BacktestHandler struct {
	repo    BacktestRepository
	loader  engine.BarLoader
	factory *engine.EngineFactory
}

func NewBacktestHandler(repo BacktestRepository, loader engine.BarLoader, factory *engine.EngineFactory) *BacktestHandler {
	return &BacktestHandler{repo: repo, loader: loader, factory: factory}
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
		Engine:    h.factory.ForSymbol(req.Symbols[0]),
		Portfolio: &engine.Portfolio{
			Cash:      req.InitialCash,
			Equity:    req.InitialCash,
			Positions: make(map[string]*engine.Position),
		},
		Signal:   engine.NewNoopSignalAdapter(),
		Risk:     engine.NewRiskManager(engine.RiskConfig{}),
		LastBars: make(map[string]interface{}),
	}

	runner := engine.NewBacktestRunner(p, h.loader)
	result, err := runner.Run(req.Symbols, start, end, req.Frequency)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	id, err := h.repo.Save(c.Request.Context(), result)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"id": id, "result": result})
}

func (h *BacktestHandler) GetResult(c *gin.Context) {
	id := c.Param("id")
	result, err := h.repo.Get(c.Request.Context(), id)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"id": id, "result": result})
}

func (h *BacktestHandler) ListResults(c *gin.Context) {
	ids, err := h.repo.List(c.Request.Context())
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"ids": ids})
}
