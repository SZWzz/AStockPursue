package agent

import (
	"strings"
	"sync"
)

// CapabilityRegistry holds a set of registered Capabilities and provides
// keyword-based matching against a user prompt.
//
// All exported methods are safe for concurrent use.
type CapabilityRegistry struct {
	mu           sync.RWMutex
	capabilities []Capability
}

// NewCapabilityRegistry creates an empty CapabilityRegistry.
func NewCapabilityRegistry() *CapabilityRegistry {
	return &CapabilityRegistry{}
}

// Register adds a Capability to the registry. It is safe for concurrent calls.
func (r *CapabilityRegistry) Register(c Capability) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.capabilities = append(r.capabilities, c)
}

// Match scans all registered capabilities and returns the best match together
// with its keyword score. When no capability scores above zero, the returned
// Capability is nil and score is 0.
func (r *CapabilityRegistry) Match(prompt string) (Capability, float64) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	promptLower := strings.ToLower(prompt)
	var best Capability
	var bestScore float64

	for _, c := range r.capabilities {
		score := keywordScore(promptLower, c.Keywords())
		if score > bestScore {
			bestScore = score
			best = c
		}
	}
	return best, bestScore
}

// keywordScore returns the fraction of keywords that appear as substrings
// in the (already-lowercased) prompt. Returns 0 when keywords is empty.
func keywordScore(prompt string, keywords []string) float64 {
	if len(keywords) == 0 {
		return 0
	}
	matched := 0
	for _, kw := range keywords {
		if strings.Contains(prompt, kw) {
			matched++
		}
	}
	return float64(matched) / float64(len(keywords))
}
