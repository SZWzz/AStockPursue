package workflow

import (
	"context"
	"testing"
)

type mockNode struct{ id string }

func (m *mockNode) ID() string                              { return m.id }
func (m *mockNode) NodeType() string                        { return "mock" }
func (m *mockNode) Category() string                        { return "test" }
func (m *mockNode) InputPorts() []PortDef                   { return nil }
func (m *mockNode) OutputPorts() []PortDef                  { return nil }
func (m *mockNode) ParamSchema() []ParamDef                 { return nil }
func (m *mockNode) Execute(ctx context.Context, inputs map[string]any, params map[string]any) (map[string]any, error) {
	return map[string]any{"ok": true}, nil
}
func (m *mockNode) Validate() error { return nil }

func TestRegistryRegisterAndCreate(t *testing.T) {
	r := NewRegistry()
	r.Register("mock", func(id string, params map[string]any) (BaseNode, error) {
		return &mockNode{id: id}, nil
	})

	node, err := r.Create("mock", "n1", nil)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if node.ID() != "n1" {
		t.Errorf("expected id n1, got %s", node.ID())
	}
	if node.NodeType() != "mock" {
		t.Errorf("expected type mock, got %s", node.NodeType())
	}
}

func TestRegistryCreateUnknown(t *testing.T) {
	r := NewRegistry()
	_, err := r.Create("nonexistent", "n1", nil)
	if err == nil {
		t.Error("expected error for unknown node type")
	}
}

func TestRegistryListAll(t *testing.T) {
	r := NewRegistry()
	r.Register("a", func(id string, params map[string]any) (BaseNode, error) {
		return &mockNode{id: id}, nil
	})
	r.Register("b", func(id string, params map[string]any) (BaseNode, error) {
		return &mockNode{id: id}, nil
	})

	all := r.ListAll()
	if len(all) != 2 {
		t.Errorf("expected 2, got %d", len(all))
	}
}
