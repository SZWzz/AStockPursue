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
  // Usage frequency tracking (persisted to localStorage)
  nodeUsageCount: Record<string, number>;

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

  // ── Undo/Redo / Clipboard ───────────────────────────────────────────────

  undo: () => void;
  redo: () => void;
  canUndo: () => boolean;
  canRedo: () => boolean;
  copySelectedNode: () => void;
  pasteNode: (position: XYPosition) => void;
  hasClipboard: () => boolean;

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

// ── Undo/Redo history + clipboard (outside store — not reactive) ──────────────

const MAX_HISTORY = 50;

/** Copied node data (without position — position is offset on paste). */
let _clipboard: { node_type: string; label: string; config: Record<string, unknown> } | null = null;

interface HistorySnapshot {
  nodes: Node[];
  edges: Edge[];
}

let _history: HistorySnapshot[] = [];
let _future: HistorySnapshot[] = [];

function _pushHistory(nodes: Node[], edges: Edge[]) {
  _history.push({ nodes: structuredClone(nodes), edges: structuredClone(edges) });
  if (_history.length > MAX_HISTORY) _history.shift();
  _future = [];  // new action clears redo stack
}

function _popHistory(): HistorySnapshot | null {
  return _history.pop() ?? null;
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
  nodeUsageCount: (() => { try { return JSON.parse(localStorage.getItem("wf_node_usage") || "{}"); } catch { return {}; } })(),

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

    // Find port types
    const sourceNode = nodes.find((n) => n.id === connection.source);
    const targetNode = nodes.find((n) => n.id === connection.target);
    if (!sourceNode || !targetNode) return { success: false, error: "Node not found" };

    const sourceDef = nodeDefinitions.find((d) => d.node_type === sourceNode.data?.node_type);
    const targetDef = nodeDefinitions.find((d) => d.node_type === targetNode.data?.node_type);
    if (!sourceDef || !targetDef) return { success: false, error: "Node type not found" };

    // Find source port first
    let sourcePort = null;
    if (connection.sourceHandle) {
      sourcePort = sourceDef.outputs.find((p) => p.name === connection.sourceHandle);
    }
    if (!sourcePort && sourceDef.outputs.length === 1) {
      sourcePort = sourceDef.outputs[0];
    }
    if (!sourcePort) return { success: false, error: "Cannot determine source port" };

    // Find best matching target port (type-compatible always wins)
    const connectedTargetHandles = get().edges
      .filter((e) => e.target === connection.target)
      .map((e) => e.targetHandle);

    let targetPort = null;
    // First, try the exact handle the user connected to (if type-compatible & unconnected)
    if (connection.targetHandle) {
      const exact = targetDef.inputs.find((p) => p.name === connection.targetHandle);
      if (exact && isCompatible(sourcePort!.port_type, exact.port_type) && !connectedTargetHandles.includes(exact.name)) {
        targetPort = exact;
      }
    }
    // Fallback: auto-match first type-compatible, unconnected input
    if (!targetPort) {
      targetPort = targetDef.inputs.find(
        (p) => isCompatible(sourcePort!.port_type, p.port_type) && !connectedTargetHandles.includes(p.name)
      );
    }
    if (!targetPort) {
      const anyCompatible = targetDef.inputs.some((p) => isCompatible(sourcePort!.port_type, p.port_type));
      if (anyCompatible) {
        return { success: false, error: "All compatible input ports are already connected" };
      }
      return { success: false, error: `Type mismatch: ${sourcePort!.port_type} → no matching input on ${targetDef.label}` };
    }

    // Type compatibility check (should always pass due to auto-match, but double-check)
    if (!isCompatible(sourcePort.port_type, targetPort.port_type)) {
      return {
        success: false,
        error: `Type mismatch: ${sourcePort.port_type} → ${targetPort.port_type}`,
      };
    }

    const tgtHandle = targetPort.name;

    // Check for duplicate connection to the same input port
    const existingConnection = get().edges.find(
      (e) => e.target === connection.target && e.targetHandle === tgtHandle
    );
    if (existingConnection) {
      return { success: false, error: "Input port already connected" };
    }

    _pushHistory(get().nodes, get().edges);
    const edge: Edge = {
      id: edgeId(connection.source, connection.target) + "_" + sourcePort.name,
      source: connection.source,
      target: connection.target,
      sourceHandle: sourcePort.name,
      targetHandle: targetPort.name,
      data: {
        source_port: sourcePort.name,
        target_port: targetPort.name,
      } as unknown as Record<string, unknown>,
    };

    set({ edges: addEdge(edge, get().edges), isDirty: true });
    return { success: true };
  },

  addNode: (nodeType: string, position: XYPosition) => {
    const def = get().nodeDefinitions.find((d) => d.node_type === nodeType);
    if (!def) return;

    _pushHistory(get().nodes, get().edges);

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

    // Track usage frequency for node palette sorting
    const usage = { ...get().nodeUsageCount };
    usage[nodeType] = (usage[nodeType] || 0) + 1;
    try { localStorage.setItem("wf_node_usage", JSON.stringify(usage)); } catch { /* quota */ }

    set({ nodes: [...get().nodes, newNode], isDirty: true, nodeUsageCount: usage });
  },

  removeNode: (id: string) => {
    _pushHistory(get().nodes, get().edges);
    set({
      nodes: get().nodes.filter((n) => n.id !== id),
      edges: get().edges.filter((e) => e.source !== id && e.target !== id),
      isDirty: true,
      selectedNodeId: get().selectedNodeId === id ? null : get().selectedNodeId,
    });
  },

  updateNodeConfig: (id: string, config: Record<string, unknown>) => {
    _pushHistory(get().nodes, get().edges);
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

      // Poll for results (short polling, the run is fast)
      const pollInterval = setInterval(async () => {
        try {
          const runResult = await api.getWorkflowRun(runId);
          if (!runResult) return;

          const nr = runResult.node_results || {};
          const hasResults = Object.keys(nr).length > 0;
          const allDone = hasResults && Object.values(nr).every((r: any) => r.status === "done" || r.status === "cached" || r.status === "error");

          // Populate log and results
          if (hasResults) {
            const logEntries: { nodeId: string; message: string; level: "info" | "error" | "success" }[] = [];
            const results: Record<string, any> = {};
            const updatedNodes = get().nodes.map((n) => {
              const r = nr[n.id];
              if (!r) return n;
              results[n.id] = { status: r.status, summary: r.summary || {}, error_message: r.error_message || "", duration_ms: r.duration_ms || 0 };
              const level = r.status === "error" ? "error" : "success";
              logEntries.push({ nodeId: n.id, message: `[${n.data?.node_type || "node"}] ${r.status}${r.duration_ms ? " in " + r.duration_ms + "ms" : ""}`, level });
              return { ...n, data: { ...n.data, status: r.status, duration_ms: r.duration_ms, error_message: r.error_message } };
            });

            set({
              executionLog: logEntries,
              nodeResults: results,
              nodes: updatedNodes,
              runStatus: allDone ? (Object.values(nr).some((r: any) => r.status === "error") ? "error" : "completed") : "running",
            });
          }

          if (allDone) {
            clearInterval(pollInterval);
          }
        } catch (e) {
          // Keep polling on transient errors
        }
      }, 1000);

      // Safety: stop polling after 120s
      setTimeout(() => clearInterval(pollInterval), 120000);
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

  // ── Undo/Redo ───────────────────────────────────────────────────────────

  undo: () => {
    const snapshot = _popHistory();
    if (!snapshot) return;
    const { nodes: currentNodes, edges: currentEdges } = get();
    _future.push({ nodes: structuredClone(currentNodes), edges: structuredClone(currentEdges) });
    set({ nodes: snapshot.nodes, edges: snapshot.edges, isDirty: true });
  },

  redo: () => {
    const snapshot = _future.pop();
    if (!snapshot) return;
    const { nodes: currentNodes, edges: currentEdges } = get();
    _history.push({ nodes: structuredClone(currentNodes), edges: structuredClone(currentEdges) });
    set({ nodes: snapshot.nodes, edges: snapshot.edges, isDirty: true });
  },

  canUndo: () => _history.length > 0,
  canRedo: () => _future.length > 0,

  copySelectedNode: () => {
    const { selectedNodeId, nodes } = get();
    if (!selectedNodeId) return;
    const node = nodes.find((n) => n.id === selectedNodeId);
    if (!node) return;
    _clipboard = {
    node_type: node.data.node_type as string,
    label: node.data.label as string,
    config: { ...(node.data.config || {}) } as Record<string, unknown>,
  };
  },

  pasteNode: (position: XYPosition) => {
    if (!_clipboard) return;
    _pushHistory(get().nodes, get().edges);

    const def = get().nodeDefinitions.find((d) => d.node_type === _clipboard!.node_type);
    const newNode: Node = {
      id: nextNodeId(),
      type: "workflowNode",
      position,
      data: {
        id: "",
        node_type: _clipboard.node_type,
        label: _clipboard.label,
        position: position,
        config: { ..._clipboard.config },
        status: "pending",
        error_message: "",
        duration_ms: 0,
        definition: def,
      },
    };
    newNode.data.id = newNode.id;

    set({ nodes: [...get().nodes, newNode], isDirty: true });
  },

  hasClipboard: () => _clipboard !== null,

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
    _history = [];
    _future = [];
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
