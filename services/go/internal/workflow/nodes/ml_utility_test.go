package nodes

import (
	"context"
	"testing"

	"github.com/astockpursue/go-core/internal/workflow"
)

// TestMLNodesRegistered verifies that all 5 ML node types are registered
// in the DefaultRegistry and can be instantiated with the correct NodeType
// and Category.
func TestMLNodesRegistered(t *testing.T) {
	tests := []struct {
		nodeType string
		category string
	}{
		{nodeType: "train_model", category: "ml"},
		{nodeType: "evaluate_model", category: "ml"},
		{nodeType: "predict", category: "ml"},
		{nodeType: "feature_importance", category: "ml"},
		{nodeType: "model_compare", category: "ml"},
	}

	for _, tt := range tests {
		t.Run(tt.nodeType, func(t *testing.T) {
			id := "test-" + tt.nodeType + "-1"
			node, err := workflow.DefaultRegistry.Create(tt.nodeType, id, nil)
			if err != nil {
				t.Fatalf("failed to create node %q: %v", tt.nodeType, err)
			}

			if got := node.NodeType(); got != tt.nodeType {
				t.Errorf("NodeType() = %q, want %q", got, tt.nodeType)
			}

			if got := node.Category(); got != tt.category {
				t.Errorf("Category() = %q, want %q", got, tt.category)
			}

			if got := node.ID(); got != id {
				t.Errorf("ID() = %q, want %q", got, id)
			}

			if err := node.Validate(); err != nil {
				t.Errorf("Validate() returned error: %v", err)
			}
		})
	}
}

// TestUtilityNodesRegistered verifies that all 6 utility node types are
// registered in the DefaultRegistry and can be instantiated with the
// correct NodeType and Category.
func TestUtilityNodesRegistered(t *testing.T) {
	tests := []struct {
		nodeType string
		category string
	}{
		{nodeType: "scale", category: "utility"},
		{nodeType: "arithmetic", category: "utility"},
		{nodeType: "schedule", category: "schedule"},
		{nodeType: "alert", category: "notify"},
		{nodeType: "branch", category: "control"},
		{nodeType: "merge", category: "control"},
	}

	for _, tt := range tests {
		t.Run(tt.nodeType, func(t *testing.T) {
			id := "test-" + tt.nodeType + "-1"
			node, err := workflow.DefaultRegistry.Create(tt.nodeType, id, nil)
			if err != nil {
				t.Fatalf("failed to create node %q: %v", tt.nodeType, err)
			}

			if got := node.NodeType(); got != tt.nodeType {
				t.Errorf("NodeType() = %q, want %q", got, tt.nodeType)
			}

			if got := node.Category(); got != tt.category {
				t.Errorf("Category() = %q, want %q", got, tt.category)
			}

			if got := node.ID(); got != id {
				t.Errorf("ID() = %q, want %q", got, id)
			}

			if err := node.Validate(); err != nil {
				t.Errorf("Validate() returned error: %v", err)
			}
		})
	}
}

// TestTrainModelNode verifies the train_model node execution.
func TestTrainModelNode(t *testing.T) {
	node, err := workflow.DefaultRegistry.Create("train_model", "test-train-1", nil)
	if err != nil {
		t.Fatalf("failed to create train_model node: %v", err)
	}

	result, err := node.Execute(context.Background(), map[string]any{
		"dataset": map[string]any{"feature_1": []float64{1.0, 2.0, 3.0}},
	}, map[string]any{
		"model_type": "regressor",
		"category":   "factor",
	})
	if err != nil {
		t.Fatalf("Execute() returned error: %v", err)
	}

	modelID, ok := result["model_id"].(string)
	if !ok {
		t.Fatal("model_id output must be a string")
	}
	if modelID == "" {
		t.Fatal("model_id must not be empty")
	}
}

// TestEvaluateModelNode verifies the evaluate_model node with mock fallback.
func TestEvaluateModelNode(t *testing.T) {
	node, err := workflow.DefaultRegistry.Create("evaluate_model", "test-eval-1", nil)
	if err != nil {
		t.Fatalf("failed to create evaluate_model node: %v", err)
	}

	result, err := node.Execute(context.Background(), map[string]any{
		"model_id": "test-model-123",
	}, map[string]any{
		"symbols":    []string{"000001.SZ"},
		"start_date": "2025-01-01",
		"end_date":   "2025-12-31",
	})
	if err != nil {
		t.Fatalf("Execute() returned error: %v", err)
	}

	expectedKeys := []string{"sharpe", "max_drawdown", "win_rate", "total_return", "ic", "ir"}
	for _, key := range expectedKeys {
		if _, ok := result[key]; !ok {
			t.Errorf("missing output key %q", key)
		}
	}
}

// TestPredictNode verifies the predict node execution.
func TestPredictNode(t *testing.T) {
	node, err := workflow.DefaultRegistry.Create("predict", "test-pred-1", nil)
	if err != nil {
		t.Fatalf("failed to create predict node: %v", err)
	}

	result, err := node.Execute(context.Background(), map[string]any{
		"model_id": "test-model-456",
		"features": map[string]any{"momentum": 0.5, "volatility": 0.3},
	}, nil)
	if err != nil {
		t.Fatalf("Execute() returned error: %v", err)
	}

	prediction, ok := result["prediction"].(float64)
	if !ok {
		t.Fatal("prediction output must be float64")
	}
	if prediction < -1 || prediction > 1 {
		t.Errorf("prediction %f out of expected range [-1, 1]", prediction)
	}
}

// TestFeatureImportanceNode verifies the feature_importance node execution.
func TestFeatureImportanceNode(t *testing.T) {
	node, err := workflow.DefaultRegistry.Create("feature_importance", "test-fi-1", nil)
	if err != nil {
		t.Fatalf("failed to create feature_importance node: %v", err)
	}

	result, err := node.Execute(context.Background(), map[string]any{
		"model_id": "test-model-789",
	}, nil)
	if err != nil {
		t.Fatalf("Execute() returned error: %v", err)
	}

	importance, ok := result["importance"].(map[string]float64)
	if !ok {
		t.Fatal("importance output must be map[string]float64")
	}
	if len(importance) != 5 {
		t.Errorf("expected 5 features, got %d", len(importance))
	}
}

// TestModelCompareNode verifies the model_compare node execution.
func TestModelCompareNode(t *testing.T) {
	node, err := workflow.DefaultRegistry.Create("model_compare", "test-mc-1", nil)
	if err != nil {
		t.Fatalf("failed to create model_compare node: %v", err)
	}

	result, err := node.Execute(context.Background(), map[string]any{
		"model_ids": []string{"model-a", "model-b", "model-c"},
	}, nil)
	if err != nil {
		t.Fatalf("Execute() returned error: %v", err)
	}

	rankingsRaw, ok := result["rankings"]
	if !ok {
		t.Fatal("rankings output missing")
	}
	rankings, ok := rankingsRaw.([]ModelRank)
	if !ok {
		t.Fatalf("rankings must be []ModelRank, got %T", rankingsRaw)
	}
	if len(rankings) != 3 {
		t.Errorf("expected 3 rankings, got %d", len(rankings))
	}
	// Verify ordering: first rank should be 1
	if rankings[0].Rank != 1 {
		t.Errorf("first ranking should be rank 1, got %d", rankings[0].Rank)
	}
}

// TestScaleNode verifies the scale node with minmax method.
func TestScaleNode(t *testing.T) {
	node, err := workflow.DefaultRegistry.Create("scale", "test-scale-1", nil)
	if err != nil {
		t.Fatalf("failed to create scale node: %v", err)
	}

	result, err := node.Execute(context.Background(), map[string]any{
		"series": []float64{10.0, 20.0, 30.0, 40.0, 50.0},
	}, map[string]any{
		"method":    "minmax",
		"range_min": 0.0,
		"range_max": 1.0,
	})
	if err != nil {
		t.Fatalf("Execute() returned error: %v", err)
	}

	scaled, ok := result["scaled"].([]float64)
	if !ok {
		t.Fatal("scaled output must be []float64")
	}
	if len(scaled) != 5 {
		t.Fatalf("expected 5 values, got %d", len(scaled))
	}
	if scaled[0] != 0.0 || scaled[4] != 1.0 {
		t.Errorf("minmax bounds: expected [0, 1], got [%f, %f]", scaled[0], scaled[4])
	}
}

// TestScaleZScoreNode verifies the scale node with zscore method.
func TestScaleZScoreNode(t *testing.T) {
	node, err := workflow.DefaultRegistry.Create("scale", "test-scale-z-1", nil)
	if err != nil {
		t.Fatalf("failed to create scale node: %v", err)
	}

	// Series [1,2,3,4,5] has mean=3, std≈1.414
	result, err := node.Execute(context.Background(), map[string]any{
		"series": []float64{1.0, 2.0, 3.0, 4.0, 5.0},
	}, map[string]any{
		"method": "zscore",
	})
	if err != nil {
		t.Fatalf("Execute() returned error: %v", err)
	}

	scaled, ok := result["scaled"].([]float64)
	if !ok {
		t.Fatal("scaled output must be []float64")
	}
	if len(scaled) != 5 {
		t.Fatalf("expected 5 values, got %d", len(scaled))
	}
}

// TestArithmeticNode verifies the arithmetic node operations.
func TestArithmeticNode(t *testing.T) {
	node, err := workflow.DefaultRegistry.Create("arithmetic", "test-arith-1", nil)
	if err != nil {
		t.Fatalf("failed to create arithmetic node: %v", err)
	}

	tests := []struct {
		name   string
		a, b   float64
		op     string
		expect float64
	}{
		{"add", 10, 5, "add", 15},
		{"sub", 10, 5, "sub", 5},
		{"mul", 10, 5, "mul", 50},
		{"div", 10, 5, "div", 2},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result, err := node.Execute(context.Background(), map[string]any{
				"a": tt.a,
				"b": tt.b,
			}, map[string]any{
				"op": tt.op,
			})
			if err != nil {
				t.Fatalf("Execute() returned error: %v", err)
			}
			got, ok := result["result"].(float64)
			if !ok {
				t.Fatal("result output must be float64")
			}
			if got != tt.expect {
				t.Errorf("result = %f, want %f", got, tt.expect)
			}
		})
	}
}

// TestArithmeticDivByZero verifies that division by zero returns an error.
func TestArithmeticDivByZero(t *testing.T) {
	node, err := workflow.DefaultRegistry.Create("arithmetic", "test-arith-dz", nil)
	if err != nil {
		t.Fatalf("failed to create arithmetic node: %v", err)
	}

	_, err = node.Execute(context.Background(), map[string]any{
		"a": 10.0,
		"b": 0.0,
	}, map[string]any{
		"op": "div",
	})
	if err == nil {
		t.Fatal("expected error for division by zero")
	}
}

// TestScheduleNode verifies the schedule node execution.
func TestScheduleNode(t *testing.T) {
	node, err := workflow.DefaultRegistry.Create("schedule", "test-sched-1", nil)
	if err != nil {
		t.Fatalf("failed to create schedule node: %v", err)
	}

	result, err := node.Execute(context.Background(), nil, map[string]any{
		"cron":     "0 9 * * 1-5",
		"timezone": "UTC",
	})
	if err != nil {
		t.Fatalf("Execute() returned error: %v", err)
	}

	nextRun, ok := result["next_run"].(string)
	if !ok {
		t.Fatal("next_run output must be a string")
	}
	if nextRun == "" {
		t.Fatal("next_run must not be empty")
	}

	triggerCount, ok := result["trigger_count"].(int)
	if !ok {
		t.Fatal("trigger_count output must be int")
	}
	if triggerCount != 0 {
		t.Errorf("expected trigger_count 0, got %d", triggerCount)
	}
}

// TestAlertNode verifies the alert node execution.
func TestAlertNode(t *testing.T) {
	node, err := workflow.DefaultRegistry.Create("alert", "test-alert-1", nil)
	if err != nil {
		t.Fatalf("failed to create alert node: %v", err)
	}

	// Test triggered = true
	result, err := node.Execute(context.Background(), map[string]any{
		"condition": true,
		"message":   "test alert",
	}, map[string]any{
		"level": "warning",
	})
	if err != nil {
		t.Fatalf("Execute() returned error: %v", err)
	}
	if result["triggered"] != true {
		t.Error("expected triggered = true")
	}
	alertID, ok := result["alert_id"].(string)
	if !ok || alertID == "" {
		t.Error("expected non-empty alert_id when triggered")
	}

	// Test triggered = false
	result, err = node.Execute(context.Background(), map[string]any{
		"condition": false,
		"message":   "no alert",
	}, map[string]any{
		"level": "info",
	})
	if err != nil {
		t.Fatalf("Execute() returned error: %v", err)
	}
	if result["triggered"] != false {
		t.Error("expected triggered = false")
	}
	if result["alert_id"] != "" {
		t.Error("expected empty alert_id when not triggered")
	}
}

// TestBranchNode verifies the branch node execution.
func TestBranchNode(t *testing.T) {
	node, err := workflow.DefaultRegistry.Create("branch", "test-branch-1", nil)
	if err != nil {
		t.Fatalf("failed to create branch node: %v", err)
	}

	// Test true branch
	result, err := node.Execute(context.Background(), map[string]any{
		"condition": true,
	}, nil)
	if err != nil {
		t.Fatalf("Execute() returned error: %v", err)
	}
	if result["true_branch"] != true {
		t.Error("expected true_branch = true")
	}
	if result["false_branch"] != false {
		t.Error("expected false_branch = false")
	}

	// Test false branch
	result, err = node.Execute(context.Background(), map[string]any{
		"condition": false,
	}, nil)
	if err != nil {
		t.Fatalf("Execute() returned error: %v", err)
	}
	if result["true_branch"] != false {
		t.Error("expected true_branch = false")
	}
	if result["false_branch"] != true {
		t.Error("expected false_branch = true")
	}
}

// TestMergeNode verifies the merge node execution.
func TestMergeNode(t *testing.T) {
	node, err := workflow.DefaultRegistry.Create("merge", "test-merge-1", nil)
	if err != nil {
		t.Fatalf("failed to create merge node: %v", err)
	}

	// Test branch_a takes priority
	result, err := node.Execute(context.Background(), map[string]any{
		"branch_a": "value_a",
		"branch_b": "value_b",
	}, nil)
	if err != nil {
		t.Fatalf("Execute() returned error: %v", err)
	}
	merged, ok := result["merged"].(string)
	if !ok || merged != "value_a" {
		t.Errorf("expected merged = 'value_a', got %v", result["merged"])
	}

	// Test fallback to branch_b
	result, err = node.Execute(context.Background(), map[string]any{
		"branch_b": "only_b",
	}, nil)
	if err != nil {
		t.Fatalf("Execute() returned error: %v", err)
	}
	merged, ok = result["merged"].(string)
	if !ok || merged != "only_b" {
		t.Errorf("expected merged = 'only_b', got %v", result["merged"])
	}
}

// TestModelCompareNodeEmpty verifies model_compare with empty input.
func TestModelCompareNodeEmpty(t *testing.T) {
	node, err := workflow.DefaultRegistry.Create("model_compare", "test-mc-empty", nil)
	if err != nil {
		t.Fatalf("failed to create model_compare node: %v", err)
	}

	result, err := node.Execute(context.Background(), map[string]any{
		"model_ids": []string{},
	}, nil)
	if err != nil {
		t.Fatalf("Execute() returned error: %v", err)
	}

	rankingsRaw, ok := result["rankings"]
	if !ok {
		t.Fatal("rankings output missing")
	}
	rankings, ok := rankingsRaw.([]ModelRank)
	if !ok {
		t.Fatalf("rankings must be []ModelRank, got %T", rankingsRaw)
	}
	if len(rankings) != 0 {
		t.Errorf("expected empty rankings, got %d", len(rankings))
	}
}

// TestScaleNodeFlatSeries verifies scale node with a flat (constant) series.
func TestScaleNodeFlatSeries(t *testing.T) {
	node, err := workflow.DefaultRegistry.Create("scale", "test-scale-flat", nil)
	if err != nil {
		t.Fatalf("failed to create scale node: %v", err)
	}

	result, err := node.Execute(context.Background(), map[string]any{
		"series": []float64{5.0, 5.0, 5.0},
	}, map[string]any{
		"method":    "minmax",
		"range_min": 0.0,
		"range_max": 1.0,
	})
	if err != nil {
		t.Fatalf("Execute() returned error: %v", err)
	}

	scaled, ok := result["scaled"].([]float64)
	if !ok {
		t.Fatal("scaled output must be []float64")
	}
	// Flat series should map to the midpoint (0.5)
	for i, v := range scaled {
		if v != 0.5 {
			t.Errorf("scaled[%d] = %f, want 0.5", i, v)
		}
	}
}
