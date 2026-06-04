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

// ── Custom node types ────────────────────────────────────────────────────────

const nodeTypes = {
  workflowNode: BaseNode,
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
      const result = onConnect(connection);
      if (!result.success) {
        console.warn("Connection rejected:", result.error);
        // Could show toast here
      }
    },
    [onConnect]
  );

  // Click on pane deselects node
  const onPaneClick = useCallback(() => {
    selectNode(null);
  }, [selectNode]);

  // Node click
  const onNodeClick = useCallback(
    (_event: React.MouseEvent, node: any) => {
      selectNode(node.id);
    },
    [selectNode]
  );

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onConnect={onConnectWrapped}
      onConnectStart={onConnectStart}
      onConnectEnd={onConnectEnd}
      onInit={onInit}
      onDragOver={onDragOver}
      onDrop={onDrop}
      onPaneClick={onPaneClick}
      onNodeClick={onNodeClick}
      nodeTypes={nodeTypes}
      defaultViewport={viewport}
      fitView
      deleteKeyCode={["Backspace", "Delete"]}
      multiSelectionKeyCode="Shift"
      snapToGrid
      snapGrid={[15, 15]}
      className="bg-dot-pattern"
    >
      <Background gap={20} size={1} />
      <Controls position="bottom-right" />
      <MiniMap position="bottom-left" nodeStrokeWidth={3} pannable zoomable />
    </ReactFlow>
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
