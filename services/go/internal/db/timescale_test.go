package db

import (
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
)

func TestTimescaleInsertAndQuery(t *testing.T) {
	if testing.Short() {
		t.Skip("skipping integration test (requires TimescaleDB)")
	}
	db := &TimescaleDB{}
	assert.NotNil(t, db)
}

func TestBuildInsertSQL(t *testing.T) {
	db := &TimescaleDB{}
	sql := db.buildInsertSQL()
	assert.Contains(t, sql, "INSERT INTO bars")
	assert.Contains(t, sql, "ON CONFLICT (symbol, timestamp, frequency)")
}

func TestBuildBarsTableSQL(t *testing.T) {
	db := &TimescaleDB{}
	sql := db.buildBarsTableSQL()
	assert.Contains(t, sql, "CREATE TABLE IF NOT EXISTS bars")
	assert.Contains(t, sql, "create_hypertable")
}

func TestBuildBacktestRunsSQL(t *testing.T) {
	db := &TimescaleDB{}
	sql := db.buildBacktestRunsSQL()
	assert.Contains(t, sql, "CREATE TABLE IF NOT EXISTS backtest_runs")
	assert.Contains(t, sql, "UUID")
}

func TestBuildEquityCurvesSQL(t *testing.T) {
	db := &TimescaleDB{}
	sql := db.buildEquityCurvesSQL()
	assert.Contains(t, sql, "CREATE TABLE IF NOT EXISTS equity_curves")
	assert.Contains(t, sql, "create_hypertable")
}

func TestBuildTradesSQL(t *testing.T) {
	db := &TimescaleDB{}
	sql := db.buildTradesSQL()
	assert.Contains(t, sql, "CREATE TABLE IF NOT EXISTS trades")
	assert.Contains(t, sql, "idx_trades_run_id")
}

func TestBarQueryStruct(t *testing.T) {
	q := BarQuery{
		Symbol:    "AAPL",
		StartTime: time.Date(2024, 1, 1, 0, 0, 0, 0, time.UTC),
		EndTime:   time.Date(2024, 1, 31, 0, 0, 0, 0, time.UTC),
		Frequency: "1d",
		Limit:     100,
	}
	assert.Equal(t, "AAPL", q.Symbol)
	assert.Equal(t, "1d", q.Frequency)
	assert.Equal(t, 100, q.Limit)
}

func TestNewTimescaleDB_EmptyConnString(t *testing.T) {
	if testing.Short() {
		t.Skip("skipping integration test (requires TimescaleDB)")
	}
	_, err := NewTimescaleDB(nil, "")
	assert.Error(t, err)
}

func TestInsertBars_EmptySlice(t *testing.T) {
	if testing.Short() {
		t.Skip("skipping test with nil TimescaleDB pool")
	}
	db := &TimescaleDB{}
	err := db.InsertBars(nil, nil)
	assert.NoError(t, err)
}
