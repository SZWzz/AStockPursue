/**
 * WorkflowCanvas — the main DAG editing surface powered by @xyflow/react.
 *
 * Features:
 * - Drop target for dragged node types from the palette
 * - Custom node rendering via BaseNode
 * - Connection validation on drop
 * - Selection management
 */

import { useCallback, useRef } from "react";
import {
  Background,
  Connection,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowInstance,
  ReactFlowProvider,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { useWorkflowStore } from "@/workflow/store/workflowStore";
import BaseNode from "@/workflow/canvas/nodes/BaseNode";
import RunSummaryPanel from "@/workflow/canvas/RunSummaryPanel";
import { isCompatible, type PortType } from "@/workflow/types/workflow";
import { visualizerNodeTypes } from "@/workflow/canvas/nodes/VisualizerNode";

// ── Custom node types ────────────────────────────────────────────────────────

const nodeTypes = {
  workflowNode: BaseNode,
  ...visualizerNodeTypes,
};

// ── Inner canvas (needs ReactFlowProvider context) ───────────────────────────

function CanvasInner() {
  const nodes = useWorkflowStore((s) => s.nodes);
  const edges = useWorkflowStore((s) => s.edges);
  const viewport = useWorkflowStore((s) => s.viewport);

  const onNodesChange = useWorkflowStore((s) => s.onNodesChange);
  const onEdgesChange = useWorkflowStore((s) => s.onEdgesChange);
  const onConnect = useWorkflowStore((s) => s.onConnect);
  const selectNode = useWorkflowStore((s) => s.selectNode);
  const addNode = useWorkflowStore((s) => s.addNode);

  const reactFlowInstance = useRef<ReactFlowInstance | null>(null);

  const onInit = useCallback((instance: ReactFlowInstance) => {
    reactFlowInstance.current = instance;
  }, []);

  // Drop handler for dragged palette items
  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const nodeType = event.dataTransfer.getData("application/reactflow-type");
      if (!nodeType) return;

      const position = reactFlowInstance.current?.screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      }) || { x: 0, y: 0 };

      addNode(nodeType, position);
    },
    [addNode]
  );

  // Validate connections
  const onConnectStart = useCallback((_event: any, _params: any) => {
    // Connection start — could highlight compatible targets in the future
  }, []);

  const onConnectEnd = useCallback(
    (_event: any, _connectionState: any) => {
      // If connection dropped on pane, reject silently
      // Could show suggestions for compatible nodes here in the future
    },
    []
  );

  const onConnectWrapped = useCallback(
    (connection: Connection) => {
      console.log("Connection attempt:", JSON.stringify(connection));
      const result = onConnect(connection);
      if (!result.success) {
        console.warn("Connection rejected:", result.error);
        useWorkflowStore.getState().addLog("", result.error || "Connection failed", "error");
      } else {
        console.log("Connection OK");
      }
    },
    [onConnect]
  );

  // ── Instant connection validation (prevents the edge from being drawn) ─────
  const nodeDefinitions = useWorkflowStore((s) => s.nodeDefinitions);

  const isValidConnection = useCallback(
    (conn: { source: string; target: string; sourceHandle?: string | null; targetHandle?: string | null }): boolean => {
      if (!conn.source || !conn.target) return false;
      if (conn.source === conn.target) return false;

      const nodes = useWorkflowStore.getState().nodes;
      const sourceNode = nodes.find((n) => n.id === conn.source);
      const targetNode = nodes.find((n) => n.id === conn.target);
      if (!sourceNode || !targetNode) return false;

      const sourceDef = nodeDefinitions.find((d) => d.node_type === sourceNode.data?.node_type);
      const targetDef = nodeDefinitions.find((d) => d.node_type === targetNode.data?.node_type);
      if (!sourceDef || !targetDef) return false;

      // Determine source port type
      let sourcePortType: PortType | null = null;
      if (conn.sourceHandle) {
        const port = sourceDef.outputs.find((p) => p.name === conn.sourceHandle);
        if (port) sourcePortType = port.port_type;
      }
      if (!sourcePortType && sourceDef.outputs.length === 1) {
        sourcePortType = sourceDef.outputs[0].port_type;
      }
      if (!sourcePortType) return false;

      // Determine target port type
      let targetPortType: PortType | null = null;
      if (conn.targetHandle) {
        const port = targetDef.inputs.find((p) => p.name === conn.targetHandle);
        if (port) targetPortType = port.port_type;
      }
      if (!targetPortType && targetDef.inputs.length === 1) {
        targetPortType = targetDef.inputs[0].port_type;
      }
      if (!targetPortType) return false;

      return isCompatible(sourcePortType, targetPortType);
    },
    [nodeDefinitions]
  );

  // Click on pane deselects node
  const onPaneClick = useCallback(() => {
    selectNode(null);
  }, [selectNode]);

  // Handle undo/redo keyboard shortcuts (Ctrl+Z / Ctrl+Shift+Z / Ctrl+Y)
  const undo = useWorkflowStore((s) => s.undo);
  const redo = useWorkflowStore((s) => s.redo);
  const canUndo = useWorkflowStore((s) => s.canUndo);
  const canRedo = useWorkflowStore((s) => s.canRedo);

  // Clipboard (copy/paste)
  const copySelectedNode = useWorkflowStore((s) => s.copySelectedNode);
  const pasteNode = useWorkflowStore((s) => s.pasteNode);
  const hasClipboard = useWorkflowStore((s) => s.hasClipboard);

  const onKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      const mod = event.metaKey || event.ctrlKey;
      // Ctrl+Z: undo
      if (mod && event.key === "z" && !event.shiftKey) {
        event.preventDefault();
        if (canUndo()) undo();
      }
      // Ctrl+Shift+Z / Ctrl+Y: redo
      else if (mod && ((event.key === "z" && event.shiftKey) || event.key === "y" || event.key === "Y")) {
        event.preventDefault();
        if (canRedo()) redo();
      }
      // Ctrl+C: copy selected node
      else if (mod && event.key === "c" && !event.shiftKey) {
        // Only handle copy when no text is selected (don't interfere with text selection)
        const selection = window.getSelection();
        if (!selection || selection.isCollapsed) {
          event.preventDefault();
          copySelectedNode();
        }
      }
      // Ctrl+V: paste copied node
      else if (mod && event.key === "v") {
        event.preventDefault();
        if (hasClipboard()) {
          const pos = reactFlowInstance.current?.screenToFlowPosition({
            x: window.innerWidth / 2,
            y: window.innerHeight / 2,
          }) || { x: 300, y: 200 };
          pasteNode(pos);
        }
      }
    },
    [undo, redo, canUndo, canRedo, copySelectedNode, pasteNode, hasClipboard]
  );

  // Handle Delete/Backspace key — remove nodes and their edges
  const removeNode = useWorkflowStore((s) => s.removeNode);
  const onNodesDelete = useCallback(
    (deletedNodes: any[]) => {
      for (const node of deletedNodes) {
        removeNode(node.id);
      }
    },
    [removeNode]
  );

  // Node click
  const onNodeClick = useCallback(
    (_event: React.MouseEvent, node: any) => {
      selectNode(node.id);
    },
    [selectNode]
  );

  // ── Render ─────────────────────────────────────────────────────────────

  return (
    <>
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onConnect={onConnectWrapped}
      onConnectStart={onConnectStart}
      onConnectEnd={onConnectEnd}
      isValidConnection={isValidConnection}
      onInit={onInit}
      onDragOver={onDragOver}
      onDrop={onDrop}
      onPaneClick={onPaneClick}
      onNodeClick={onNodeClick}
      onNodesDelete={onNodesDelete}
      onKeyDown={onKeyDown}
      nodeTypes={nodeTypes}
      defaultViewport={viewport}
      fitView
      deleteKeyCode={["Backspace", "Delete"]}
      multiSelectionKeyCode="Shift"
      snapToGrid
      snapGrid={[15, 15]}
      connectionRadius={30}
      className="bg-dot-pattern"
    >
      <Background gap={20} size={1} />
      <Controls position="bottom-right" />
      <MiniMap position="bottom-left" nodeStrokeWidth={3} pannable zoomable />
    </ReactFlow>
    <RunSummaryPanel />
    </>
  );
}

// ── Exported component (wraps in ReactFlowProvider) ──────────────────────────

export default function WorkflowCanvas() {
  return (
    <ReactFlowProvider>
      <CanvasInner />
    </ReactFlowProvider>
  );
}
