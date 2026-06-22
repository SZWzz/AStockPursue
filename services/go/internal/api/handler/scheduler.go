package handler

import (
	"context"
	"encoding/json"
	"net/http"
	"strconv"
	"sync"
	"time"

	"github.com/astockpursue/go-core/internal/engine"
	"github.com/astockpursue/go-core/internal/log"
	"github.com/astockpursue/go-core/internal/market"
	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5/pgxpool"
)

// ScheduledJob represents a recurring backtest job (metadata from PostgreSQL).
type ScheduledJob struct {
	ID           int       `json:"id"`
	Name         string    `json:"name"`
	Symbols      []string  `json:"symbols"`
	StartDate    string    `json:"start_date"`
	EndDate      string    `json:"end_date"`
	Frequency    string    `json:"frequency"`
	InitialCash  float64   `json:"initial_cash"`
	CronExpr     string    `json:"cron_expr"`
	JobType      string    `json:"job_type"`
	Status       string    `json:"status"`
	LastRun      *time.Time `json:"last_run,omitempty"`
	NextRun      *time.Time `json:"next_run,omitempty"`
	CreatedAt    time.Time  `json:"created_at"`
}

// jobRuntime holds running state for a scheduled job.
type jobRuntime struct {
	runner  *engine.BacktestRunner
	store   BacktestRepository
	ds      *market.DataStore
	stopCh  chan struct{}
	job     *ScheduledJob
}

// SchedulerHandler manages recurring backtest jobs.
type SchedulerHandler struct {
	mu      sync.RWMutex
	db      *pgxpool.Pool
	running map[int]*jobRuntime // runtime state for running jobs
	ds      *market.DataStore
	factory *engine.EngineFactory
	repo    BacktestRepository
	logger  *log.Logger
}

func NewSchedulerHandler(ds *market.DataStore, factory *engine.EngineFactory, repo BacktestRepository, db *pgxpool.Pool) *SchedulerHandler {
	return &SchedulerHandler{
		db:      db,
		running: make(map[int]*jobRuntime),
		ds:      ds,
		factory: factory,
		repo:    repo,
		logger:  log.New(),
	}
}

type schedulerConfig struct {
	Symbols     []string `json:"symbols"`
	StartDate   string   `json:"start_date"`
	EndDate     string   `json:"end_date"`
	Frequency   string   `json:"frequency"`
	InitialCash float64  `json:"initial_cash"`
}

// CreateJob creates a new scheduled backtest and persists to PostgreSQL.
// POST /api/v1/scheduler
func (h *SchedulerHandler) CreateJob(c *gin.Context) {
	var req struct {
		Name        string   `json:"name" binding:"required"`
		Symbols     []string `json:"symbols" binding:"required"`
		StartDate   string   `json:"start_date" binding:"required"`
		EndDate     string   `json:"end_date" binding:"required"`
		Frequency   string   `json:"frequency"`
		InitialCash float64  `json:"initial_cash"`
		CronExpr    string   `json:"cron_expr"`
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

	if h.db == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "database not available"})
		return
	}

	cfg := schedulerConfig{
		Symbols:     req.Symbols,
		StartDate:   req.StartDate,
		EndDate:     req.EndDate,
		Frequency:   req.Frequency,
		InitialCash: req.InitialCash,
	}
	cfgJSON, err := json.Marshal(cfg)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	var id int
	err = h.db.QueryRow(c.Request.Context(),
		`INSERT INTO scheduled_jobs (name, job_type, cron_expr, config, status)
		 VALUES ($1, $2, $3, $4, $5) RETURNING id`,
		req.Name, "backtest", req.CronExpr, cfgJSON, "paused",
	).Scan(&id)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	job := &ScheduledJob{
		ID:          id,
		Name:        req.Name,
		Symbols:     req.Symbols,
		StartDate:   req.StartDate,
		EndDate:     req.EndDate,
		Frequency:   req.Frequency,
		InitialCash: req.InitialCash,
		CronExpr:    req.CronExpr,
		JobType:     "backtest",
		Status:      "paused",
		CreatedAt:   time.Now(),
	}

	// Run once immediately
	go h.runOnce(job)

	c.JSON(http.StatusCreated, job)
}

// ListJobs returns all scheduled jobs from PostgreSQL.
// GET /api/v1/scheduler
func (h *SchedulerHandler) ListJobs(c *gin.Context) {
	if h.db == nil {
		c.JSON(http.StatusOK, gin.H{"jobs": []ScheduledJob{}, "count": 0})
		return
	}

	rows, err := h.db.Query(c.Request.Context(),
		`SELECT id, name, job_type, cron_expr, config, status, last_run, next_run, created_at
		 FROM scheduled_jobs ORDER BY created_at DESC`)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	defer rows.Close()

	jobs := make([]ScheduledJob, 0)
	for rows.Next() {
		var j ScheduledJob
		var cfgJSON []byte
		if err := rows.Scan(&j.ID, &j.Name, &j.JobType, &j.CronExpr, &cfgJSON, &j.Status, &j.LastRun, &j.NextRun, &j.CreatedAt); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}
		var cfg schedulerConfig
		if err := json.Unmarshal(cfgJSON, &cfg); err == nil {
			j.Symbols = cfg.Symbols
			j.StartDate = cfg.StartDate
			j.EndDate = cfg.EndDate
			j.Frequency = cfg.Frequency
			j.InitialCash = cfg.InitialCash
		}
		jobs = append(jobs, j)
	}

	c.JSON(http.StatusOK, gin.H{"jobs": jobs, "count": len(jobs)})
}

// GetJob returns a single job by ID from PostgreSQL.
// GET /api/v1/scheduler/:id
func (h *SchedulerHandler) GetJob(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid job id"})
		return
	}

	if h.db == nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "job not found"})
		return
	}

	var j ScheduledJob
	var cfgJSON []byte
	err = h.db.QueryRow(c.Request.Context(),
		`SELECT id, name, job_type, cron_expr, config, status, last_run, next_run, created_at
		 FROM scheduled_jobs WHERE id = $1`, id,
	).Scan(&j.ID, &j.Name, &j.JobType, &j.CronExpr, &cfgJSON, &j.Status, &j.LastRun, &j.NextRun, &j.CreatedAt)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "job not found"})
		return
	}

	var cfg schedulerConfig
	if err := json.Unmarshal(cfgJSON, &cfg); err == nil {
		j.Symbols = cfg.Symbols
		j.StartDate = cfg.StartDate
		j.EndDate = cfg.EndDate
		j.Frequency = cfg.Frequency
		j.InitialCash = cfg.InitialCash
	}

	c.JSON(http.StatusOK, j)
}

// StartJob starts a paused job.
// POST /api/v1/scheduler/:id/start
func (h *SchedulerHandler) StartJob(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid job id"})
		return
	}

	if h.db == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "database not available"})
		return
	}

	// Load job config from PG
	var j ScheduledJob
	var cfgJSON []byte
	err = h.db.QueryRow(c.Request.Context(),
		`SELECT id, name, job_type, cron_expr, config, status, last_run, next_run, created_at
		 FROM scheduled_jobs WHERE id = $1`, id,
	).Scan(&j.ID, &j.Name, &j.JobType, &j.CronExpr, &cfgJSON, &j.Status, &j.LastRun, &j.NextRun, &j.CreatedAt)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "job not found"})
		return
	}

	var cfg schedulerConfig
	if err := json.Unmarshal(cfgJSON, &cfg); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "invalid job config"})
		return
	}
	j.Symbols = cfg.Symbols
	j.StartDate = cfg.StartDate
	j.EndDate = cfg.EndDate
	j.Frequency = cfg.Frequency
	j.InitialCash = cfg.InitialCash

	// Create runtime
	pipeline := &engine.Pipeline{
		Engine:    h.factory.ForSymbol(cfg.Symbols[0]),
		Portfolio: &engine.Portfolio{
			Cash:      cfg.InitialCash,
			Equity:    cfg.InitialCash,
			Positions: make(map[string]*engine.Position),
		},
		Signal:   engine.NewNoopSignalAdapter(),
		Risk:     engine.NewRiskManager(engine.RiskConfig{}),
		LastBars: make(map[string]*engine.Bar),
	}
	runner := engine.NewBacktestRunner(pipeline, h.ds)

	rt := &jobRuntime{
		runner: runner,
		store:  h.repo,
		ds:     h.ds,
		stopCh: make(chan struct{}),
		job:    &j,
	}

	h.mu.Lock()
	h.running[id] = rt
	h.mu.Unlock()

	// Update status in PG
	if _, err := h.db.Exec(c.Request.Context(),
		`UPDATE scheduled_jobs SET status = $1 WHERE id = $2`, "running", id); err != nil {
		h.logger.Error("scheduler: update status to running: %v", err)
	}

	go h.runLoop(rt)

	c.JSON(http.StatusOK, gin.H{"id": id, "status": "running"})
}

// PauseJob pauses a running job.
// POST /api/v1/scheduler/:id/pause
func (h *SchedulerHandler) PauseJob(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid job id"})
		return
	}

	h.mu.Lock()
	rt, ok := h.running[id]
	if ok && rt.stopCh != nil {
		close(rt.stopCh)
	}
	delete(h.running, id)
	h.mu.Unlock()

	if h.db != nil {
		if _, err := h.db.Exec(c.Request.Context(),
			`UPDATE scheduled_jobs SET status = $1 WHERE id = $2`, "paused", id); err != nil {
			h.logger.Error("scheduler: update status to paused: %v", err)
		}
	}

	if !ok {
		c.JSON(http.StatusNotFound, gin.H{"error": "job not found"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"id": id, "status": "paused"})
}

// DeleteJob removes a scheduled job.
// DELETE /api/v1/scheduler/:id
func (h *SchedulerHandler) DeleteJob(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid job id"})
		return
	}

	h.mu.Lock()
	rt, ok := h.running[id]
	if ok && rt.stopCh != nil {
		close(rt.stopCh)
	}
	delete(h.running, id)
	h.mu.Unlock()

	if h.db != nil {
		tag, err := h.db.Exec(c.Request.Context(),
			`DELETE FROM scheduled_jobs WHERE id = $1`, id)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}
		if tag.RowsAffected() == 0 && !ok {
			c.JSON(http.StatusNotFound, gin.H{"error": "job not found"})
			return
		}
	} else if !ok {
		c.JSON(http.StatusNotFound, gin.H{"error": "job not found"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"id": id, "deleted": true})
}

// runOnce executes a job once immediately.
func (h *SchedulerHandler) runOnce(job *ScheduledJob) {
	start, err := time.Parse("2006-01-02", job.StartDate)
	if err != nil {
		h.logger.Error("scheduler: invalid start date %q: %v", job.StartDate, err)
		return
	}
	end, err := time.Parse("2006-01-02", job.EndDate)
	if err != nil {
		h.logger.Error("scheduler: invalid end date %q: %v", job.EndDate, err)
		return
	}

	pipeline := &engine.Pipeline{
		Engine:    h.factory.ForSymbol(job.Symbols[0]),
		Portfolio: &engine.Portfolio{
			Cash:      job.InitialCash,
			Equity:    job.InitialCash,
			Positions: make(map[string]*engine.Position),
		},
		Signal:   engine.NewNoopSignalAdapter(),
		Risk:     engine.NewRiskManager(engine.RiskConfig{}),
		LastBars: make(map[string]*engine.Bar),
	}
	runner := engine.NewBacktestRunner(pipeline, h.ds)

	result, err := runner.Run(job.Symbols, start, end, job.Frequency)
	if err != nil {
		return
	}

	now := time.Now()
	if h.db != nil {
		if _, err := h.db.Exec(context.Background(),
			`UPDATE scheduled_jobs SET last_run = $1 WHERE id = $2`, now, job.ID); err != nil {
			h.logger.Error("scheduler: update last_run: %v", err)
		}
	}
	if h.repo != nil {
		if _, err := h.repo.Save(context.Background(), result); err != nil {
			h.logger.Error("scheduler: save result error: %v", err)
		}
	}
}

func (h *SchedulerHandler) runLoop(rt *jobRuntime) {
	intervals := map[string]time.Duration{
		"hourly":  time.Hour,
		"daily":   24 * time.Hour,
		"weekly":  7 * 24 * time.Hour,
		"monthly": 30 * 24 * time.Hour,
	}
	interval, ok := intervals[rt.job.CronExpr]
	if !ok {
		interval = 24 * time.Hour
	}

	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for {
		select {
		case <-rt.stopCh:
			return
		case <-ticker.C:
			h.executeRun(rt)
		}
	}
}

func (h *SchedulerHandler) executeRun(rt *jobRuntime) {
	job := rt.job
	start, err := time.Parse("2006-01-02", job.StartDate)
	if err != nil {
		h.logger.Error("scheduler: invalid start date %q: %v", job.StartDate, err)
		return
	}
	end, err := time.Parse("2006-01-02", job.EndDate)
	if err != nil {
		h.logger.Error("scheduler: invalid end date %q: %v", job.EndDate, err)
		return
	}
	result, err := rt.runner.Run(job.Symbols, start, end, job.Frequency)
	if err != nil {
		return
	}
	now := time.Now()
	job.LastRun = &now

	if h.db != nil {
		if _, err := h.db.Exec(context.Background(),
			`UPDATE scheduled_jobs SET last_run = $1 WHERE id = $2`, now, job.ID); err != nil {
			h.logger.Error("scheduler: update last_run: %v", err)
		}
	}
	if rt.store != nil {
		if _, err := rt.store.Save(context.Background(), result); err != nil {
			h.logger.Error("scheduler: save result error: %v", err)
		}
	}
}
