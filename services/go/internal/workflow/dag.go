package workflow

import "fmt"

// Edge represents a directed connection between two workflow nodes.
type Edge struct {
	FromNode string `json:"from_node"`
	FromPort string `json:"from_port"`
	ToNode   string `json:"to_node"`
	ToPort   string `json:"to_port"`
}

// NodeInstance represents a single node instance within a workflow DAG.
type NodeInstance struct {
	ID       string         `json:"id"`
	NodeType string         `json:"node_type"`
	Params   map[string]any `json:"params,omitempty"`
}

// Workflow is a complete DAG consisting of node instances and edges.
type Workflow struct {
	Nodes []NodeInstance `json:"nodes"`
	Edges []Edge         `json:"edges"`
}

// CycleError is returned by TopoSort when a cycle is detected in the DAG.
type CycleError struct {
	Node string
}

func (e *CycleError) Error() string {
	return fmt.Sprintf("workflow: cycle detected involving node %q", e.Node)
}

// TopoSort performs Kahn's algorithm to produce layers of nodes.
// Each layer contains nodes that can execute in parallel.
func TopoSort(edges []Edge) ([][]string, error) {
	inDegree := make(map[string]int)
	graph := make(map[string][]string)

	for _, e := range edges {
		inDegree[e.ToNode]++
		graph[e.FromNode] = append(graph[e.FromNode], e.ToNode)
		if _, ok := inDegree[e.FromNode]; !ok {
			inDegree[e.FromNode] = 0
		}
	}

	var queue []string
	for node, deg := range inDegree {
		if deg == 0 {
			queue = append(queue, node)
		}
	}

	var layers [][]string
	visited := 0
	for len(queue) > 0 {
		size := len(queue)
		layer := make([]string, 0, size)
		for i := 0; i < size; i++ {
			node := queue[0]
			queue = queue[1:]
			layer = append(layer, node)
			visited++
			for _, neighbor := range graph[node] {
				inDegree[neighbor]--
				if inDegree[neighbor] == 0 {
					queue = append(queue, neighbor)
				}
			}
		}
		layers = append(layers, layer)
	}

	if visited < len(inDegree) {
		return nil, &CycleError{Node: "unknown"}
	}

	return layers, nil
}
