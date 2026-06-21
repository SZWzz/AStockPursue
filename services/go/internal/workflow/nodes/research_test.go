package nodes

import (
	"testing"

	"github.com/astockpursue/go-core/internal/workflow"
)

// TestFinancialsNodeType verifies that a financials node created via the
// default registry returns the correct NodeType().
func TestFinancialsNodeType(t *testing.T) {
	node, err := workflow.DefaultRegistry.Create("financials", "test-fin-1", nil)
	if err != nil {
		t.Fatalf("failed to create financials node: %v", err)
	}

	if got := node.NodeType(); got != "financials" {
		t.Errorf("expected NodeType %q, got %q", "financials", got)
	}

	if got := node.ID(); got != "test-fin-1" {
		t.Errorf("expected ID %q, got %q", "test-fin-1", got)
	}

	if got := node.Category(); got != "research" {
		t.Errorf("expected Category %q, got %q", "research", got)
	}
}

// TestGeopoliticsNodeType verifies that a geopolitics node created via the
// default registry returns the correct NodeType().
func TestGeopoliticsNodeType(t *testing.T) {
	node, err := workflow.DefaultRegistry.Create("geopolitics", "test-geo-1", nil)
	if err != nil {
		t.Fatalf("failed to create geopolitics node: %v", err)
	}

	if got := node.NodeType(); got != "geopolitics" {
		t.Errorf("expected NodeType %q, got %q", "geopolitics", got)
	}

	if got := node.ID(); got != "test-geo-1" {
		t.Errorf("expected ID %q, got %q", "test-geo-1", got)
	}

	if got := node.Category(); got != "research" {
		t.Errorf("expected Category %q, got %q", "research", got)
	}
}

// TestResearchNodes verifies that all 7 research node types are
// registered in the DefaultRegistry and can be instantiated successfully.
func TestResearchNodes(t *testing.T) {
	expectedTypes := []string{
		"financials",
		"geopolitics",
		"northbound",
		"news",
		"sentiment",
		"analyst_estimates",
		"insider_trades",
	}

	for i, nodeType := range expectedTypes {
		id := "test-" + nodeType + "-1"
		node, err := workflow.DefaultRegistry.Create(nodeType, id, nil)
		if err != nil {
			t.Errorf("[%d] type %q: failed to create: %v", i, nodeType, err)
			continue
		}

		if got := node.NodeType(); got != nodeType {
			t.Errorf("[%d] type %q: NodeType() returned %q", i, nodeType, got)
		}

		if got := node.Category(); got != "research" {
			t.Errorf("[%d] type %q: Category() returned %q, want %q", i, nodeType, got, "research")
		}

		// Verify input ports include "symbol"
		hasSymbol := false
		for _, port := range node.InputPorts() {
			if port.Name == "symbol" {
				hasSymbol = true
				break
			}
		}
		if !hasSymbol {
			t.Errorf("[%d] type %q: InputPorts() missing \"symbol\" port", i, nodeType)
		}

		// Verify output ports include "result"
		hasResult := false
		for _, port := range node.OutputPorts() {
			if port.Name == "result" {
				hasResult = true
				break
			}
		}
		if !hasResult {
			t.Errorf("[%d] type %q: OutputPorts() missing \"result\" port", i, nodeType)
		}

		// Validate should return nil
		if err := node.Validate(); err != nil {
			t.Errorf("[%d] type %q: Validate() returned error: %v", i, nodeType, err)
		}
	}
}
