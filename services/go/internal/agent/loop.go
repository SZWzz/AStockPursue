// Package agent provides capability-based task dispatch for the Go-side agent.
package agent

import (
	"context"
	"fmt"
)

// MatchThreshold is the minimum keyword score required for a capability
// to be selected over the LLM fallback. Capabilities scoring below this
// threshold are discarded and the prompt is forwarded to Python/LLM.
const MatchThreshold = 0.3

// AgentResult carries the outcome of a single AgentLoop.Run() invocation.
type AgentResult struct {
	// Source is either "go_capability" when a native capability matched and
	// executed successfully, or "python_llm" when the LLM fallback was used.
	Source string

	// Data is the result payload returned by either the capability or the
	// LLM fallback.
	Data map[string]any

	// Error is non-nil when the execution failed. A nil Error does not
	// guarantee that Source is populated — callers should check both.
	Error error
}

// AgentLoop is the top-level execution loop for the Go-side agent. It
// follows a capability-first strategy: given a user prompt, it tries to
// match a registered Go capability. If a match meets MatchThreshold the
// capability is executed directly; otherwise the prompt is forwarded to
// the Python LLM fallback function.
type AgentLoop struct {
	registry    *CapabilityRegistry
	llmFallback func(ctx context.Context, prompt string) (map[string]any, error)
}

// NewAgentLoop creates an AgentLoop with the given capability registry and
// LLM fallback function. The fallback may be nil, in which case Run returns
// an error when no capability matches.
func NewAgentLoop(
	registry *CapabilityRegistry,
	llmFallback func(ctx context.Context, prompt string) (map[string]any, error),
) *AgentLoop {
	return &AgentLoop{registry: registry, llmFallback: llmFallback}
}

// Run dispatches the user prompt. It first attempts to match and execute a
// registered Go capability. If the best match scores below MatchThreshold or
// the capability errors, it falls back to the Python LLM function. When both
// paths fail the returned AgentResult carries an appropriate error.
func (a *AgentLoop) Run(ctx context.Context, prompt string) *AgentResult {
	capability, score := a.registry.Match(prompt)

	if capability != nil && score >= MatchThreshold {
		result, err := capability.Execute(ctx, map[string]any{"prompt": prompt})
		if err == nil {
			return &AgentResult{Source: "go_capability", Data: result}
		}
	}

	if a.llmFallback != nil {
		result, err := a.llmFallback(ctx, prompt)
		if err != nil {
			return &AgentResult{Source: "python_llm", Error: fmt.Errorf("llm fallback: %w", err)}
		}
		return &AgentResult{Source: "python_llm", Data: result}
	}

	return &AgentResult{Error: fmt.Errorf("no capability matched and no LLM fallback available")}
}
