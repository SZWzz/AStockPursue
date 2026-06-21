// Package ml provides machine learning model management for the AStockPursue
// trading platform. It includes a SQLite-backed ModelRegistry for persisting
// trained models and an Evaluator for assessing model performance.
package ml

import "time"

// ModelType classifies the kind of ML model.
type ModelType string

const (
	ModelTypeClassifier ModelType = "classifier"
	ModelTypeRegressor  ModelType = "regressor"
	ModelTypeRanker     ModelType = "ranker"
)

// ModelCategory describes the trading-domain purpose of the model.
type ModelCategory string

const (
	CategoryFactor ModelCategory = "factor"
	CategorySignal ModelCategory = "signal"
	CategoryRisk   ModelCategory = "risk"
)

// ModelStatus tracks the lifecycle stage of a model.
type ModelStatus string

const (
	StatusTraining ModelStatus = "training"
	StatusReady    ModelStatus = "ready"
	StatusArchived ModelStatus = "archived"
)

// MLModel represents a serialized machine learning model stored in the registry.
type MLModel struct {
	ID          string
	Name        string
	ModelType   ModelType
	Category    ModelCategory
	Hyperparams map[string]any
	Metrics     map[string]float64
	FilePath    string
	FileBytes   []byte
	Status      ModelStatus
	CreatedAt   time.Time
	UpdatedAt   time.Time
}
