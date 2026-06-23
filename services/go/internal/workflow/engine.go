package workflow

import (
	"context"
	"fmt"
	"sync"
)

// WorkflowResult holds the outputs produced by every node in the workflow
// after a successful execution, or the error if execution failed.
type WorkflowResult struct {
	NodeOutputs map[string]NodeOutputs
	Error       error
}

// Engine drives the execution of a Workflow DAG.
//
// It performs a topological sort of the workflow edges to determine layers,
// then executes each layer's nodes concurrently via goroutines.  The outputs
// of a layer are made available as inputs to downstream layers, mirroring the
// data-flow edges defined in the Workflow.
type Engine struct {
	registry *NodeRegistry
}

// NewEngine creates an Engine backed by the given NodeRegistry.
//
// The registry is used to instantiate node types during execution.
func NewEngine(registry *NodeRegistry) *Engine {
	return &Engine{registry: registry}
}

// Execute runs the workflow to completion, executing each topological layer
// in order and running all nodes within a layer concurrently.
//
// Steps:
//  1. TopoSort the workflow edges into parallel layers.
//  2. For each layer, spawn a goroutine per node.
//  3. Each goroutine creates the node via the registry, gathers inputs from
//     upstream node outputs, calls Execute, and stores the result.
//  4. Wait for the layer to finish; on any error return immediately.
//  5. Continue to the next layer.
func (e *Engine) Execute(ctx context.Context, wf *Workflow) (*WorkflowResult, error) {
	layers, err := TopoSort(wf.Edges)
	if err != nil {
		return nil, err
	}

	nodeIndex := make(map[string]NodeInstance)
	for _, n := range wf.Nodes {
		nodeIndex[n.ID] = n
	}

	// outputs maps node ID → port name → value.
	outputs := make(map[string]NodeOutputs)
	var mu sync.Mutex

	for _, layer := range layers {
		var wg sync.WaitGroup
		errCh := make(chan error, len(layer))

		for _, nodeID := range layer {
			inst, ok := nodeIndex[nodeID]
			if !ok {
				continue
			}

			wg.Add(1)
			go func(id string, inst NodeInstance) {
				defer wg.Done()

				node, err := e.registry.Create(inst.NodeType, id, inst.Params)
				if err != nil {
					errCh <- fmt.Errorf("node %s: create %s: %w", id, inst.NodeType, err)
					return
				}

				// Gather inputs from upstream nodes via the workflow edges.
				inputs := make(NodeParams)
				for _, edge := range wf.Edges {
					if edge.ToNode == id {
						mu.Lock()
						if upOutputs, ok := outputs[edge.FromNode]; ok {
							if val, ok := upOutputs[edge.FromPort]; ok {
								inputs[edge.ToPort] = val
							}
						}
						mu.Unlock()
					}
				}

				result, err := node.Execute(ctx, inputs, inst.Params)
				if err != nil {
					errCh <- fmt.Errorf("node %s execute: %w", id, err)
					return
				}

				mu.Lock()
				outputs[id] = result
				mu.Unlock()
			}(nodeID, inst)
		}

		wg.Wait()
		close(errCh)

		if err := <-errCh; err != nil {
			return &WorkflowResult{NodeOutputs: outputs, Error: err}, err
		}
	}

	return &WorkflowResult{NodeOutputs: outputs}, nil
}
