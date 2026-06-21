package ml

import (
	"context"
	"crypto/sha256"
	"database/sql"
	"fmt"
	"log"
	"math"
)

// EvalResult holds the key performance metrics from a model evaluation.
type EvalResult struct {
	ModelID     string  `json:"model_id"`
	Sharpe      float64 `json:"sharpe"`
	MaxDrawdown float64 `json:"max_drawdown"`
	WinRate     float64 `json:"win_rate"`
	TotalReturn float64 `json:"total_return"`
	IC          float64 `json:"ic"`
	IR          float64 `json:"ir"`
}

// Evaluator assesses the performance of registered ML models.
type Evaluator struct {
	db *sql.DB
}

// NewEvaluator creates a new Evaluator backed by the given database.
func NewEvaluator(db *sql.DB) *Evaluator {
	return &Evaluator{db: db}
}

// Evaluate computes simulated performance metrics for the given model.
//
// This is a mock implementation that derives deterministic but reasonable
// metrics from the model's identity. In production, this method will perform
// walk-forward backtesting across the given symbol universe.
func (e *Evaluator) Evaluate(ctx context.Context, modelID string, symbols []string, startDate, endDate string) (*EvalResult, error) {
	// Validate the model exists.
	_, err := e.getModelID(ctx, modelID)
	if err != nil {
		return nil, fmt.Errorf("ml: model not found: %s: %w", modelID, err)
	}

	// Deterministic mock metrics derived from the model ID hash, ensuring the
	// same model always produces the same evaluation result.
	h := sha256.Sum256([]byte(modelID))
	seed := float64(h[0])/255.0 + float64(h[1])/255.0*0.1

	sharpe := 0.5 + seed*2.0    // range ~0.5 to 2.5
	maxDD := 0.05 + seed*0.25   // range ~0.05 to 0.30
	winRate := 0.40 + seed*0.25  // range ~0.40 to 0.65
	totalReturn := 0.05 + seed*0.45 // range ~0.05 to 0.50
	ic := 0.01 + seed*0.10      // range ~0.01 to 0.11
	ir := sharpe / math.Sqrt(252) // annualized IR from Sharpe

	// Save the evaluation metrics back to the model record.
	metrics := map[string]float64{
		"sharpe":       math.Round(sharpe*10000) / 10000,
		"max_drawdown": math.Round(maxDD*10000) / 10000,
		"win_rate":     math.Round(winRate*10000) / 10000,
		"total_return": math.Round(totalReturn*10000) / 10000,
		"ic":           math.Round(ic*10000) / 10000,
		"ir":           math.Round(ir*10000) / 10000,
	}
	if err := e.updateMetrics(ctx, modelID, metrics); err != nil {
		log.Printf("[ml/evaluator] update metrics error: %v", err)
	}

	return &EvalResult{
		ModelID:     modelID,
		Sharpe:      metrics["sharpe"],
		MaxDrawdown: metrics["max_drawdown"],
		WinRate:     metrics["win_rate"],
		TotalReturn: metrics["total_return"],
		IC:          metrics["ic"],
		IR:          metrics["ir"],
	}, nil
}

// getModelID checks that the model exists in the registry.
func (e *Evaluator) getModelID(ctx context.Context, id string) (string, error) {
	var dbID string
	err := e.db.QueryRowContext(ctx,
		`SELECT id FROM ml_models WHERE id = ?`, id,
	).Scan(&dbID)
	return dbID, err
}

// updateMetrics persists evaluation metrics to the model record.
func (e *Evaluator) updateMetrics(ctx context.Context, id string, metrics map[string]float64) error {
	reg := NewModelRegistry(e.db)
	return reg.UpdateMetrics(ctx, id, metrics)
}
