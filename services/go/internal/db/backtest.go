package db

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/astockpursue/go-core/internal/engine"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// BacktestConfig holds the original request parameters saved alongside results.
type BacktestConfig struct {
	Symbols     []string `json:"symbols"`
	StartDate   string   `json:"start_date"`
	EndDate     string   `json:"end_date"`
	Frequency   string   `json:"frequency"`
	InitialCash float64  `json:"initial_cash"`
}

// BacktestRow represents a row in the backtest_results table.
type BacktestRow struct {
	ID        int             `json:"id"`
	UserID    int             `json:"user_id"`
	Name      string          `json:"name"`
	Symbols   []string        `json:"symbols"`
	Config    json.RawMessage `json:"config"`
	Result    json.RawMessage `json:"result"`
	CreatedAt time.Time       `json:"created_at"`
}

// PostgresBacktestStore persists backtest results via pgx pool.
type PostgresBacktestStore struct {
	pool *pgxpool.Pool
}

// NewPostgresBacktestStore creates a store backed by a TimescaleDB pool.
func NewPostgresBacktestStore(timescale *TimescaleDB) *PostgresBacktestStore {
	if timescale == nil {
		return &PostgresBacktestStore{}
	}
	return &PostgresBacktestStore{pool: timescale.pool}
}

// NewPGBacktestStore creates a PostgresBacktestStore directly from a pgxpool.Pool.
func NewPGBacktestStore(pool *pgxpool.Pool) *PostgresBacktestStore {
	if pool == nil {
		return &PostgresBacktestStore{}
	}
	return &PostgresBacktestStore{pool: pool}
}

// Save persists a backtest result and returns the id as a string.
func (s *PostgresBacktestStore) Save(ctx context.Context, result *engine.BacktestResult) (string, error) {
	return s.SaveWithConfig(ctx, result, "", nil)
}

// SaveWithConfig persists a backtest result with optional name and config metadata.
func (s *PostgresBacktestStore) SaveWithConfig(ctx context.Context, result *engine.BacktestResult, name string, cfg *BacktestConfig) (string, error) {
	if s.pool == nil {
		return "", fmt.Errorf("database not available")
	}

	configJSON := json.RawMessage("{}")
	if cfg != nil {
		if raw, err := json.Marshal(cfg); err == nil {
			configJSON = raw
		}
	}

	resultJSON, err := json.Marshal(result)
	if err != nil {
		return "", fmt.Errorf("marshal backtest result: %w", err)
	}

	var id int
	err = s.pool.QueryRow(ctx,
		`INSERT INTO backtest_results (user_id, name, symbols, config, result)
		 VALUES ($1, $2, $3, $4, $5)
		 RETURNING id`,
		1, name, result.Symbols, configJSON, resultJSON,
	).Scan(&id)
	if err != nil {
		return "", fmt.Errorf("insert backtest result: %w", err)
	}
	return fmt.Sprintf("%d", id), nil
}

// Get retrieves a backtest result by id.
func (s *PostgresBacktestStore) Get(ctx context.Context, id string) (*engine.BacktestResult, error) {
	if s.pool == nil {
		return nil, fmt.Errorf("database not available")
	}

	var resultJSON []byte
	err := s.pool.QueryRow(ctx,
		`SELECT result FROM backtest_results WHERE id = $1`, id,
	).Scan(&resultJSON)
	if err != nil {
		if err == pgx.ErrNoRows {
			return nil, fmt.Errorf("backtest result not found: %s", id)
		}
		return nil, fmt.Errorf("query backtest result: %w", err)
	}

	var result engine.BacktestResult
	if err := json.Unmarshal(resultJSON, &result); err != nil {
		return nil, fmt.Errorf("unmarshal backtest result: %w", err)
	}
	return &result, nil
}

// List returns all backtest result IDs, newest first.
func (s *PostgresBacktestStore) List(ctx context.Context) ([]string, error) {
	if s.pool == nil {
		return nil, fmt.Errorf("database not available")
	}

	rows, err := s.pool.Query(ctx,
		`SELECT id FROM backtest_results ORDER BY created_at DESC`,
	)
	if err != nil {
		return nil, fmt.Errorf("list backtest results: %w", err)
	}
	defer rows.Close()

	var ids []string
	for rows.Next() {
		var id int
		if err := rows.Scan(&id); err != nil {
			return nil, fmt.Errorf("scan id: %w", err)
		}
		ids = append(ids, fmt.Sprintf("%d", id))
	}
	return ids, nil
}

// ListRows returns complete rows for all backtest results.
func (s *PostgresBacktestStore) ListRows(ctx context.Context) ([]BacktestRow, error) {
	if s.pool == nil {
		return nil, fmt.Errorf("database not available")
	}

	rows, err := s.pool.Query(ctx,
		`SELECT id, user_id, name, symbols, config, result, created_at
		 FROM backtest_results ORDER BY created_at DESC`,
	)
	if err != nil {
		return nil, fmt.Errorf("list backtest rows: %w", err)
	}
	defer rows.Close()

	var results []BacktestRow
	for rows.Next() {
		var r BacktestRow
		if err := rows.Scan(&r.ID, &r.UserID, &r.Name, &r.Symbols, &r.Config, &r.Result, &r.CreatedAt); err != nil {
			return nil, fmt.Errorf("scan backtest row: %w", err)
		}
		results = append(results, r)
	}
	return results, nil
}
