package nodes

import (
	"testing"

	"github.com/astockpursue/go-core/internal/workflow"
)

// TestSignalNodesRegistered verifies that all 8 signal and indicator node
// types are registered in the DefaultRegistry and can be instantiated
// with the correct NodeType and Category.
func TestSignalNodesRegistered(t *testing.T) {
	tests := []struct {
		nodeType string
		category string
	}{
		// Signal nodes
		{nodeType: "cross_over", category: "signal"},
		{nodeType: "cross_signal", category: "signal"},
		{nodeType: "entry_signal", category: "signal"},
		// Indicator nodes
		{nodeType: "bollinger", category: "indicator"},
		{nodeType: "sma", category: "indicator"},
		{nodeType: "ema", category: "indicator"},
		{nodeType: "std_dev", category: "indicator"},
		{nodeType: "delta", category: "indicator"},
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

			// Basic contract checks
			if len(node.InputPorts()) == 0 {
				t.Error("InputPorts() returned empty")
			}
			if len(node.OutputPorts()) == 0 {
				t.Error("OutputPorts() returned empty")
			}

			if err := node.Validate(); err != nil {
				t.Errorf("Validate() returned error: %v", err)
			}
		})
	}
}
