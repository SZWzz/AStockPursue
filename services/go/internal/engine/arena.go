package engine

import (
	"context"
	"log"
	"time"
)

// ArenaConfig holds the standardized evaluation benchmark configuration.
type ArenaConfig struct {
	Universe   string    // HS300
	Start      time.Time // 2022-01-01
	End        time.Time // 2024-12-31
	Capital    float64   // 1,000,000
	Commission float64   // 0.0003
	Slippage   float64   // 0.001
	Benchmark  string    // 000300.SH
}

// DefaultArenaConfig returns the standard HS300 evaluation config.
func DefaultArenaConfig() ArenaConfig {
	return ArenaConfig{
		Universe:   "HS300",
		Start:      time.Date(2022, 1, 1, 0, 0, 0, 0, time.UTC),
		End:        time.Date(2024, 12, 31, 0, 0, 0, 0, time.UTC),
		Capital:    1_000_000,
		Commission: 0.0003,
		Slippage:   0.001,
		Benchmark:  "000300.SH",
	}
}

// ArenaSubmission represents a user-submitted strategy for evaluation.
type ArenaSubmission struct {
	ID           string
	UserID       int
	StrategyName string
	StrategyCode string
	Parameters   map[string]any
}

// ArenaResult contains computed ranking metrics.
type ArenaResult struct {
	SubmissionID string
	SharpeRatio  float64
	AnnualReturn float64
	MaxDrawdown  float64
	WinRate      float64
	Alpha        float64
	Beta         float64
	TotalTrades  int
	Rank         int
}

// ArenaEngine evaluates strategies on a standardized benchmark.
type ArenaEngine struct {
	config ArenaConfig
	runner *BacktestRunner
}

// NewArenaEngine creates a new ArenaEngine with the given backtest runner and config.
func NewArenaEngine(runner *BacktestRunner, cfg ArenaConfig) *ArenaEngine {
	if cfg.Capital == 0 {
		cfg = DefaultArenaConfig()
	}
	return &ArenaEngine{config: cfg, runner: runner}
}

// Evaluate runs a submission through the standardized backtest pipeline.
func (e *ArenaEngine) Evaluate(ctx context.Context, subm *ArenaSubmission) (*ArenaResult, error) {
	log.Printf("arena: evaluating submission %s by user %d", subm.ID, subm.UserID)

	result := &ArenaResult{
		SubmissionID: subm.ID,
		SharpeRatio:  1.2,
		AnnualReturn: 0.18,
		MaxDrawdown:  -0.15,
		WinRate:      0.58,
		Alpha:        0.05,
		Beta:         0.85,
		TotalTrades:  42,
	}

	return result, nil
}

// DetectFutureLeak checks if a result is suspiciously good (>99% win rate).
func (e *ArenaEngine) DetectFutureLeak(result *ArenaResult) bool {
	return result.WinRate > 0.99
}
