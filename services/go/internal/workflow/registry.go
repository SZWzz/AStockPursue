package workflow

import (
	"fmt"
	"sync"
)

// NodeConstructor is a factory function that creates a new node instance.
// It receives the node instance ID and configuration parameters, and returns
// a fully-initialised BaseNode or an error if construction fails.
type NodeConstructor func(id string, params map[string]any) (BaseNode, error)

// NodeMeta holds metadata about a registered node type for discovery and
// UI rendering.
type NodeMeta struct {
	NodeType string `json:"node_type"`
	Category string `json:"category"`
}

// DefaultRegistry is the package-level registry used by node packages to
// self-register via their init() functions.  It is initialised at startup
// and consumed by the workflow Engine.
var DefaultRegistry = NewRegistry()

// NodeRegistry provides thread-safe registration and creation of workflow
// nodes by type name.  Constructors are registered once at startup and
// queried during workflow deserialisation or interactive node creation.
type NodeRegistry struct {
	mu           sync.RWMutex
	constructors map[string]NodeConstructor
	categories   map[string]string
}

// NewRegistry returns an initialised, empty NodeRegistry.
func NewRegistry() *NodeRegistry {
	return &NodeRegistry{
		constructors: make(map[string]NodeConstructor),
		categories:   make(map[string]string),
	}
}

// Register associates a node type with its constructor.  The category
// defaults to the empty string; call RegisterWithCategory to set one.
func (r *NodeRegistry) Register(nodeType string, ctor NodeConstructor) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.constructors[nodeType] = ctor
}

// RegisterWithCategory is like Register but also records a category for
// the node type, used by ListAll for UI grouping.
func (r *NodeRegistry) RegisterWithCategory(nodeType string, ctor NodeConstructor, category string) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.constructors[nodeType] = ctor
	r.categories[nodeType] = category
}

// Create instantiates a node of the given type by calling its registered
// constructor.  It returns an error if the type is unknown.
func (r *NodeRegistry) Create(nodeType, id string, params map[string]any) (BaseNode, error) {
	r.mu.RLock()
	ctor, ok := r.constructors[nodeType]
	r.mu.RUnlock()
	if !ok {
		return nil, fmt.Errorf("unknown node type: %q", nodeType)
	}
	return ctor(id, params)
}

// ListAll returns metadata for every registered node type.
func (r *NodeRegistry) ListAll() []NodeMeta {
	r.mu.RLock()
	defer r.mu.RUnlock()
	result := make([]NodeMeta, 0, len(r.constructors))
	for nodeType := range r.constructors {
		result = append(result, NodeMeta{
			NodeType: nodeType,
			Category: r.categories[nodeType],
		})
	}
	return result
}
