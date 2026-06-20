package market

import (
	"os"
	"path/filepath"
	"testing"
	"time"

	commonv1 "github.com/astockpursue/go-core/internal/gen/common/v1"
	"github.com/stretchr/testify/assert"
)

func TestLocalStoreSaveAndLoad(t *testing.T) {
	dir := t.TempDir()
	store := NewLocalStore(dir)

	bars := []*commonv1.Bar{
		{Symbol: "600000", Open: 10.0, High: 11.0, Low: 9.5, Close: 10.5, Volume: 1000000, Timestamp: time.Date(2026, 1, 2, 0, 0, 0, 0, time.UTC).UnixMilli(), Frequency: "1d"},
		{Symbol: "600000", Open: 10.5, High: 11.5, Low: 10.0, Close: 11.0, Volume: 1500000, Timestamp: time.Date(2026, 1, 3, 0, 0, 0, 0, time.UTC).UnixMilli(), Frequency: "1d"},
	}

	err := store.SaveBars("600000", "1d", bars)
	assert.NoError(t, err)

	// Verify file was created
	expectedPath := filepath.Join(dir, "sh", "600000", "1d.jsonl")
	assert.FileExists(t, expectedPath)

	// Load with full range
	start := time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)
	end := time.Date(2026, 1, 10, 0, 0, 0, 0, time.UTC)
	loaded, err := store.LoadBars("600000", start, end, "1d")
	assert.NoError(t, err)
	assert.Equal(t, 2, len(loaded))
	assert.InDelta(t, 10.0, loaded[0].Open, 0.01)
	assert.InDelta(t, 11.0, loaded[1].Close, 0.01)
}

func TestLocalStoreLoadWithDateFilter(t *testing.T) {
	dir := t.TempDir()
	store := NewLocalStore(dir)

	bars := []*commonv1.Bar{
		{Symbol: "600000", Open: 10.0, Close: 10.5, Volume: 1000000, Timestamp: time.Date(2026, 1, 2, 0, 0, 0, 0, time.UTC).UnixMilli(), Frequency: "1d"},
		{Symbol: "600000", Open: 11.0, Close: 11.5, Volume: 2000000, Timestamp: time.Date(2026, 1, 5, 0, 0, 0, 0, time.UTC).UnixMilli(), Frequency: "1d"},
		{Symbol: "600000", Open: 12.0, Close: 12.5, Volume: 3000000, Timestamp: time.Date(2026, 2, 1, 0, 0, 0, 0, time.UTC).UnixMilli(), Frequency: "1d"},
	}
	store.SaveBars("600000", "1d", bars)

	// Only January data
	start := time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)
	end := time.Date(2026, 1, 31, 0, 0, 0, 0, time.UTC)
	loaded, err := store.LoadBars("600000", start, end, "1d")
	assert.NoError(t, err)
	assert.Equal(t, 2, len(loaded))
}

func TestLocalStoreLoadEmptyFile(t *testing.T) {
	dir := t.TempDir()
	store := NewLocalStore(dir)

	start := time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)
	end := time.Date(2026, 1, 10, 0, 0, 0, 0, time.UTC)
	loaded, err := store.LoadBars("600000", start, end, "1d")
	assert.NoError(t, err)
	assert.Equal(t, 0, len(loaded))
}

func TestLocalStoreSaveDedup(t *testing.T) {
	dir := t.TempDir()
	store := NewLocalStore(dir)

	ts := time.Date(2026, 1, 2, 0, 0, 0, 0, time.UTC).UnixMilli()
	bars1 := []*commonv1.Bar{
		{Symbol: "600000", Open: 10.0, Close: 10.5, Timestamp: ts, Frequency: "1d"},
	}
	bars2 := []*commonv1.Bar{
		{Symbol: "600000", Open: 99.0, Close: 99.5, Timestamp: ts, Frequency: "1d"},
	}

	store.SaveBars("600000", "1d", bars1)
	store.SaveBars("600000", "1d", bars2)

	start := time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)
	end := time.Date(2026, 1, 10, 0, 0, 0, 0, time.UTC)
	loaded, err := store.LoadBars("600000", start, end, "1d")
	assert.NoError(t, err)
	// Dedup: same timestamp should not duplicate
	assert.Equal(t, 1, len(loaded))
	// First write wins (original data preserved)
	assert.InDelta(t, 10.0, loaded[0].Open, 0.01)
}

func TestLocalStoreSZSymbol(t *testing.T) {
	dir := t.TempDir()
	store := NewLocalStore(dir)

	bars := []*commonv1.Bar{
		{Symbol: "000001", Open: 5.0, Close: 5.5, Volume: 500000, Timestamp: time.Date(2026, 1, 2, 0, 0, 0, 0, time.UTC).UnixMilli(), Frequency: "1d"},
	}
	store.SaveBars("000001", "1d", bars)

	expectedPath := filepath.Join(dir, "sz", "000001", "1d.jsonl")
	assert.FileExists(t, expectedPath)
}

func TestLocalStoreBJSymbol(t *testing.T) {
	dir := t.TempDir()
	store := NewLocalStore(dir)

	bars := []*commonv1.Bar{
		{Symbol: "430047", Open: 8.0, Close: 8.5, Volume: 200000, Timestamp: time.Date(2026, 1, 2, 0, 0, 0, 0, time.UTC).UnixMilli(), Frequency: "1d"},
	}
	store.SaveBars("430047", "1d", bars)

	expectedPath := filepath.Join(dir, "bj", "430047", "1d.jsonl")
	assert.FileExists(t, expectedPath)
}

func TestLocalStoreSaveBarsEmptyDir(t *testing.T) {
	// Store basePath may not exist yet - should create it
	dir := filepath.Join(t.TempDir(), "nonexistent", "subdir")
	store := NewLocalStore(dir)

	bars := []*commonv1.Bar{
		{Symbol: "600000", Open: 10.0, Close: 10.5, Volume: 1000000, Timestamp: time.Date(2026, 1, 2, 0, 0, 0, 0, time.UTC).UnixMilli(), Frequency: "1d"},
	}
	err := store.SaveBars("600000", "1d", bars)
	assert.NoError(t, err)
	assert.DirExists(t, dir)
}

func TestLocalStorePath(t *testing.T) {
	store := NewLocalStore("/data/bars")
	assert.Equal(t, "/data/bars", store.Path())
}

func TestLocalStoreDelete(t *testing.T) {
	dir := t.TempDir()
	store := NewLocalStore(dir)

	bars := []*commonv1.Bar{
		{Symbol: "600000", Open: 10.0, Close: 10.5, Timestamp: time.Now().UnixMilli(), Frequency: "1d"},
	}
	store.SaveBars("600000", "1d", bars)

	err := store.DeleteBars("600000", "1d")
	assert.NoError(t, err)

	path := store.filePath("600000", "1d")
	_, err = os.Stat(path)
	assert.True(t, os.IsNotExist(err))
}
