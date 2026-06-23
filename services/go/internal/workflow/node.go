package workflow

import "context"

// NodeParams is a named type alias for the configuration parameters map
// passed to a node's Execute method. It is map[string]any under the hood
// and is fully interchangeable with that type. The alias exists only for
// readability and to provide a migration anchor for a future structured
// configuration type.
type NodeParams = map[string]any

// NodeOutputs is a named type alias for the outputs map returned by a
// node's Execute method, keyed by output port name. Like NodeParams it is
// map[string]any and fully interchangeable; the alias is for readability
// and future migration.
type NodeOutputs = map[string]any

// PortType represents the type of data a port accepts or produces.
type PortType string

const (
	// PortOHLCV represents OHLCV bar data (open, high, low, close, volume).
	PortOHLCV PortType = "ohlcv"
	// PortSignal represents trading signal data (buy/sell/hold weights).
	PortSignal PortType = "signal"
	// PortSeries represents a generic time-series of values.
	PortSeries PortType = "series"
	// PortParams represents configuration parameters passed into the node.
	PortParams PortType = "params"
	// PortAny represents any data type (dynamic/loose coupling).
	PortAny PortType = "any"
)

// PortDef describes a single input or output port on a workflow node.
type PortDef struct {
	Name     string   `json:"name"`
	Type     PortType `json:"type"`
	Required bool     `json:"required"`
}

// ParamDef describes a single user-configurable parameter for a node.
type ParamDef struct {
	Name        string `json:"name"`
	Type        string `json:"type"` // "int","float","string","bool","string_array"
	Default     any    `json:"default,omitempty"`
	Description string `json:"description,omitempty"`
}

// BaseNode is the interface that every workflow node must implement.
//
// Each node declares its identity (ID, NodeType, Category), its data-flow
// contract (InputPorts, OutputPorts), its configurable parameters
// (ParamSchema), and its execution behaviour (Execute). Validate is called
// before the workflow is run to catch misconfiguration early.
type BaseNode interface {
	// ID returns the unique identifier of this node instance within the workflow.
	ID() string

	// NodeType returns the type name (e.g. "market_data", "factor", "signal").
	NodeType() string

	// Category returns the high-level grouping for UI/UX (e.g. "Data", "Analysis").
	Category() string

	// InputPorts returns the list of input ports this node expects.
	InputPorts() []PortDef

	// OutputPorts returns the list of output ports this node produces.
	OutputPorts() []PortDef

	// ParamSchema returns the list of user-configurable parameters for this node.
	ParamSchema() []ParamDef

	// Execute runs the node's logic with the given inputs and parameters,
	// returning the output values keyed by port name.
	Execute(ctx context.Context, inputs NodeParams, params NodeParams) (NodeOutputs, error)

	// Validate checks that the node is correctly configured before execution.
	Validate() error
}
