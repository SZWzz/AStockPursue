package handler

import (
	"context"
	"net/http"
	"sync"
	"time"

	"github.com/astockpursue/go-core/internal/engine"
	"github.com/astockpursue/go-core/internal/market"
	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
)

// ScheduledJob represents a recurring backtest job.
type ScheduledJob struct {
	ID          string              `json:"id"`
	Name        string              `json:"name"`
	Symbols     []string            `json:"symbols"`
	StartDate   string              `json:"start_date"`
	EndDate     string              `json:"end_date"`
	Frequency   string              `json:"frequency"`
	InitialCash float64             `json:"initial_cash"`
	CronExpr    string              `json:"cron_expr"` // "daily", "weekly", "monthly", "hourly"
	Status      string              `json:"status"`
	LastRun     *time.Time          `json:"last_run,omitempty"`
	LastResult  *engine.BacktestResult `json:"last_result,omitempty"`
	CreatedAt   time.Time           `json:"created_at"`
	runner      *engine.BacktestRunner
	store       BacktestRepository
	ds          *market.DataStore
	stopCh      chan struct{}
}

// SchedulerHandler manages recurring backtest jobs.
type SchedulerHandler struct {
	mu      sync.RWMutex
	jobs    map[string]*ScheduledJob
	ds      *market.DataStore
	factory *engine.EngineFactory
	repo    BacktestRepository
}

func NewSchedulerHandler(ds *market.DataStore, factory *engine.EngineFactory, repo BacktestRepository) *SchedulerHandler {
	return &SchedulerHandler{
		jobs:    make(map[string]*ScheduledJob),
		ds:      ds,
		factory: factory,
		repo:    repo,
	}
}

// CreateJob creates a new scheduled backtest.
// POST /api/v1/scheduler
func (h *SchedulerHandler) CreateJob(c *gin.Context) {
	var req struct {
		Name        string   `json:"name" binding:"required"`
		Symbols     []string `json:"symbols" binding:"required"`
		StartDate   string   `json:"start_date" binding:"required"`
		EndDate     string   `json:"end_date" binding:"required"`
		Frequency   string   `json:"frequency"`
		InitialCash float64  `json:"initial_cash"`
		CronExpr    string   `json:"cron_expr"` // "daily", "weekly", "monthly", "hourly"
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
	if req.CronExpr == "" {
		req.CronExpr = "daily"
	}

	pipeline := &engine.Pipeline{
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
	runner := engine.NewBacktestRunner(pipeline, h.ds)

	job := &ScheduledJob{
		ID:          uuid.New().String(),
		Name:        req.Name,
		Symbols:     req.Symbols,
		StartDate:   req.StartDate,
		EndDate:     req.EndDate,
		Frequency:   req.Frequency,
		InitialCash: req.InitialCash,
		CronExpr:    req.CronExpr,
		Status:      "paused",
		CreatedAt:   time.Now(),
		runner:      runner,
		store:       h.repo,
		ds:          h.ds,
	}

	h.mu.Lock()
	h.jobs[job.ID] = job
	h.mu.Unlock()

	go h.runJob(job)

	c.JSON(http.StatusCreated, job)
}

// ListJobs returns all scheduled jobs.
// GET /api/v1/scheduler
func (h *SchedulerHandler) ListJobs(c *gin.Context) {
	h.mu.RLock()
	defer h.mu.RUnlock()

	jobs := make([]*ScheduledJob, 0, len(h.jobs))
	for _, j := range h.jobs {
		jobs = append(jobs, j)
	}
	c.JSON(http.StatusOK, gin.H{"jobs": jobs, "count": len(jobs)})
}

// GetJob returns a single job by ID.
// GET /api/v1/scheduler/:id
func (h *SchedulerHandler) GetJob(c *gin.Context) {
	id := c.Param("id")
	h.mu.RLock()
	job, ok := h.jobs[id]
	h.mu.RUnlock()
	if !ok {
		c.JSON(http.StatusNotFound, gin.H{"error": "job not found"})
		return
	}
	c.JSON(http.StatusOK, job)
}

// StartJob starts a paused job.
// POST /api/v1/scheduler/:id/start
func (h *SchedulerHandler) StartJob(c *gin.Context) {
	id := c.Param("id")
	h.mu.RLock()
	job, ok := h.jobs[id]
	h.mu.RUnlock()
	if !ok {
		c.JSON(http.StatusNotFound, gin.H{"error": "job not found"})
		return
	}
	job.Status = "running"
	job.stopCh = make(chan struct{})
	go h.runLoop(job)
	c.JSON(http.StatusOK, gin.H{"id": id, "status": "running"})
}

// PauseJob pauses a running job.
// POST /api/v1/scheduler/:id/pause
func (h *SchedulerHandler) PauseJob(c *gin.Context) {
	id := c.Param("id")
	h.mu.RLock()
	job, ok := h.jobs[id]
	h.mu.RUnlock()
	if !ok {
		c.JSON(http.StatusNotFound, gin.H{"error": "job not found"})
		return
	}
	job.Status = "paused"
	if job.stopCh != nil {
		close(job.stopCh)
	}
	c.JSON(http.StatusOK, gin.H{"id": id, "status": "paused"})
}

// DeleteJob removes a scheduled job.
// DELETE /api/v1/scheduler/:id
func (h *SchedulerHandler) DeleteJob(c *gin.Context) {
	id := c.Param("id")
	h.mu.Lock()
	job, ok := h.jobs[id]
	if ok && job.stopCh != nil {
		close(job.stopCh)
	}
	delete(h.jobs, id)
	h.mu.Unlock()
	if !ok {
		c.JSON(http.StatusNotFound, gin.H{"error": "job not found"})
		return
	}
	c.JSON(http.StatusOK, gin.H{"id": id, "deleted": true})
}

func (h *SchedulerHandler) runJob(job *ScheduledJob) {
	// Run once immediately
	h.executeRun(job)
}

func (h *SchedulerHandler) runLoop(job *ScheduledJob) {
	intervals := map[string]time.Duration{
		"hourly":  time.Hour,
		"daily":   24 * time.Hour,
		"weekly":  7 * 24 * time.Hour,
		"monthly": 30 * 24 * time.Hour,
	}
	interval, ok := intervals[job.CronExpr]
	if !ok {
		interval = 24 * time.Hour
	}

	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for {
		select {
		case <-job.stopCh:
			return
		case <-ticker.C:
			h.executeRun(job)
		}
	}
}

func (h *SchedulerHandler) executeRun(job *ScheduledJob) {
	start, _ := time.Parse("2006-01-02", job.StartDate)
	end, _ := time.Parse("2006-01-02", job.EndDate)
	result, err := job.runner.Run(job.Symbols, start, end, job.Frequency)
	if err != nil {
		return
	}
	now := time.Now()
	job.LastRun = &now
	job.LastResult = result

	// Persist if store available
	if job.store != nil {
		_, _ = job.store.Save(context.TODO(), result)
	}
}
