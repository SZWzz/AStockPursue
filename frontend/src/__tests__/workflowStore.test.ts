import { describe, it, expect, beforeEach, vi } from "vitest";
import type { NodeDefinition } from "@/workflow/types/workflow";

// Mock @xyflow/react — the store imports it for edge/node change helpers
vi.mock("@xyflow/react", () => ({
  addEdge: (edge: any, edges: any[]) => [...edges, edge],
  applyEdgeChanges: (_changes: any[], edges: any[]) => edges,
  applyNodeChanges: (_changes: any[], nodes: any[]) => nodes,
}));

// Sample node definitions for testing
const SAMPLE_DEFS: NodeDefinition[] = [
  {
    node_type: "column_extract",
    category: "data",
    label: "Column Extract",
    description: "Extract OHLCV columns",
    icon: "Database",
    inputs: [{ name: "ohlcv_data", port_type: "df_ohlcv", direction: "input", required: true, description: "OHLCV data" }],
    outputs: [{ name: "series", port_type: "df_factor", direction: "output", required: true, description: "Series" }],
    config_schema: { column: { type: "string", default: "close" } },
    resource_profile: "cpu_bound",
  },
  {
    node_type: "ma",
    category: "alpha",
    label: "MA",
    description: "Moving Average",
    icon: "TrendingUp",
    inputs: [{ name: "series", port_type: "df_factor", direction: "input", required: true, description: "Input factor" }],
    outputs: [{ name: "ma", port_type: "df_factor", direction: "output", required: true, description: "MA output" }],
    config_schema: { window: { type: "integer", default: 20 } },
    resource_profile: "cpu_bound",
  },
  {
    node_type: "rank_select",
    category: "strategy",
    label: "Rank Select",
    description: "Select top N",
    icon: "Target",
    inputs: [{ name: "factor", port_type: "df_factor", direction: "input", required: true, description: "Factor" }],
    outputs: [{ name: "signal", port_type: "signal", direction: "output", required: true, description: "Signal" }],
    config_schema: { top_n: { type: "integer", default: 10 } },
    resource_profile: "cpu_bound",
  },
];

describe("useWorkflowStore — pure logic", () => {
  beforeEach(async () => {
    const { useWorkflowStore } = await import("@/workflow/store/workflowStore");
    useWorkflowStore.getState().reset();
    // Inject sample definitions
    useWorkflowStore.setState({ nodeDefinitions: SAMPLE_DEFS });
  });

  it("starts with empty canvas", async () => {
    const { useWorkflowStore } = await import("@/workflow/store/workflowStore");
    const state = useWorkflowStore.getState();
    expect(state.nodes).toEqual([]);
    expect(state.edges).toEqual([]);
    expect(state.runStatus).toBe("idle");
    expect(state.isDirty).toBe(false);
  });

  it("addNode creates a node with correct type and position", async () => {
    const { useWorkflowStore } = await import("@/workflow/store/workflowStore");
    useWorkflowStore.getState().addNode("ma", { x: 100, y: 200 });

    const state = useWorkflowStore.getState();
    expect(state.nodes).toHaveLength(1);
    expect(state.nodes[0].data.node_type).toBe("ma");
    expect(state.nodes[0].position).toEqual({ x: 100, y: 200 });
    expect(state.isDirty).toBe(true);
  });

  it("addNode does nothing for unknown node type", async () => {
    const { useWorkflowStore } = await import("@/workflow/store/workflowStore");
    useWorkflowStore.getState().addNode("nonexistent", { x: 0, y: 0 });

    const state = useWorkflowStore.getState();
    expect(state.nodes).toHaveLength(0);
  });

  it("removeNode clears node and related edges", async () => {
    const { useWorkflowStore } = await import("@/workflow/store/workflowStore");
    const store = useWorkflowStore.getState();

    store.addNode("ma", { x: 100, y: 0 });
    store.addNode("rank_select", { x: 300, y: 0 });

    const nodeId = useWorkflowStore.getState().nodes[0].id;
    store.removeNode(nodeId);

    const state = useWorkflowStore.getState();
    expect(state.nodes).toHaveLength(1);
    expect(state.nodes[0].data.node_type).toBe("rank_select");
  });

  it("selectNode sets/clears selectedNodeId", async () => {
    const { useWorkflowStore } = await import("@/workflow/store/workflowStore");
    const store = useWorkflowStore.getState();

    store.addNode("ma", { x: 0, y: 0 });
    const nodeId = useWorkflowStore.getState().nodes[0].id;

    store.selectNode(nodeId);
    expect(useWorkflowStore.getState().selectedNodeId).toBe(nodeId);

    store.selectNode(null);
    expect(useWorkflowStore.getState().selectedNodeId).toBeNull();
  });

  it("updateNodeConfig updates config on existing node", async () => {
    const { useWorkflowStore } = await import("@/workflow/store/workflowStore");
    const store = useWorkflowStore.getState();

    store.addNode("ma", { x: 0, y: 0 });
    const nodeId = useWorkflowStore.getState().nodes[0].id;

    store.updateNodeConfig(nodeId, { window: 50 });
    const node = useWorkflowStore.getState().nodes[0];
    expect(node.data.config).toEqual({ window: 50 });
    expect(useWorkflowStore.getState().isDirty).toBe(true);
  });

  it("validateWorkflow detects missing required inputs", async () => {
    const { useWorkflowStore } = await import("@/workflow/store/workflowStore");
    const store = useWorkflowStore.getState();

    // Add a node with required input but no edge
    store.addNode("ma", { x: 0, y: 0 });

    const errors = store.validateWorkflow();
    expect(errors.length).toBeGreaterThan(0);
    expect(errors[0].message).toContain("Required input");
  });

  it("setViewport updates viewport state", async () => {
    const { useWorkflowStore } = await import("@/workflow/store/workflowStore");
    const store = useWorkflowStore.getState();

    store.setViewport({ x: 50, y: 100, zoom: 1.5 });
    expect(useWorkflowStore.getState().viewport).toEqual({ x: 50, y: 100, zoom: 1.5 });
  });

  it("setWorkflowName marks dirty", async () => {
    const { useWorkflowStore } = await import("@/workflow/store/workflowStore");
    const store = useWorkflowStore.getState();

    store.setWorkflowName("My Strategy");
    expect(useWorkflowStore.getState().workflowName).toBe("My Strategy");
    expect(useWorkflowStore.getState().isDirty).toBe(true);
  });

  it("addLog appends to execution log", async () => {
    const { useWorkflowStore } = await import("@/workflow/store/workflowStore");
    const store = useWorkflowStore.getState();

    store.addLog("node_1", "Processing started", "info");
    store.addLog("node_1", "Done", "success");

    expect(useWorkflowStore.getState().executionLog).toHaveLength(2);
    expect(useWorkflowStore.getState().executionLog[0]).toEqual({
      nodeId: "node_1",
      message: "Processing started",
      level: "info",
    });
  });

  it("onConnect rejects connection to unknown nodes", async () => {
    const { useWorkflowStore } = await import("@/workflow/store/workflowStore");
    const store = useWorkflowStore.getState();

    const result = store.onConnect({
      source: "unknown_source",
      target: "unknown_target",
      sourceHandle: null,
      targetHandle: null,
    } as any);
    expect(result.success).toBe(false);
  });

  it("onConnect allows valid type-compatible connection", async () => {
    const { useWorkflowStore } = await import("@/workflow/store/workflowStore");
    const store = useWorkflowStore.getState();

    store.addNode("column_extract", { x: 0, y: 0 });
    store.addNode("ma", { x: 200, y: 0 });

    const state = useWorkflowStore.getState();
    const sourceNode = state.nodes.find((n) => n.data.node_type === "column_extract")!;
    const targetNode = state.nodes.find((n) => n.data.node_type === "ma")!;

    const result = store.onConnect({
      source: sourceNode.id,
      target: targetNode.id,
      sourceHandle: null,
      targetHandle: null,
    } as any);
    expect(result.success).toBe(true);
    expect(useWorkflowStore.getState().edges).toHaveLength(1);
    expect(useWorkflowStore.getState().isDirty).toBe(true);
  });

  it("reset clears everything", async () => {
    const { useWorkflowStore } = await import("@/workflow/store/workflowStore");
    const store = useWorkflowStore.getState();

    store.addNode("ma", { x: 0, y: 0 });
    store.reset();

    const state = useWorkflowStore.getState();
    expect(state.nodes).toEqual([]);
    expect(state.edges).toEqual([]);
    expect(state.workflowId).toBeNull();
    expect(state.isDirty).toBe(false);
  });

  it("removeNode clears selectedNodeId if selected node is removed", async () => {
    const { useWorkflowStore } = await import("@/workflow/store/workflowStore");
    const store = useWorkflowStore.getState();

    store.addNode("ma", { x: 0, y: 0 });
    const nodeId = useWorkflowStore.getState().nodes[0].id;
    store.selectNode(nodeId);
    store.removeNode(nodeId);

    expect(useWorkflowStore.getState().selectedNodeId).toBeNull();
  });
});
