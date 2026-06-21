package ml

import (
	"context"
	"database/sql"
	"testing"

	"github.com/stretchr/testify/assert"

	// Pure-Go SQLite driver for in-memory test databases.
	_ "modernc.org/sqlite"
)

func newTestDB(t *testing.T) *sql.DB {
	t.Helper()
	db, err := sql.Open("sqlite", ":memory:")
	assert.NoError(t, err)
	t.Cleanup(func() { db.Close() })
	return db
}

func newTestRegistry(t *testing.T) *ModelRegistry {
	t.Helper()
	db := newTestDB(t)
	reg := NewModelRegistry(db)
	assert.NoError(t, reg.Init())
	return reg
}

func TestCreate(t *testing.T) {
	reg := newTestRegistry(t)
	ctx := context.Background()

	model := &MLModel{
		Name:      "test-classifier",
		ModelType: ModelTypeClassifier,
		Category:  CategorySignal,
		Hyperparams: map[string]any{
			"n_estimators": float64(100),
			"max_depth":    float64(5),
		},
		Metrics: map[string]float64{
			"accuracy": 0.85,
		},
		FilePath: "/models/test.pkl",
	}

	err := reg.Create(ctx, model)
	assert.NoError(t, err)
	assert.NotEmpty(t, model.ID, "ID should be assigned on creation")
	assert.Equal(t, StatusTraining, model.Status)
	assert.False(t, model.CreatedAt.IsZero())
	assert.False(t, model.UpdatedAt.IsZero())

	// Verify we can retrieve it.
	got, err := reg.Get(ctx, model.ID)
	assert.NoError(t, err)
	assert.NotNil(t, got)
	assert.Equal(t, model.Name, got.Name)
	assert.Equal(t, ModelTypeClassifier, got.ModelType)
	assert.Equal(t, CategorySignal, got.Category)
	assert.Equal(t, float64(100), got.Hyperparams["n_estimators"])
	assert.Equal(t, 0.85, got.Metrics["accuracy"])
	assert.Equal(t, "/models/test.pkl", got.FilePath)
}

func TestList(t *testing.T) {
	reg := newTestRegistry(t)
	ctx := context.Background()

	// Create models in two categories.
	for i, cat := range []ModelCategory{CategoryFactor, CategorySignal, CategoryFactor} {
		err := reg.Create(ctx, &MLModel{
			Name:      "model-" + string(rune('a'+i)),
			ModelType: ModelTypeRegressor,
			Category:  cat,
			Hyperparams: map[string]any{
				"lr": 0.01,
			},
		})
		assert.NoError(t, err)
	}

	// List factor models — should return 2.
	factors, err := reg.List(ctx, CategoryFactor)
	assert.NoError(t, err)
	assert.Len(t, factors, 2)

	// List signal models — should return 1.
	signals, err := reg.List(ctx, CategorySignal)
	assert.NoError(t, err)
	assert.Len(t, signals, 1)

	// List risk models — should return 0.
	risks, err := reg.List(ctx, CategoryRisk)
	assert.NoError(t, err)
	assert.Len(t, risks, 0)
}

func TestArchive(t *testing.T) {
	reg := newTestRegistry(t)
	ctx := context.Background()

	model := &MLModel{
		Name:      "model-to-archive",
		ModelType: ModelTypeRanker,
		Category:  CategoryRisk,
	}
	err := reg.Create(ctx, model)
	assert.NoError(t, err)
	assert.Equal(t, StatusTraining, model.Status)

	// Archive it.
	err = reg.Archive(ctx, model.ID)
	assert.NoError(t, err)

	// Verify status changed.
	got, err := reg.Get(ctx, model.ID)
	assert.NoError(t, err)
	assert.NotNil(t, got)
	assert.Equal(t, StatusArchived, got.Status)
}

func TestListByStatus(t *testing.T) {
	reg := newTestRegistry(t)
	ctx := context.Background()

	for i, status := range []ModelStatus{StatusTraining, StatusReady, StatusTraining} {
		m := &MLModel{
			Name:      "model-" + string(rune('a'+i)),
			ModelType: ModelTypeClassifier,
			Category:  CategoryFactor,
			Status:    status,
		}
		err := reg.Create(ctx, m)
		assert.NoError(t, err)
	}

	training, err := reg.ListByStatus(ctx, StatusTraining)
	assert.NoError(t, err)
	assert.Len(t, training, 2)

	ready, err := reg.ListByStatus(ctx, StatusReady)
	assert.NoError(t, err)
	assert.Len(t, ready, 1)

	archived, err := reg.ListByStatus(ctx, StatusArchived)
	assert.NoError(t, err)
	assert.Len(t, archived, 0)
}

func TestUpdateMetrics(t *testing.T) {
	reg := newTestRegistry(t)
	ctx := context.Background()

	model := &MLModel{
		Name:      "model-to-update",
		ModelType: ModelTypeRegressor,
		Category:  CategorySignal,
		Metrics: map[string]float64{
			"r2": 0.72,
		},
	}
	err := reg.Create(ctx, model)
	assert.NoError(t, err)

	newMetrics := map[string]float64{
		"sharpe": 1.5,
		"r2":     0.88,
	}
	err = reg.UpdateMetrics(ctx, model.ID, newMetrics)
	assert.NoError(t, err)

	got, err := reg.Get(ctx, model.ID)
	assert.NoError(t, err)
	assert.Equal(t, 1.5, got.Metrics["sharpe"])
	assert.Equal(t, 0.88, got.Metrics["r2"])
}

func TestGetNonExistent(t *testing.T) {
	reg := newTestRegistry(t)
	ctx := context.Background()

	got, err := reg.Get(ctx, "non-existent-id")
	assert.NoError(t, err)
	assert.Nil(t, got, "non-existent model should return nil")
}

func TestCreateExplicitID(t *testing.T) {
	reg := newTestRegistry(t)
	ctx := context.Background()

	model := &MLModel{
		ID:        "explicit-id-123",
		Name:      "explicit-id-model",
		ModelType: ModelTypeRanker,
		Category:  CategoryFactor,
	}
	err := reg.Create(ctx, model)
	assert.NoError(t, err)
	assert.Equal(t, "explicit-id-123", model.ID)

	got, err := reg.Get(ctx, "explicit-id-123")
	assert.NoError(t, err)
	assert.NotNil(t, got)
}
