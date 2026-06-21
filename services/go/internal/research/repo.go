package research

import (
	"database/sql"
	"encoding/json"
	"time"
)

const cacheTTL = 5 * time.Minute

type Repo struct {
	db *sql.DB
}

func NewRepo(db *sql.DB) *Repo { return &Repo{db: db} }

func (r *Repo) Init() error {
	_, err := r.db.Exec(`CREATE TABLE IF NOT EXISTS research_cache (
		symbol TEXT NOT NULL,
		category TEXT NOT NULL,
		key TEXT NOT NULL,
		value REAL NOT NULL DEFAULT 0,
		metadata TEXT DEFAULT '{}',
		fetched_at INTEGER NOT NULL,
		PRIMARY KEY (symbol, category, key)
	)`)
	return err
}

func (r *Repo) Get(symbol, category, key string) (*DataPoint, error) {
	row := r.db.QueryRow(
		"SELECT symbol, category, key, value, metadata, fetched_at FROM research_cache WHERE symbol=? AND category=? AND key=?",
		symbol, category, key,
	)
	dp := &DataPoint{}
	var metaJSON string
	var fetchedAt int64
	err := row.Scan(&dp.Symbol, &dp.Category, &dp.Key, &dp.Value, &metaJSON, &fetchedAt)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	dp.Date = time.Unix(fetchedAt, 0)
	if time.Since(dp.Date) > cacheTTL {
		return nil, nil // expired
	}
	_ = json.Unmarshal([]byte(metaJSON), &dp.Metadata)
	return dp, nil
}

func (r *Repo) Save(dp *DataPoint) error {
	metaJSON, _ := json.Marshal(dp.Metadata)
	_, err := r.db.Exec(
		`INSERT OR REPLACE INTO research_cache (symbol, category, key, value, metadata, fetched_at)
		 VALUES (?, ?, ?, ?, ?, ?)`,
		dp.Symbol, dp.Category, dp.Key, dp.Value, string(metaJSON), time.Now().Unix(),
	)
	return err
}

func (r *Repo) GetCategory(symbol, category string) ([]DataPoint, error) {
	rows, err := r.db.Query(
		"SELECT symbol, category, key, value, metadata, fetched_at FROM research_cache WHERE symbol=? AND category=?",
		symbol, category,
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var result []DataPoint
	for rows.Next() {
		dp := DataPoint{}
		var metaJSON string
		var fetchedAt int64
		if err := rows.Scan(&dp.Symbol, &dp.Category, &dp.Key, &dp.Value, &metaJSON, &fetchedAt); err != nil {
			continue
		}
		dp.Date = time.Unix(fetchedAt, 0)
		_ = json.Unmarshal([]byte(metaJSON), &dp.Metadata)
		if time.Since(dp.Date) <= cacheTTL {
			result = append(result, dp)
		}
	}
	return result, nil
}
