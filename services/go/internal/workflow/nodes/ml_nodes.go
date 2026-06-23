// Package nodes provides built-in workflow node implementations for the
// AStockPursue Go workflow engine.  This file contains ML-related nodes
// for training, evaluating, predicting, comparing models and inspecting
// feature importance.
package nodes

import (
	"context"
	"crypto/sha256"
	"fmt"
	"math"
	"sort"

	"github.com/astockpursue/go-core/internal/ml"
	"github.com/astockpursue/go-core/internal/workflow"
	"github.com/google/uuid"
)

// ---------------------------------------------------------------------------
// 1. train_model — mock model training that generates a UUID model ID
// ---------------------------------------------------------------------------

// TrainModelNode mocks model training by generating a UUID-based model ID
// and recording the model_type and category from parameters.
type TrainModelNode struct {
	id string
}

func (n *TrainModelNode) ID() string      { return n.id }
func (n *TrainModelNode) NodeType() string { return "train_model" }
func (n *TrainModelNode) Category() string { return "ml" }

func (n *TrainModelNode) InputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "dataset", Type: workflow.PortAny, Required: true},
	}
}

func (n *TrainModelNode) OutputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "model_id", Type: workflow.PortAny, Required: true},
	}
}

func (n *TrainModelNode) ParamSchema() []workflow.ParamDef {
	return []workflow.ParamDef{
		{Name: "model_type", Type: "string", Default: "regressor", Description: "Type of model: regressor, classifier, ranker"},
		{Name: "category", Type: "string", Default: "factor", Description: "Model category: factor, signal, risk"},
	}
}

func (n *TrainModelNode) Execute(ctx context.Context, inputs workflow.NodeParams, params workflow.NodeParams) (workflow.NodeOutputs, error) {
	if _, ok := inputs["dataset"]; !ok {
		return nil, fmt.Errorf("train_model: dataset input is required")
	}
	// Mock: generate a unique model ID
	modelID := uuid.New().String()
	return workflow.NodeOutputs{"model_id": modelID}, nil
}

func (n *TrainModelNode) Validate() error { return nil }

// ---------------------------------------------------------------------------
// 2. evaluate_model — evaluates an ML model's performance
// ---------------------------------------------------------------------------

// EvaluateModelNode computes performance metrics for a trained model.
// If an ml.Evaluator is provided it delegates to Evaluator.Evaluate;
// otherwise it falls back to a deterministic mock derived from the model_id.
type EvaluateModelNode struct {
	id        string
	evaluator *ml.Evaluator
}

func (n *EvaluateModelNode) ID() string      { return n.id }
func (n *EvaluateModelNode) NodeType() string { return "evaluate_model" }
func (n *EvaluateModelNode) Category() string { return "ml" }

func (n *EvaluateModelNode) InputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "model_id", Type: workflow.PortAny, Required: true},
	}
}

func (n *EvaluateModelNode) OutputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "sharpe", Type: workflow.PortAny, Required: true},
		{Name: "max_drawdown", Type: workflow.PortAny, Required: true},
		{Name: "win_rate", Type: workflow.PortAny, Required: true},
		{Name: "total_return", Type: workflow.PortAny, Required: true},
		{Name: "ic", Type: workflow.PortAny, Required: true},
		{Name: "ir", Type: workflow.PortAny, Required: true},
	}
}

func (n *EvaluateModelNode) ParamSchema() []workflow.ParamDef {
	return []workflow.ParamDef{
		{Name: "symbols", Type: "string_array", Default: []string{}, Description: "Symbols to evaluate on"},
		{Name: "start_date", Type: "string", Default: "", Description: "Evaluation start date (YYYY-MM-DD)"},
		{Name: "end_date", Type: "string", Default: "", Description: "Evaluation end date (YYYY-MM-DD)"},
	}
}

func (n *EvaluateModelNode) Execute(ctx context.Context, inputs workflow.NodeParams, params workflow.NodeParams) (workflow.NodeOutputs, error) {
	modelID, ok := inputs["model_id"].(string)
	if !ok {
		return nil, fmt.Errorf("evaluate_model: model_id must be a string, got %T", inputs["model_id"])
	}

	// Extract optional evaluation parameters
	symbols, _ := params["symbols"].([]string)
	startDate, _ := params["start_date"].(string)
	endDate, _ := params["end_date"].(string)

	// Use the real ml.Evaluator if available
	if n.evaluator != nil {
		result, err := n.evaluator.Evaluate(ctx, modelID, symbols, startDate, endDate)
		if err != nil {
			return nil, fmt.Errorf("evaluate_model: %w", err)
		}
		return workflow.NodeOutputs{
			"sharpe":       result.Sharpe,
			"max_drawdown": result.MaxDrawdown,
			"win_rate":     result.WinRate,
			"total_return": result.TotalReturn,
			"ic":           result.IC,
			"ir":           result.IR,
		}, nil
	}

	// Fallback: deterministic mock metrics derived from model_id hash
	h := sha256.Sum256([]byte(modelID))
	seed := float64(h[0])/255.0 + float64(h[1])/255.0*0.1

	sharpe := 0.5 + seed*2.0         // range ~0.5 to 2.5
	maxDD := 0.05 + seed*0.25        // range ~0.05 to 0.30
	winRate := 0.40 + seed*0.25      // range ~0.40 to 0.65
	totalReturn := 0.05 + seed*0.45  // range ~0.05 to 0.50
	ic := 0.01 + seed*0.10           // range ~0.01 to 0.11
	ir := sharpe / math.Sqrt(252)    // annualized IR

	return workflow.NodeOutputs{
		"sharpe":       math.Round(sharpe*10000) / 10000,
		"max_drawdown": math.Round(maxDD*10000) / 10000,
		"win_rate":     math.Round(winRate*10000) / 10000,
		"total_return": math.Round(totalReturn*10000) / 10000,
		"ic":           math.Round(ic*10000) / 10000,
		"ir":           math.Round(ir*10000) / 10000,
	}, nil
}

func (n *EvaluateModelNode) Validate() error { return nil }

// ---------------------------------------------------------------------------
// 3. predict — makes a mock prediction from model_id + features
// ---------------------------------------------------------------------------

// PredictNode generates a deterministic mock prediction in [-1, 1] derived
// from the model_id hash.
type PredictNode struct {
	id string
}

func (n *PredictNode) ID() string      { return n.id }
func (n *PredictNode) NodeType() string { return "predict" }
func (n *PredictNode) Category() string { return "ml" }

func (n *PredictNode) InputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "model_id", Type: workflow.PortAny, Required: true},
		{Name: "features", Type: workflow.PortAny, Required: true},
	}
}

func (n *PredictNode) OutputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "prediction", Type: workflow.PortAny, Required: true},
	}
}

func (n *PredictNode) ParamSchema() []workflow.ParamDef { return nil }

func (n *PredictNode) Execute(ctx context.Context, inputs workflow.NodeParams, params workflow.NodeParams) (workflow.NodeOutputs, error) {
	modelID, ok := inputs["model_id"].(string)
	if !ok {
		return nil, fmt.Errorf("predict: model_id must be a string, got %T", inputs["model_id"])
	}
	if _, ok := inputs["features"]; !ok {
		return nil, fmt.Errorf("predict: features input is required")
	}

	// Deterministic mock: prediction in [-1, 1] from model_id hash
	h := sha256.Sum256([]byte(modelID))
	seed := float64(h[0]) / 255.0
	prediction := (seed - 0.5) * 2.0

	return workflow.NodeOutputs{"prediction": math.Round(prediction*10000) / 10000}, nil
}

func (n *PredictNode) Validate() error { return nil }

// ---------------------------------------------------------------------------
// 4. feature_importance — mock feature importance (top 5 features)
// ---------------------------------------------------------------------------

// FeatureImportanceNode returns deterministic mock feature importance values
// for the top 5 features derived from the model_id hash.
type FeatureImportanceNode struct {
	id string
}

func (n *FeatureImportanceNode) ID() string      { return n.id }
func (n *FeatureImportanceNode) NodeType() string { return "feature_importance" }
func (n *FeatureImportanceNode) Category() string { return "ml" }

func (n *FeatureImportanceNode) InputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "model_id", Type: workflow.PortAny, Required: true},
	}
}

func (n *FeatureImportanceNode) OutputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "importance", Type: workflow.PortAny, Required: true},
	}
}

func (n *FeatureImportanceNode) ParamSchema() []workflow.ParamDef { return nil }

func (n *FeatureImportanceNode) Execute(ctx context.Context, inputs workflow.NodeParams, params workflow.NodeParams) (workflow.NodeOutputs, error) {
	modelID, ok := inputs["model_id"].(string)
	if !ok {
		return nil, fmt.Errorf("feature_importance: model_id must be a string, got %T", inputs["model_id"])
	}

	// Deterministic mock: derive 5 feature importances from model_id hash
	h := sha256.Sum256([]byte(modelID))
	names := []string{"momentum_1m", "volatility_20d", "volume_trend", "rsi_14", "macd"}
	raw := make([]float64, 5)
	total := 0.0
	for i := 0; i < 5; i++ {
		raw[i] = float64(h[i]) / 255.0
		total += raw[i]
	}
	importance := make(map[string]float64, 5)
	if total > 0 {
		for i, name := range names {
			importance[name] = math.Round(raw[i]/total*10000) / 10000
		}
	} else {
		for i, name := range names {
			_ = i
			importance[name] = 0.2
		}
	}

	return workflow.NodeOutputs{"importance": importance}, nil
}

func (n *FeatureImportanceNode) Validate() error { return nil }

// ---------------------------------------------------------------------------
// 5. model_compare — compares multiple models and returns rankings (mock)
// ---------------------------------------------------------------------------

// ModelRank represents a single model's position in a comparison ranking.
type ModelRank struct {
	ModelID string  `json:"model_id"`
	Score   float64 `json:"score"`
	Rank    int     `json:"rank"`
}

// ModelCompareNode sorts models by a deterministic score derived from their
// ID hash and returns the full ranking.
type ModelCompareNode struct {
	id string
}

func (n *ModelCompareNode) ID() string      { return n.id }
func (n *ModelCompareNode) NodeType() string { return "model_compare" }
func (n *ModelCompareNode) Category() string { return "ml" }

func (n *ModelCompareNode) InputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "model_ids", Type: workflow.PortAny, Required: true},
	}
}

func (n *ModelCompareNode) OutputPorts() []workflow.PortDef {
	return []workflow.PortDef{
		{Name: "rankings", Type: workflow.PortAny, Required: true},
	}
}

func (n *ModelCompareNode) ParamSchema() []workflow.ParamDef { return nil }

func (n *ModelCompareNode) Execute(ctx context.Context, inputs workflow.NodeParams, params workflow.NodeParams) (workflow.NodeOutputs, error) {
	rawIDs, ok := inputs["model_ids"].([]string)
	if !ok {
		// Accept []any (JSON unmarshalling convention) as fallback.
		rawAny, ok2 := inputs["model_ids"].([]any)
		if !ok2 {
			return nil, fmt.Errorf("model_compare: model_ids must be []string, got %T", inputs["model_ids"])
		}
		rawIDs = make([]string, len(rawAny))
		for i, v := range rawAny {
			s, ok3 := v.(string)
			if !ok3 {
				return nil, fmt.Errorf("model_compare: model_ids[%d] must be string, got %T", i, v)
			}
			rawIDs[i] = s
		}
	}

	if len(rawIDs) == 0 {
		return workflow.NodeOutputs{"rankings": []ModelRank{}}, nil
	}

	type scoredItem struct {
		modelID string
		score   float64
	}
	items := make([]scoredItem, len(rawIDs))
	for i, mid := range rawIDs {
		h := sha256.Sum256([]byte(mid))
		score := float64(h[0])/255.0 + float64(h[1])/255.0*0.01
		items[i] = scoredItem{modelID: mid, score: math.Round(score*10000) / 10000}
	}
	sort.SliceStable(items, func(i, j int) bool {
		return items[i].score > items[j].score
	})

	rankings := make([]ModelRank, len(items))
	for i, item := range items {
		rankings[i] = ModelRank{
			ModelID: item.modelID,
			Score:   item.score,
			Rank:    i + 1,
		}
	}

	return workflow.NodeOutputs{"rankings": rankings}, nil
}

func (n *ModelCompareNode) Validate() error { return nil }

// ---------------------------------------------------------------------------
// Self-registration via init()
// ---------------------------------------------------------------------------

func init() {
	workflow.DefaultRegistry.RegisterWithCategory("train_model", func(id string, params workflow.NodeParams) (workflow.BaseNode, error) {
		return &TrainModelNode{id: id}, nil
	}, "ml")

	workflow.DefaultRegistry.RegisterWithCategory("evaluate_model", func(id string, params workflow.NodeParams) (workflow.BaseNode, error) {
		return &EvaluateModelNode{id: id, evaluator: nil}, nil
	}, "ml")

	workflow.DefaultRegistry.RegisterWithCategory("predict", func(id string, params workflow.NodeParams) (workflow.BaseNode, error) {
		return &PredictNode{id: id}, nil
	}, "ml")

	workflow.DefaultRegistry.RegisterWithCategory("feature_importance", func(id string, params workflow.NodeParams) (workflow.BaseNode, error) {
		return &FeatureImportanceNode{id: id}, nil
	}, "ml")

	workflow.DefaultRegistry.RegisterWithCategory("model_compare", func(id string, params workflow.NodeParams) (workflow.BaseNode, error) {
		return &ModelCompareNode{id: id}, nil
	}, "ml")
}
