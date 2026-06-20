package db

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestBuildInsertBacktestRunSQL(t *testing.T) {
	store := &PostgresBacktestStore{}
	sql := store.buildInsertRunSQL()
	assert.Contains(t, sql, "INSERT INTO backtest_runs")
}

func TestBuildInsertEquitySQL(t *testing.T) {
	store := &PostgresBacktestStore{}
	sql := store.buildInsertEquitySQL()
	assert.Contains(t, sql, "INSERT INTO equity_curves")
}

func TestBuildInsertTradesSQL(t *testing.T) {
	store := &PostgresBacktestStore{}
	sql := store.buildInsertTradesSQL()
	assert.Contains(t, sql, "INSERT INTO trades")
}

func TestBuildGetRunSQL(t *testing.T) {
	store := &PostgresBacktestStore{}
	sql := store.buildGetRunSQL()
	assert.Contains(t, sql, "symbols")
	assert.Contains(t, sql, "frequency")
	assert.Contains(t, sql, "FROM backtest_runs")
}

func TestBuildGetEquitySQL(t *testing.T) {
	store := &PostgresBacktestStore{}
	sql := store.buildGetEquitySQL()
	assert.Contains(t, sql, "FROM equity_curves")
	assert.Contains(t, sql, "ORDER BY timestamp")
}

func TestBuildGetTradesSQL(t *testing.T) {
	store := &PostgresBacktestStore{}
	sql := store.buildGetTradesSQL()
	assert.Contains(t, sql, "FROM trades")
	assert.Contains(t, sql, "ORDER BY timestamp")
}

func TestBuildListRunsSQL(t *testing.T) {
	store := &PostgresBacktestStore{}
	sql := store.buildListRunsSQL()
	assert.Contains(t, sql, "SELECT id FROM backtest_runs")
	assert.Contains(t, sql, "ORDER BY created_at DESC")
}

func TestNewPostgresBacktestStoreNilPool(t *testing.T) {
	if testing.Short() {
		t.Skip("skipping integration test")
	}
	store := NewPostgresBacktestStore(nil)
	assert.NotNil(t, store)
}
