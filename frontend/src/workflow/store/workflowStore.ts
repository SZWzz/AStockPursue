/**
 * Zustand store for workflow canvas state and execution management.
 *
 * Manages: nodes, edges, viewport, run state, and all CRUD + execution actions.
 * Port-compatibility validation runs client-side for instant feedback;
 * the server re-validates on save/run.
 */

import { create } from "zustand";
import {
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
  Connection,
  Edge,
  EdgeChange,
  Node,
  NodeChange,
  XYPosition,
} from "@xyflow/react";
import { api } from "@/lib/api";
import type {
  ConnectResult,
  NodeDefinition,
  NodeRunResult,
  WorkflowEdgeData,
  WorkflowNodeData,
} from "@/workflow/types/workflow";
import { isCompatible } from "@/workflow/types/workflow";

type Viewport = { x: number; y: number; zoom: number };

// ── Store shape ─────────────────────────────────────────────────────────────

interface WorkflowState {
  // Canvas
  projectId: string | null;
  workflowId: string | null;
  workflowName: string;
  nodes: Node[];
  edges: Edge[];
  viewport: Viewport;

  // Execution
  runId: string | null;
  runStatus: "idle" | "running" | "completed" | "error";
  nodeResults: Record<string, NodeRunResult>;
  executionLog: { nodeId: string; message: string; level: "info" | "error" | "success" }[];

  // UI
  selectedNodeId: string | null;
  isDirty: boolean;
  isSaving: boolean;

  // Node types (fetched from server)
  nodeDefinitions: NodeDefinition[];

  // ── Canvas actions ──────────────────────────────────────────────────────

  onNodesChange: (changes: NodeChange[]) => void;
  onEdgesChange: (changes: EdgeChange[]) => void;
  onConnect: (connection: Connection) => ConnectResult;
  addNode: (nodeType: string, position: XYPosition) => void;
  removeNode: (id: string) => void;
  updateNodeConfig: (id: string, config: Record<string, unknown>) => void;
  selectNode: (id: string | null) => void;
  setViewport: (vp: Viewport) => void;

  // ── Persistence ─────────────────────────────────────────────────────────

  saveWorkflow: () => Promise<void>;
  loadWorkflow: (id: string) => Promise<void>;
  loadProjectWorkflows: (projectId: string) => Promise<void>;
  setProjectId: (id: string) => void;
  setWorkflowName: (name: string) => void;

  // ── Execution ───────────────────────────────────────────────────────────

  runWorkflow: (targetNodeId?: string) => Promise<void>;
  runSingleNode: (nodeId: string) => Promise<void>;
  stopRun: () => Promise<void>;
  addLog: (nodeId: string, message: string, level?: "info" | "error" | "success") => void;

  // ── Validation ──────────────────────────────────────────────────────────

  validateWorkflow: () => { nodeId?: string; edgeId?: string; message: string }[];
  getCompatibleNodes: (portType: string) => NodeDefinition[];

  // ── Initialisation ──────────────────────────────────────────────────────

  fetchNodeDefinitions: () => Promise<void>;
  reset: () => void;
}

// ── Helpers ─────────────────────────────────────────────────────────────────

let _nodeIdCounter = 0;
function nextNodeId(): string {
  _nodeIdCounter += 1;
  return `node_${Date.now()}_${_nodeIdCounter}`;
}

function edgeId(source: string, target: string): string {
  return `e_${source}_${target}`;
}

// ── Initial state factory ────────────────────────────────────────────────────

const initialViewport: Viewport = { x: 0, y: 0, zoom: 1 };

// ── Store ────────────────────────────────────────────────────────────────────

export const useWorkflowStore = create<WorkflowState>((set, get) => ({
  projectId: null,
  workflowId: null,
  workflowName: "Untitled Workflow",
  nodes: [],
  edges: [],
  viewport: initialViewport,

  runId: null,
  runStatus: "idle",
  nodeResults: {},
  executionLog: [],

  selectedNodeId: null,
  isDirty: false,
  isSaving: false,

  nodeDefinitions: [],

  // ── Canvas actions ──────────────────────────────────────────────────────

  onNodesChange: (changes: NodeChange[]) => {
    set({ nodes: applyNodeChanges(changes, get().nodes), isDirty: true });
  },

  onEdgesChange: (changes: EdgeChange[]) => {
    set({ edges: applyEdgeChanges(changes, get().edges), isDirty: true });
  },

  onConnect: (connection: Connection): ConnectResult => {
    const { nodes, nodeDefinitions } = get();
    if (!connection.source || !connection.target) return { success: false, error: "Invalid connection" };
    if (!connection.sourceHandle || !connection.targetHandle) return { success: false, error: "Missing port handles" };

    // Find port types
    const sourceNode = nodes.find((n) => n.id === connection.source);
    const targetNode = nodes.find((n) => n.id === connection.target);
    if (!sourceNode || !targetNode) return { success: false, error: "Node not found" };

    const sourceDef = nodeDefinitions.find((d) => d.node_type === sourceNode.data?.node_type);
    const targetDef = nodeDefinitions.find((d) => d.node_type === targetNode.data?.node_type);
    if (!sourceDef || !targetDef) return { success: false, error: "Node type not found" };

    const sourcePort = sourceDef.outputs.find((p) => p.name === connection.sourceHandle);
    const targetPort = targetDef.inputs.find((p) => p.name === connection.targetHandle);
    if (!sourcePort || !targetPort) return { success: false, error: "Port not found" };

    // Type compatibility check
    if (!isCompatible(sourcePort.port_type, targetPort.port_type)) {
      return {
        success: false,
        error: `Type mismatch: ${sourcePort.port_type} → ${targetPort.port_type}`,
      };
    }

    // Check for duplicate connection to the same input port
    const existingConnection = get().edges.find(
      (e) => e.target === connection.target && e.targetHandle === connection.targetHandle
    );
    if (existingConnection) {
      return { success: false, error: "Input port already connected" };
    }

    const edge: Edge = {
      id: edgeId(connection.source, connection.target),
      source: connection.source,
      target: connection.target,
      sourceHandle: connection.sourceHandle,
      targetHandle: connection.targetHandle,
      data: {
        source_port: connection.sourceHandle,
        target_port: connection.targetHandle,
      } as unknown as Record<string, unknown>,
    };

    set({ edges: addEdge(edge, get().edges), isDirty: true });
    return { success: true };
  },

  addNode: (nodeType: string, position: XYPosition) => {
    const def = get().nodeDefinitions.find((d) => d.node_type === nodeType);
    if (!def) return;

    const newNode: Node = {
      id: nextNodeId(),
      type: "workflowNode", // Custom node component name
      position,
      data: {
        id: "", // filled below
        node_type: nodeType,
        label: def.label,
        position: position,
        config: {},
        status: "pending",
        error_message: "",
        duration_ms: 0,
        definition: def,
      },
    };
    newNode.data.id = newNode.id;

    set({ nodes: [...get().nodes, newNode], isDirty: true });
  },

  removeNode: (id: string) => {
    set({
      nodes: get().nodes.filter((n) => n.id !== id),
      edges: get().edges.filter((e) => e.source !== id && e.target !== id),
      isDirty: true,
      selectedNodeId: get().selectedNodeId === id ? null : get().selectedNodeId,
    });
  },

  updateNodeConfig: (id: string, config: Record<string, unknown>) => {
    set({
      nodes: get().nodes.map((n) =>
        n.id === id ? { ...n, data: { ...n.data, config } } : n
      ),
      isDirty: true,
    });
  },

  selectNode: (id: string | null) => set({ selectedNodeId: id }),

  setViewport: (vp: Viewport) => set({ viewport: vp }),

  // ── Persistence ─────────────────────────────────────────────────────────

  saveWorkflow: async () => {
    const { workflowId, workflowName, nodes, edges, viewport } = get();
    set({ isSaving: true });
    try {
      if (!workflowId) {
        // Create new workflow first
        throw new Error("No workflow to save — create one first");
      }

      const body = {
        name: workflowName,
        nodes: nodes.map((n) => ({
          id: n.id,
          node_type: n.data.node_type,
          label: n.data.label,
          position: n.position,
          config: n.data.config,
        })),
        edges: edges.map((e) => ({
          id: e.id,
          source: e.source,
          source_port: (e.data as unknown as WorkflowEdgeData)?.source_port || e.sourceHandle || "",
          target: e.target,
          target_port: (e.data as unknown as WorkflowEdgeData)?.target_port || e.targetHandle || "",
        })),
        viewport,
      };

      await api.saveWorkflow(workflowId, body);
      set({ isDirty: false });
    } catch (e) {
      console.error("Failed to save workflow:", e);
      throw e;
    } finally {
      set({ isSaving: false });
    }
  },

  loadWorkflow: async (id: string) => {
    const data = await api.getWorkflow(id);
    if (!data) return;

    const defs = get().nodeDefinitions;

    set({
      workflowId: data.id,
      projectId: data.project_id,
      workflowName: data.name,
      viewport: data.viewport || initialViewport,
      nodes: (data.nodes || []).map((n: WorkflowNodeData) => {
        const def = defs.find((d) => d.node_type === n.node_type);
        return {
          id: n.id,
          type: "workflowNode",
          position: n.position,
          data: { ...n, definition: def },
        } as Node;
      }),
      edges: (data.edges || []).map((e: WorkflowEdgeData) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        sourceHandle: e.source_port,
        targetHandle: e.target_port,
        data: e as unknown as Record<string, unknown>,
      } as Edge)),
      isDirty: false,
    });
  },

  loadProjectWorkflows: async (_projectId: string) => {
    // Project-level workflows list — for project dashboard
    // Implemented via API call in the WorkflowPage component
  },

  setProjectId: (id: string) => set({ projectId: id }),
  setWorkflowName: (name: string) => set({ workflowName: name, isDirty: true }),

  // ── Execution ───────────────────────────────────────────────────────────

  runWorkflow: async (targetNodeId?: string) => {
    const { workflowId, isDirty } = get();
    if (!workflowId) return;

    // Auto-save if dirty to prevent running stale workflow
    if (isDirty) {
      try {
        await get().saveWorkflow();
      } catch (e) {
        console.warn("Auto-save before run failed:", e);
        // Continue anyway — user was warned by isDirty indicator
      }
    }

    set({ runStatus: "running", executionLog: [], nodeResults: {} });

    try {
      const data = await api.runWorkflow(workflowId, { target_node_id: targetNodeId });
      const runId = (data as { run_id: string }).run_id;
      set({ runId });

      // Connect SSE for progress
      const token = sessionStorage.getItem("vt_token");
      const sseUrl = `/v1/api/workflow/runs/${runId}/stream?jwt=${token}`;
      const eventSource = new EventSource(sseUrl);

      eventSource.addEventListener("node_start", (e) => {
        const d = JSON.parse(e.data);
        get().addLog(d.node_id, `Started`, "info");
      });

      eventSource.addEventListener("node_done", (e) => {
        const d = JSON.parse(e.data);
        get().addLog(d.node_id, `Completed in ${d.duration_ms}ms`, "success");
        // Update node status on canvas
        set({
          nodes: get().nodes.map((n) =>
            n.id === d.node_id
              ? { ...n, data: { ...n.data, status: "done", duration_ms: d.duration_ms } }
              : n
          ),
        });
      });

      eventSource.addEventListener("node_error", (e) => {
        const d = JSON.parse(e.data);
        get().addLog(d.node_id, `Error: ${d.error_message}`, "error");
        set({
          nodes: get().nodes.map((n) =>
            n.id === d.node_id
              ? { ...n, data: { ...n.data, status: "error", error_message: d.error_message } }
              : n
          ),
        });
      });

      eventSource.addEventListener("node_cached", (e) => {
        const d = JSON.parse(e.data);
        get().addLog(d.node_id, "Used cached result", "success");
        set({
          nodes: get().nodes.map((n) =>
            n.id === d.node_id ? { ...n, data: { ...n.data, status: "cached" } } : n
          ),
        });
      });

      eventSource.addEventListener("workflow_done", () => {
        set({ runStatus: "completed" });
        eventSource.close();
      });

      eventSource.addEventListener("workflow_error", () => {
        set({ runStatus: "error" });
        eventSource.close();
      });

      eventSource.onerror = () => {
        set({ runStatus: get().runStatus === "running" ? "error" : get().runStatus });
        eventSource.close();
      };
    } catch (e) {
      console.error("Failed to run workflow:", e);
      set({ runStatus: "error" });
      throw e;
    }
  },

  runSingleNode: async (nodeId: string) => {
    const { workflowId, nodes, edges, nodeResults } = get();
    if (!workflowId) return;

    const node = nodes.find((n) => n.id === nodeId);
    if (!node) return;

    // Gather inputs from upstream edges using previous run results
    const inputs: Record<string, unknown> = {};
    const incomingEdges = edges.filter((e) => e.target === nodeId);
    for (const edge of incomingEdges) {
      const upstreamResult = nodeResults[edge.source];
      if (upstreamResult && upstreamResult.summary && edge.targetHandle) {
        // Try to find the specific output port's data
        inputs[edge.targetHandle] = upstreamResult.summary;
      }
    }

    try {
      const data = await api.runSingleNode(workflowId, nodeId, { inputs });
      get().addLog(nodeId, `Single run completed`, "success");
      return data;
    } catch (e) {
      console.error("Failed to run single node:", e);
      throw e;
    }
  },

  stopRun: async () => {
    const { workflowId } = get();
    if (!workflowId) return;
    await api.stopWorkflow(workflowId);
    set({ runStatus: "idle" });
  },

  addLog: (nodeId: string, message: string, level: "info" | "error" | "success" = "info") => {
    set({ executionLog: [...get().executionLog, { nodeId, message, level }] });
  },

  // ── Validation ──────────────────────────────────────────────────────────

  validateWorkflow: () => {
    const { nodes, edges, nodeDefinitions } = get();
    const errors: { nodeId?: string; edgeId?: string; message: string }[] = [];

    // Check required inputs are connected
    for (const node of nodes) {
      const def = nodeDefinitions.find((d) => d.node_type === node.data?.node_type);
      if (!def) continue;
      for (const port of def.inputs) {
        if (!port.required) continue;
        const connected = edges.some(
          (e) => e.target === node.id && e.targetHandle === port.name
        );
        if (!connected) {
          errors.push({ nodeId: node.id, message: `Required input '${port.name}' is not connected` });
        }
      }
    }
    return errors;
  },

  getCompatibleNodes: (portType: string): NodeDefinition[] => {
    return get().nodeDefinitions.filter((def) =>
      def.inputs.some((p) => isCompatible(portType as any, p.port_type))
    );
  },

  // ── Initialisation ──────────────────────────────────────────────────────

  fetchNodeDefinitions: async () => {
    try {
      const data = await api.listNodeTypes();
      if (Array.isArray(data)) {
        set({ nodeDefinitions: data as NodeDefinition[] });
      }
    } catch (e) {
      console.error("Failed to fetch node definitions:", e);
    }
  },

  reset: () => {
    _nodeIdCounter = 0;
    set({
      projectId: null,
      workflowId: null,
      workflowName: "Untitled Workflow",
      nodes: [],
      edges: [],
      viewport: initialViewport,
      runId: null,
      runStatus: "idle",
      nodeResults: {},
      executionLog: [],
      selectedNodeId: null,
      isDirty: false,
    });
  },
}));
