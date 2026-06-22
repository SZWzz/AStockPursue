package db

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestPostgresBacktestStoreNilPool(t *testing.T) {
	store := NewPostgresBacktestStore(nil)
	assert.NotNil(t, store)
}

func TestNewPGBacktestStore(t *testing.T) {
	store := NewPGBacktestStore(nil)
	assert.NotNil(t, store)
}

func TestSaveNilPool(t *testing.T) {
	store := &PostgresBacktestStore{}
	_, err := store.Save(nil, nil)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "database not available")
}

func TestGetNilPool(t *testing.T) {
	store := &PostgresBacktestStore{}
	_, err := store.Get(nil, "1")
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "database not available")
}

func TestListNilPool(t *testing.T) {
	store := &PostgresBacktestStore{}
	_, err := store.List(nil)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "database not available")
}

func TestListRowsNilPool(t *testing.T) {
	store := &PostgresBacktestStore{}
	_, err := store.ListRows(nil)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "database not available")
}
