package papertrade

import (
	"context"
	"encoding/json"

	"github.com/jackc/pgx/v5/pgxpool"
)

// PGRunRepository persists paper trading runs to PostgreSQL.
type PGRunRepository struct {
	db *pgxpool.Pool
}

// NewPGRunRepository creates a new PGRunRepository.
func NewPGRunRepository(db *pgxpool.Pool) *PGRunRepository {
	return &PGRunRepository{db: db}
}

type runConfig struct {
	Symbols   []string `json:"symbols"`
	Frequency string   `json:"frequency"`
}

func (r *PGRunRepository) Save(run *Run) error {
	if r.db == nil {
		return nil
	}

	cfg := runConfig{
		Symbols:   run.Symbols,
		Frequency: run.Frequency,
	}
	cfgJSON, err := json.Marshal(cfg)
	if err != nil {
		return err
	}

	_, err = r.db.Exec(context.Background(),
		`INSERT INTO paper_trading_runs (id, name, strategy, status, initial_capital, equity, pnl, pnl_pct, config)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
		 ON CONFLICT (id) DO UPDATE SET
		 status = EXCLUDED.status, equity = EXCLUDED.equity,
		 pnl = EXCLUDED.pnl, pnl_pct = EXCLUDED.pnl_pct,
		 config = EXCLUDED.config`,
		run.ID, run.Name, "", string(run.Status),
		run.InitialCash, 0.0, 0.0, 0.0, cfgJSON,
	)
	return err
}

func (r *PGRunRepository) LoadAll() ([]*Run, error) {
	if r.db == nil {
		return nil, nil
	}

	rows, err := r.db.Query(context.Background(),
		`SELECT id, name, strategy, status, initial_capital, config, created_at
		 FROM paper_trading_runs ORDER BY created_at DESC`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var runs []*Run
	for rows.Next() {
		var run Run
		var strategy, status string
		var cfgJSON []byte
		if err := rows.Scan(&run.ID, &run.Name, &strategy, &status,
			&run.InitialCash, &cfgJSON, &run.CreatedAt); err != nil {
			return nil, err
		}
		run.Status = RunStatus(status)
		var cfg runConfig
		if err := json.Unmarshal(cfgJSON, &cfg); err == nil {
			run.Symbols = cfg.Symbols
			run.Frequency = cfg.Frequency
		}
		runs = append(runs, &run)
	}
	return runs, nil
}

func (r *PGRunRepository) Delete(id string) error {
	if r.db == nil {
		return nil
	}
	_, err := r.db.Exec(context.Background(),
		`DELETE FROM paper_trading_runs WHERE id = $1`, id)
	return err
}
