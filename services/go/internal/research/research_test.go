package research

import (
	"context"
	"database/sql"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	_ "modernc.org/sqlite"
)

// newTestDB creates an in-memory SQLite database with the research_cache table.
func newTestDB(t *testing.T) *sql.DB {
	t.Helper()
	db, err := sql.Open("sqlite", ":memory:")
	require.NoError(t, err)
	_, err = db.Exec(`CREATE TABLE IF NOT EXISTS research_cache (
		symbol TEXT NOT NULL,
		category TEXT NOT NULL,
		key TEXT NOT NULL,
		value REAL NOT NULL DEFAULT 0,
		metadata TEXT DEFAULT '{}',
		fetched_at INTEGER NOT NULL,
		PRIMARY KEY (symbol, category, key)
	)`)
	require.NoError(t, err)
	t.Cleanup(func() { db.Close() })
	return db
}

func TestResearchService_MockDataGeneration(t *testing.T) {
	ctx := context.Background()

	t.Run("FinancialsService_mock", func(t *testing.T) {
		svc := NewFinancialsService(nil, nil)
		result, err := svc.Analyze(ctx, "600519.SH", nil)
		require.NoError(t, err)
		assert.NotEmpty(t, result)
		assert.NotZero(t, result["revenue_yoy"])
	})

	t.Run("NewsService_mock", func(t *testing.T) {
		svc := NewNewsService(nil, nil)
		result, err := svc.Analyze(ctx, "000001.SZ", nil)
		require.NoError(t, err)
		assert.NotEmpty(t, result)
		articles, ok := result["recent_articles"].([]map[string]any)
		assert.True(t, ok)
		assert.NotEmpty(t, articles)
	})

	t.Run("NorthboundService_mock", func(t *testing.T) {
		svc := NewNorthboundService(nil, nil)
		result, err := svc.Analyze(ctx, "000001.SZ", nil)
		require.NoError(t, err)
		assert.NotEmpty(t, result)
		assert.NotZero(t, result["net_inflow_daily"])
		assert.NotZero(t, result["cumulative_net_buy"])
	})

	t.Run("GeopoliticsService_mock", func(t *testing.T) {
		svc := NewGeopoliticsService(nil, nil)
		result, err := svc.Analyze(ctx, "", nil)
		require.NoError(t, err)
		assert.NotEmpty(t, result)
		topics, ok := result["topics"].([]map[string]any)
		assert.True(t, ok)
		assert.NotEmpty(t, topics)
		assert.Len(t, topics, len(predefinedTopics))
	})
}

func TestResearchService_NilRepo(t *testing.T) {
	ctx := context.Background()

	t.Run("FinancialsService_nil_repo_no_panic", func(t *testing.T) {
		svc := NewFinancialsService(nil, nil)
		assert.NotPanics(t, func() {
			_, _ = svc.Analyze(ctx, "600519.SH", nil)
		})
	})

	t.Run("NewsService_nil_repo_no_panic", func(t *testing.T) {
		svc := NewNewsService(nil, nil)
		assert.NotPanics(t, func() {
			_, _ = svc.Analyze(ctx, "000001.SZ", nil)
		})
	})

	t.Run("NorthboundService_nil_repo_no_panic", func(t *testing.T) {
		svc := NewNorthboundService(nil, nil)
		assert.NotPanics(t, func() {
			_, _ = svc.Analyze(ctx, "000001.SZ", nil)
		})
	})

	t.Run("GeopoliticsService_nil_repo_no_panic", func(t *testing.T) {
		svc := NewGeopoliticsService(nil, nil)
		assert.NotPanics(t, func() {
			_, _ = svc.Analyze(ctx, "", nil)
		})
	})
}

func TestResearchService_CacheSaveLoad(t *testing.T) {
	ctx := context.Background()
	db := newTestDB(t)
	repo := NewRepo(db)
	require.NoError(t, repo.Init())

	t.Run("FinancialsService_save_and_load", func(t *testing.T) {
		svc := NewFinancialsService(repo, nil)

		// First call should generate mock data and cache it
		result1, err := svc.Analyze(ctx, "600519.SH", nil)
		require.NoError(t, err)
		assert.NotEmpty(t, result1)

		// Second call should return cached data
		result2, err := svc.Analyze(ctx, "600519.SH", nil)
		require.NoError(t, err)
		assert.NotEmpty(t, result2)

		// Both results should be non-empty (mock and cached should be equivalent)
		assert.NotZero(t, result2["revenue_yoy"])
	})

	t.Run("NewsService_save_and_load", func(t *testing.T) {
		svc := NewNewsService(repo, nil)

		result1, err := svc.Analyze(ctx, "000001.SZ", nil)
		require.NoError(t, err)

		result2, err := svc.Analyze(ctx, "000001.SZ", nil)
		require.NoError(t, err)

		assert.NotEmpty(t, result2)
		// Non-panicking load from cache is the important verification
		_ = result1
	})

	t.Run("GeopoliticsService_save_and_load", func(t *testing.T) {
		svc := NewGeopoliticsService(repo, nil)

		result1, err := svc.Analyze(ctx, "", nil)
		require.NoError(t, err)

		result2, err := svc.Analyze(ctx, "", nil)
		require.NoError(t, err)

		topics, ok := result2["topics"].([]map[string]any)
		assert.True(t, ok)
		assert.Len(t, topics, len(predefinedTopics))
		_ = result1
	})

	t.Run("NorthboundService_save_and_load", func(t *testing.T) {
		svc := NewNorthboundService(repo, nil)

		result1, err := svc.Analyze(ctx, "000001.SZ", nil)
		require.NoError(t, err)

		result2, err := svc.Analyze(ctx, "000001.SZ", nil)
		require.NoError(t, err)

		assert.NotZero(t, result2["net_inflow_daily"])
		_ = result1
	})
}

func TestResearchService_Name(t *testing.T) {
	tests := []struct {
		svc  Service
		name string
	}{
		{NewFinancialsService(nil, nil), "financials"},
		{NewNewsService(nil, nil), "news"},
		{NewNorthboundService(nil, nil), "northbound"},
		{NewGeopoliticsService(nil, nil), "geopolitics"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			assert.Equal(t, tt.name, tt.svc.Name())
		})
	}
}

func TestResearchService_IsAvailable(t *testing.T) {
	assert.False(t, NewFinancialsService(nil, nil).IsAvailable())
	assert.False(t, NewNewsService(nil, nil).IsAvailable())
	assert.False(t, NewNorthboundService(nil, nil).IsAvailable())
	assert.False(t, NewGeopoliticsService(nil, nil).IsAvailable())
}

func TestRepo_GetCategory_EmptyTable(t *testing.T) {
	db := newTestDB(t)
	repo := NewRepo(db)
	require.NoError(t, repo.Init())

	dps, err := repo.GetCategory("600519.SH", "financials")
	assert.NoError(t, err)
	assert.Empty(t, dps)
}

func TestRepo_SaveAndGet(t *testing.T) {
	db := newTestDB(t)
	repo := NewRepo(db)
	require.NoError(t, repo.Init())

	dp := &DataPoint{
		Symbol:   "600519.SH",
		Category: "financials",
		Key:      "revenue_yoy",
		Value:    12.5,
		Date:     time.Now(),
	}
	err := repo.Save(dp)
	require.NoError(t, err)

	result, err := repo.Get("600519.SH", "financials", "revenue_yoy")
	assert.NoError(t, err)
	require.NotNil(t, result)
	assert.Equal(t, 12.5, result.Value)
	assert.Equal(t, "revenue_yoy", result.Key)
}
