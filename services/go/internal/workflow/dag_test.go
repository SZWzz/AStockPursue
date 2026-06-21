package workflow

import "testing"

func TestTopoSortLinear(t *testing.T) {
	edges := []Edge{
		{FromNode: "a", FromPort: "out", ToNode: "b", ToPort: "in"},
		{FromNode: "b", FromPort: "out", ToNode: "c", ToPort: "in"},
	}
	layers, err := TopoSort(edges)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(layers) != 3 {
		t.Errorf("expected 3 layers, got %d", len(layers))
	}
}

func TestTopoSortParallel(t *testing.T) {
	edges := []Edge{
		{FromNode: "a", FromPort: "out", ToNode: "b", ToPort: "in"},
		{FromNode: "a", FromPort: "out", ToNode: "c", ToPort: "in"},
	}
	layers, err := TopoSort(edges)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(layers) != 2 {
		t.Errorf("expected 2 layers (a → [b,c] in parallel), got %d", len(layers))
	}
	if len(layers[1]) != 2 {
		t.Errorf("expected 2 nodes in layer 1, got %d", len(layers[1]))
	}
}

func TestTopoSortCycleDetection(t *testing.T) {
	edges := []Edge{
		{FromNode: "a", FromPort: "out", ToNode: "b", ToPort: "in"},
		{FromNode: "b", FromPort: "out", ToNode: "a", ToPort: "in"},
	}
	_, err := TopoSort(edges)
	if err == nil {
		t.Error("expected cycle error")
	}
}
