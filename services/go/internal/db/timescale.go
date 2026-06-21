package db

import (
	"context"
	"database/sql"
	"embed"
	"fmt"
	"time"

	"github.com/golang-migrate/migrate/v4"
	_ "github.com/golang-migrate/migrate/v4/database/postgres"
	"github.com/golang-migrate/migrate/v4/source/iofs"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/jackc/pgx/v5/stdlib"
	commonv1 "github.com/astockpursue/go-core/internal/gen/common/v1"
)

//go:embed migrations/*.sql
var migrationsFS embed.FS

// RunMigrations executes all pending database migrations from the embedded SQL files.
// connString should be a PostgreSQL connection string, e.g. "postgres://user:pass@localhost:5432/db?sslmode=disable".
func RunMigrations(connString string) error {
	d, err := iofs.New(migrationsFS, "migrations")
	if err != nil {
		return fmt.Errorf("migrations iofs: %w", err)
	}
	m, err := migrate.NewWithSourceInstance("iofs", d, connString)
	if err != nil {
		return fmt.Errorf("migrations init: %w", err)
	}
	if err := m.Up(); err != nil && err != migrate.ErrNoChange {
		return fmt.Errorf("migrations up: %w", err)
	}
	return nil
}

type TimescaleDB struct {
	pool *pgxpool.Pool
}

func NewTimescaleDB(ctx context.Context, connString string) (*TimescaleDB, error) {
	if ctx == nil {
		return nil, fmt.Errorf("timescale: context must not be nil")
	}
	if connString == "" {
		return nil, fmt.Errorf("timescale: connection string must not be empty")
	}
	pool, err := pgxpool.New(ctx, connString)
	if err != nil {
		return nil, fmt.Errorf("failed to create timescale pool: %w", err)
	}
	return &TimescaleDB{pool: pool}, nil
}

// Pool returns the underlying pgxpool.Pool for health checks.
func (db *TimescaleDB) Pool() *pgxpool.Pool {
	return db.pool
}

// DB returns a *sql.DB backed by the TimescaleDB connection pool.
// Use this when an API requires database/sql while still benefiting from pgx.
func (db *TimescaleDB) DB() *sql.DB {
	return stdlib.OpenDBFromPool(db.pool)
}

func (db *TimescaleDB) Close() {
	if db.pool != nil {
		db.pool.Close()
	}
}

func (db *TimescaleDB) InitSchema(ctx context.Context) error {
	statements := []string{
		db.buildBarsTableSQL(),
		db.buildBacktestRunsSQL(),
		db.buildEquityCurvesSQL(),
		db.buildTradesSQL(),
		db.buildSignalsTableSQL(),
		db.buildWorkflowsTableSQL(),
		db.buildScheduledJobsTableSQL(),
		db.buildUserSettingsTableSQL(),
		db.buildPaperTradingRunsTableSQL(),
		db.buildFactorResultsTableSQL(),
	}
	for _, s := range statements {
		if _, err := db.pool.Exec(ctx, s); err != nil {
			return fmt.Errorf("schema init: %w", err)
		}
	}
	return nil
}

func (db *TimescaleDB) buildBarsTableSQL() string {
	return `
CREATE TABLE IF NOT EXISTS bars (
    symbol     TEXT NOT NULL,
    timestamp  TIMESTAMPTZ NOT NULL,
    open       DOUBLE PRECISION NOT NULL,
    high       DOUBLE PRECISION NOT NULL,
    low        DOUBLE PRECISION NOT NULL,
    close      DOUBLE PRECISION NOT NULL,
    volume     BIGINT NOT NULL,
    frequency  TEXT NOT NULL DEFAULT '1d',
    PRIMARY KEY (symbol, timestamp, frequency)
);

SELECT create_hypertable('bars', 'timestamp', if_not_exists => TRUE);
`
}

func (db *TimescaleDB) buildBacktestRunsSQL() string {
	return `
CREATE TABLE IF NOT EXISTS backtest_runs (
    id              UUID PRIMARY KEY,
    symbols         TEXT[] NOT NULL,
    frequency       TEXT NOT NULL DEFAULT '1d',
    start_date      TIMESTAMPTZ NOT NULL,
    end_date        TIMESTAMPTZ NOT NULL,
    initial_cash    DOUBLE PRECISION NOT NULL,
    final_equity    DOUBLE PRECISION NOT NULL DEFAULT 0,
    total_return    DOUBLE PRECISION NOT NULL DEFAULT 0,
    sharpe_ratio    DOUBLE PRECISION NOT NULL DEFAULT 0,
    max_drawdown    DOUBLE PRECISION NOT NULL DEFAULT 0,
    max_drawdown_pct DOUBLE PRECISION NOT NULL DEFAULT 0,
    win_rate        DOUBLE PRECISION NOT NULL DEFAULT 0,
    total_trades    INT NOT NULL DEFAULT 0,
    winning_trades  INT NOT NULL DEFAULT 0,
    losing_trades   INT NOT NULL DEFAULT 0,
    signal_name     TEXT,
    risk_config     JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);`
}

func (db *TimescaleDB) buildEquityCurvesSQL() string {
	return `
CREATE TABLE IF NOT EXISTS equity_curves (
    run_id          UUID NOT NULL REFERENCES backtest_runs(id) ON DELETE CASCADE,
    timestamp       TIMESTAMPTZ NOT NULL,
    equity          DOUBLE PRECISION NOT NULL,
    cash            DOUBLE PRECISION NOT NULL,
    position_count  INT NOT NULL DEFAULT 0,
    PRIMARY KEY (run_id, timestamp)
);
SELECT create_hypertable('equity_curves', 'timestamp', if_not_exists => TRUE);`
}

func (db *TimescaleDB) buildTradesSQL() string {
	return `
CREATE TABLE IF NOT EXISTS trades (
    id          UUID PRIMARY KEY,
    run_id      UUID NOT NULL REFERENCES backtest_runs(id) ON DELETE CASCADE,
    symbol      TEXT NOT NULL,
    side        TEXT NOT NULL,
    quantity    DOUBLE PRECISION NOT NULL,
    price       DOUBLE PRECISION NOT NULL,
    commission  DOUBLE PRECISION NOT NULL DEFAULT 0,
    pnl         DOUBLE PRECISION,
    timestamp   TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_trades_run_id ON trades(run_id);`
}

func (db *TimescaleDB) InsertBars(ctx context.Context, bars []*commonv1.Bar) error {
	if len(bars) == 0 {
		return nil
	}
	if db.pool == nil {
		return fmt.Errorf("timescale pool is nil")
	}
	batch := &pgx.Batch{}
	for _, bar := range bars {
		batch.Queue(db.buildInsertSQL(),
			bar.Symbol,
			time.UnixMilli(bar.Timestamp),
			bar.Open, bar.High, bar.Low, bar.Close,
			bar.Volume,
			bar.Frequency,
		)
	}
	br := db.pool.SendBatch(ctx, batch)
	defer br.Close()
	_, err := br.Exec()
	return err
}

func (db *TimescaleDB) buildInsertSQL() string {
	return `
INSERT INTO bars (symbol, timestamp, open, high, low, close, volume, frequency)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
ON CONFLICT (symbol, timestamp, frequency) DO UPDATE
SET open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low,
    close = EXCLUDED.close, volume = EXCLUDED.volume;
`
}

type BarQuery struct {
	Symbol    string
	StartTime time.Time
	EndTime   time.Time
	Frequency string
	Limit     int
}

func (db *TimescaleDB) QueryBars(ctx context.Context, q BarQuery) ([]*commonv1.Bar, error) {
	if db.pool == nil {
		return nil, fmt.Errorf("database not available")
	}
	query := `SELECT symbol, timestamp, open, high, low, close, volume, frequency
FROM bars WHERE symbol = $1 AND timestamp >= $2 AND timestamp <= $3 AND frequency = $4
ORDER BY timestamp ASC`
	if q.Limit > 0 {
		query += fmt.Sprintf(" LIMIT %d", q.Limit)
	}
	rows, err := db.pool.Query(ctx, query, q.Symbol, q.StartTime, q.EndTime, q.Frequency)
	if err != nil {
		return nil, fmt.Errorf("query bars: %w", err)
	}
	defer rows.Close()

	var bars []*commonv1.Bar
	for rows.Next() {
		bar := &commonv1.Bar{}
		var ts time.Time
		err := rows.Scan(&bar.Symbol, &ts, &bar.Open, &bar.High, &bar.Low, &bar.Close, &bar.Volume, &bar.Frequency)
		if err != nil {
			return nil, fmt.Errorf("scan bar: %w", err)
		}
		bar.Timestamp = ts.UnixMilli()
		bars = append(bars, bar)
	}
	return bars, nil
}

func (db *TimescaleDB) buildSignalsTableSQL() string {
	return `
CREATE TABLE IF NOT EXISTS signals (
    id SERIAL PRIMARY KEY,
    user_id INTEGER DEFAULT 1,
    type VARCHAR(32) NOT NULL,
    symbol VARCHAR(32) NOT NULL,
    direction VARCHAR(8) DEFAULT 'buy',
    strength DOUBLE PRECISION DEFAULT 0,
    source VARCHAR(64) DEFAULT '',
    status VARCHAR(16) DEFAULT 'new',
    created_at TIMESTAMPTZ DEFAULT now()
);`
}

func (db *TimescaleDB) buildWorkflowsTableSQL() string {
	return `
CREATE TABLE IF NOT EXISTS workflows (
    id SERIAL PRIMARY KEY,
    user_id INTEGER DEFAULT 1,
    name VARCHAR(128) NOT NULL,
    nodes JSONB DEFAULT '[]',
    edges JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);`
}

func (db *TimescaleDB) buildScheduledJobsTableSQL() string {
	return `
CREATE TABLE IF NOT EXISTS scheduled_jobs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER DEFAULT 1,
    name VARCHAR(128) NOT NULL,
    job_type VARCHAR(32) DEFAULT 'backtest',
    cron_expr VARCHAR(64) NOT NULL,
    config JSONB DEFAULT '{}',
    status VARCHAR(16) DEFAULT 'pending',
    last_run TIMESTAMPTZ,
    next_run TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);`
}

func (db *TimescaleDB) buildUserSettingsTableSQL() string {
	return `
CREATE TABLE IF NOT EXISTS user_settings (
    user_id INTEGER PRIMARY KEY DEFAULT 1,
    settings JSONB NOT NULL DEFAULT '{}',
    updated_at TIMESTAMPTZ DEFAULT now()
);`
}

func (db *TimescaleDB) buildPaperTradingRunsTableSQL() string {
	return `
CREATE TABLE IF NOT EXISTS paper_trading_runs (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(128),
    strategy VARCHAR(64),
    status VARCHAR(16),
    initial_capital DOUBLE PRECISION,
    equity DOUBLE PRECISION,
    pnl DOUBLE PRECISION,
    pnl_pct DOUBLE PRECISION,
    config JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);`
}

func (db *TimescaleDB) buildFactorResultsTableSQL() string {
	return `
CREATE TABLE IF NOT EXISTS factor_results (
    id SERIAL PRIMARY KEY,
    factor_name VARCHAR(128) NOT NULL,
    symbol VARCHAR(32),
    value DOUBLE PRECISION,
    ic DOUBLE PRECISION,
    sharpe DOUBLE PRECISION,
    status VARCHAR(32) DEFAULT 'production',
    computed_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_factor_results_name ON factor_results(factor_name);`
}
