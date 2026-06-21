package db

import (
	"context"
	"fmt"

	"github.com/astockpursue/go-core/internal/engine"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type PostgresBacktestStore struct {
	pool *pgxpool.Pool
}

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

func (s *PostgresBacktestStore) Save(ctx context.Context, result *engine.BacktestResult) (string, error) {
	if s.pool == nil {
		return "", fmt.Errorf("database not available")
	}
	id := uuid.New().String()

	_, err := s.pool.Exec(ctx, s.buildInsertRunSQL(),
		id, result.Symbols, result.Frequency,
		result.StartTime, result.EndTime,
		result.InitialCash, result.FinalEquity,
		result.TotalReturn, result.SharpeRatio,
		result.MaxDrawdown, result.MaxDrawdownPct,
		result.WinRate, result.TotalTrades,
		result.WinningTrades, result.LosingTrades,
	)
	if err != nil {
		return "", fmt.Errorf("insert backtest run: %w", err)
	}

	if len(result.EquityCurve) > 0 {
		if err := s.insertEquityPoints(ctx, id, result.EquityCurve); err != nil {
			return "", err
		}
	}

	if len(result.Trades) > 0 {
		if err := s.insertTrades(ctx, id, result.Trades); err != nil {
			return "", err
		}
	}

	return id, nil
}

func (s *PostgresBacktestStore) insertEquityPoints(ctx context.Context, runID string, points []engine.EquityPoint) error {
	batch := &pgx.Batch{}
	for _, ep := range points {
		batch.Queue(s.buildInsertEquitySQL(), runID, ep.Timestamp, ep.Equity, ep.Cash, ep.PositionCount)
	}
	br := s.pool.SendBatch(ctx, batch)
	defer br.Close()
	_, err := br.Exec()
	if err != nil {
		return fmt.Errorf("insert equity curves: %w", err)
	}
	return nil
}

func (s *PostgresBacktestStore) insertTrades(ctx context.Context, runID string, trades []engine.TradeRecord) error {
	batch := &pgx.Batch{}
	for _, t := range trades {
		tradeID := uuid.New().String()
		batch.Queue(s.buildInsertTradesSQL(),
			tradeID, runID, t.Symbol, string(t.Side),
			t.Quantity, t.Price, t.Commission, t.PnL, t.Timestamp,
		)
	}
	br := s.pool.SendBatch(ctx, batch)
	defer br.Close()
	_, err := br.Exec()
	if err != nil {
		return fmt.Errorf("insert trades: %w", err)
	}
	return nil
}

func (s *PostgresBacktestStore) Get(ctx context.Context, id string) (*engine.BacktestResult, error) {
	if s.pool == nil {
		return nil, fmt.Errorf("database not available")
	}
	result := &engine.BacktestResult{}

	row := s.pool.QueryRow(ctx, s.buildGetRunSQL(), id)
	err := row.Scan(
		&result.Symbols, &result.Frequency,
		&result.StartTime, &result.EndTime,
		&result.InitialCash, &result.FinalEquity,
		&result.TotalReturn, &result.SharpeRatio,
		&result.MaxDrawdown, &result.MaxDrawdownPct,
		&result.WinRate, &result.TotalTrades,
		&result.WinningTrades, &result.LosingTrades,
	)
	if err != nil {
		if err == pgx.ErrNoRows {
			return nil, fmt.Errorf("backtest result not found: %s", id)
		}
		return nil, fmt.Errorf("query backtest run: %w", err)
	}

	rows, err := s.pool.Query(ctx, s.buildGetEquitySQL(), id)
	if err != nil {
		return nil, fmt.Errorf("query equity curve: %w", err)
	}
	defer rows.Close()
	for rows.Next() {
		var ep engine.EquityPoint
		if err := rows.Scan(&ep.Timestamp, &ep.Equity, &ep.Cash, &ep.PositionCount); err != nil {
			return nil, fmt.Errorf("scan equity point: %w", err)
		}
		result.EquityCurve = append(result.EquityCurve, ep)
	}

	tRows, err := s.pool.Query(ctx, s.buildGetTradesSQL(), id)
	if err != nil {
		return nil, fmt.Errorf("query trades: %w", err)
	}
	defer tRows.Close()
	for tRows.Next() {
		var t engine.TradeRecord
		if err := tRows.Scan(&t.Symbol, &t.Side, &t.Quantity, &t.Price, &t.Commission, &t.PnL, &t.Timestamp); err != nil {
			return nil, fmt.Errorf("scan trade: %w", err)
		}
		result.Trades = append(result.Trades, t)
	}

	return result, nil
}

func (s *PostgresBacktestStore) List(ctx context.Context) ([]string, error) {
	if s.pool == nil {
		return nil, fmt.Errorf("database not available")
	}
	rows, err := s.pool.Query(ctx, s.buildListRunsSQL())
	if err != nil {
		return nil, fmt.Errorf("list backtest runs: %w", err)
	}
	defer rows.Close()
	var ids []string
	for rows.Next() {
		var id string
		if err := rows.Scan(&id); err != nil {
			return nil, fmt.Errorf("scan id: %w", err)
		}
		ids = append(ids, id)
	}
	return ids, nil
}

func (s *PostgresBacktestStore) buildInsertRunSQL() string {
	return `INSERT INTO backtest_runs (
		id, symbols, frequency, start_date, end_date,
		initial_cash, final_equity,
		total_return, sharpe_ratio,
		max_drawdown, max_drawdown_pct,
		win_rate, total_trades, winning_trades, losing_trades
	) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)`
}

func (s *PostgresBacktestStore) buildInsertEquitySQL() string {
	return `INSERT INTO equity_curves (run_id, timestamp, equity, cash, position_count) VALUES ($1,$2,$3,$4,$5)`
}

func (s *PostgresBacktestStore) buildInsertTradesSQL() string {
	return `INSERT INTO trades (id, run_id, symbol, side, quantity, price, commission, pnl, timestamp) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)`
}

func (s *PostgresBacktestStore) buildGetRunSQL() string {
	return `SELECT symbols, frequency, start_date, end_date, initial_cash, final_equity, total_return, sharpe_ratio, max_drawdown, max_drawdown_pct, win_rate, total_trades, winning_trades, losing_trades FROM backtest_runs WHERE id = $1`
}

func (s *PostgresBacktestStore) buildGetEquitySQL() string {
	return `SELECT timestamp, equity, cash, position_count FROM equity_curves WHERE run_id = $1 ORDER BY timestamp ASC`
}

func (s *PostgresBacktestStore) buildGetTradesSQL() string {
	return `SELECT symbol, side, quantity, price, commission, pnl, timestamp FROM trades WHERE run_id = $1 ORDER BY timestamp ASC`
}

func (s *PostgresBacktestStore) buildListRunsSQL() string {
	return `SELECT id FROM backtest_runs ORDER BY created_at DESC`
}
