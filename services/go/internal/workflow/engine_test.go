package workflow

import (
	"context"
	"testing"
)

// passThroughNode is a test node that passes an input value through,
// falling back to a "value" parameter when no input is connected.
type passThroughNode struct{ id string }

func (n *passThroughNode) ID() string                               { return n.id }
func (n *passThroughNode) NodeType() string                         { return "pass_through" }
func (n *passThroughNode) Category() string                         { return "test" }
func (n *passThroughNode) InputPorts() []PortDef                    { return []PortDef{{Name: "in", Type: PortAny}} }
func (n *passThroughNode) OutputPorts() []PortDef                   { return []PortDef{{Name: "out", Type: PortAny}} }
func (n *passThroughNode) ParamSchema() []ParamDef                  { return nil }
func (n *passThroughNode) Validate() error                          { return nil }

func (n *passThroughNode) Execute(ctx context.Context, inputs map[string]any, params map[string]any) (map[string]any, error) {
	val := params["value"]
	if v, ok := inputs["in"]; ok {
		val = v
	}
	return map[string]any{"out": val}, nil
}

func TestEngineLinearWorkflow(t *testing.T) {
	reg := NewRegistry()
	reg.Register("pass_through", func(id string, params map[string]any) (BaseNode, error) {
		return &passThroughNode{id: id}, nil
	})

	engine := NewEngine(reg)
	wf := &Workflow{
		Nodes: []NodeInstance{
			{ID: "a", NodeType: "pass_through", Params: map[string]any{"value": 1}},
			{ID: "b", NodeType: "pass_through"},
		},
		Edges: []Edge{
			{FromNode: "a", FromPort: "out", ToNode: "b", ToPort: "in"},
		},
	}

	result, err := engine.Execute(context.Background(), wf)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	// Node a should output its param value 1.
	if v, ok := result.NodeOutputs["a"]["out"]; !ok || v != 1 {
		t.Errorf("expected node a out=1, got %v (ok=%v)", v, ok)
	}

	// Node b should receive a's output and pass it through.
	if v, ok := result.NodeOutputs["b"]["out"]; !ok || v != 1 {
		t.Errorf("expected node b out=1, got %v (ok=%v)", v, ok)
	}
}

func TestEngineEmptyWorkflow(t *testing.T) {
	reg := NewRegistry()
	engine := NewEngine(reg)
	wf := &Workflow{}

	result, err := engine.Execute(context.Background(), wf)
	if err != nil {
		t.Fatalf("unexpected error on empty workflow: %v", err)
	}
	if len(result.NodeOutputs) != 0 {
		t.Errorf("expected empty outputs, got %d nodes", len(result.NodeOutputs))
	}
}

func TestEngineCycleError(t *testing.T) {
	reg := NewRegistry()
	engine := NewEngine(reg)
	wf := &Workflow{
		Nodes: []NodeInstance{
			{ID: "a", NodeType: "pass_through"},
			{ID: "b", NodeType: "pass_through"},
		},
		Edges: []Edge{
			{FromNode: "a", FromPort: "out", ToNode: "b", ToPort: "in"},
			{FromNode: "b", FromPort: "out", ToNode: "a", ToPort: "in"},
		},
	}

	_, err := engine.Execute(context.Background(), wf)
	if err == nil {
		t.Fatal("expected cycle error")
	}
}

func TestEngineUnknownNodeType(t *testing.T) {
	reg := NewRegistry()
	reg.Register("pass_through", func(id string, params map[string]any) (BaseNode, error) {
		return &passThroughNode{id: id}, nil
	})
	engine := NewEngine(reg)
	wf := &Workflow{
		Nodes: []NodeInstance{
			{ID: "a", NodeType: "pass_through"},
			{ID: "b", NodeType: "nonexistent"},
		},
		Edges: []Edge{
			{FromNode: "a", FromPort: "out", ToNode: "b", ToPort: "in"},
		},
	}

	_, err := engine.Execute(context.Background(), wf)
	if err == nil {
		t.Fatal("expected error for unknown node type")
	}
}
