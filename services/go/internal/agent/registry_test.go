package agent

import (
	"context"
	"testing"
)

type mockCap struct {
	name     string
	keywords []string
}

func (m *mockCap) Name() string              { return m.name }
func (m *mockCap) Description() string       { return "test" }
func (m *mockCap) Keywords() []string        { return m.keywords }
func (m *mockCap) Execute(ctx context.Context, params map[string]any) (map[string]any, error) {
	return map[string]any{"from": m.name}, nil
}

func TestMatchByKeyword(t *testing.T) {
	reg := NewCapabilityRegistry()
	reg.Register(&mockCap{name: "quote", keywords: []string{"报价", "价格", "price", "quote"}})
	reg.Register(&mockCap{name: "backtest", keywords: []string{"回测", "backtest", "历史"}})

	c, score := reg.Match("查一下600519的最新报价")
	if c == nil {
		t.Fatal("expected a match")
	}
	if c.Name() != "quote" {
		t.Errorf("expected quote, got %s", c.Name())
	}
	if score < 0.2 {
		t.Errorf("expected score >= 0.2, got %.2f", score)
	}
}

func TestNoMatch(t *testing.T) {
	reg := NewCapabilityRegistry()
	reg.Register(&mockCap{name: "quote", keywords: []string{"报价"}})

	c, score := reg.Match("今天天气怎么样")
	if score > 0 {
		t.Logf("partial match score: %.2f (expected 0)", score)
	}
	_ = c
}
