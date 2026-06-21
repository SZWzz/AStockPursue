package papertrade

import (
	"fmt"
	"sync"
	"time"

	"github.com/astockpursue/go-core/internal/engine"
	"github.com/astockpursue/go-core/internal/market"
	"github.com/google/uuid"
)

// Run represents a paper trading session.
type Run struct {
	ID          string                    `json:"id"`
	Name        string                    `json:"name"`
	Symbols     []string                  `json:"symbols"`
	Frequency   string                    `json:"frequency"`
	InitialCash float64                   `json:"initial_cash"`
	Status      RunStatus                 `json:"status"`
	CreatedAt   time.Time                 `json:"created_at"`
	Runner      *engine.LiveTradingRunner `json:"-"`
}

// Engine manages paper trading runs.
type Engine struct {
	mu      sync.RWMutex
	runs    map[string]*Run
	ds      *market.DataStore
	factory *engine.EngineFactory
	repo    Repository
}

// NewEngine creates a new paper trading engine.
func NewEngine(ds *market.DataStore, factory *engine.EngineFactory) *Engine {
	return &Engine{
		runs:    make(map[string]*Run),
		ds:      ds,
		factory: factory,
		repo:    NewMemoryRepository(),
	}
}

// WithRepository sets a persistent repository (PostgreSQL).
func (e *Engine) WithRepository(repo Repository) *Engine {
	e.repo = repo
	return e
}

// Create creates a new paper trading run (status: created).
func (e *Engine) Create(name string, symbols []string, freq string, initialCash float64) (*Run, error) {
	if freq == "" {
		freq = "1d"
	}
	if initialCash <= 0 {
		initialCash = 100000
	}

	pipeline := &engine.Pipeline{
		Engine:    e.factory.ForSymbol(symbols[0]),
		Portfolio: &engine.Portfolio{Cash: initialCash, Equity: initialCash, Positions: make(map[string]*engine.Position)},
		Signal:    engine.NewSignalAdapter("localhost:8902", 10*time.Second),
		Risk:      engine.NewRiskManager(engine.RiskConfig{}),
		LastBars:  make(map[string]interface{}),
	}

	runner := engine.NewLiveTradingRunner(pipeline, 1*time.Minute)
	runner.WithFetcher(&dsFetcher{ds: e.ds}, symbols, freq)

	run := &Run{
		ID:          uuid.New().String(),
		Name:        name,
		Symbols:     symbols,
		Frequency:   freq,
		InitialCash: initialCash,
		Status:      StatusCreated,
		CreatedAt:   time.Now(),
		Runner:      runner,
	}

	e.mu.Lock()
	e.runs[run.ID] = run
	e.mu.Unlock()

	if e.repo != nil {
		_ = e.repo.Save(run)
	}

	return run, nil
}

// Start transitions a run from created→running.
func (e *Engine) Start(id string) error {
	e.mu.Lock()
	defer e.mu.Unlock()

	run, ok := e.runs[id]
	if !ok {
		return fmt.Errorf("papertrade: run %s not found", id)
	}
	if err := run.transition(StatusRunning); err != nil {
		return err
	}
	return run.Runner.Start()
}

// Stop transitions a run to stopped and shuts down the runner.
func (e *Engine) Stop(id string) error {
	e.mu.Lock()
	defer e.mu.Unlock()

	run, ok := e.runs[id]
	if !ok {
		return fmt.Errorf("papertrade: run %s not found", id)
	}
	if err := run.Runner.Stop(); err != nil {
		return err
	}
	return run.transition(StatusStopped)
}

// Delete removes a run (stopping it first if running).
func (e *Engine) Delete(id string) error {
	e.mu.Lock()
	defer e.mu.Unlock()

	run, ok := e.runs[id]
	if !ok {
		return fmt.Errorf("papertrade: run %s not found", id)
	}
	if run.Status == StatusRunning {
		_ = run.Runner.Stop()
	}
	delete(e.runs, id)
	if e.repo != nil {
		_ = e.repo.Delete(id)
	}
	return nil
}

// List returns all runs.
func (e *Engine) List() []*Run {
	e.mu.RLock()
	defer e.mu.RUnlock()
	runs := make([]*Run, 0, len(e.runs))
	for _, r := range e.runs {
		runs = append(runs, r)
	}
	return runs
}

// Get returns a single run by ID.
func (e *Engine) Get(id string) *Run {
	e.mu.RLock()
	defer e.mu.RUnlock()
	return e.runs[id]
}

// dsFetcher adapts market.DataStore to engine.BarFetcher.
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
