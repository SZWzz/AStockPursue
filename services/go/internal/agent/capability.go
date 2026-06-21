// Package agent provides capability-based task dispatch for the Go-side agent.
// A Capability represents a concrete action (e.g. quote lookup, backtest)
// that can be matched to a user prompt by keyword scoring.
package agent

import "context"

// Capability is a named, keyword-matchable unit of work that the Go agent
// can execute directly without delegating to the Python LLM Agent layer.
type Capability interface {
	// Name returns a short unique identifier for this capability (e.g. "quote", "backtest").
	Name() string

	// Description returns a human-readable explanation of what this capability does.
	Description() string

	// Keywords returns the list of terms (Chinese or English) used to match
	// a user prompt against this capability via keywordScore.
	Keywords() []string

	// Execute runs the capability with the given parameters and returns a result map.
	Execute(ctx context.Context, params map[string]any) (map[string]any, error)
}
