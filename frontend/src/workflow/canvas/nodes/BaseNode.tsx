/**
 * BaseNode — shared wrapper for all workflow node types on the canvas.
 *
 * Renders icon, label, status badge, input/output handles, and quick-metrics
 * footer.  The actual computation logic lives on the backend; this component
 * is purely presentational.
 */

import { memo } from "react";
import { Handle, NodeProps, Position } from "@xyflow/react";
import { cn } from "@/lib/utils";
import type { NodeDefinition, NodePort, WorkflowNodeData } from "@/workflow/types/workflow";

// ── Status badge colours ────────────────────────────────────────────────────

const STATUS_STYLES: Record<string, string> = {
  running: "border-blue-500 bg-blue-50 dark:bg-blue-950 animate-pulse",
  done: "border-green-500 bg-green-50 dark:bg-green-950",
  error: "border-red-500 bg-red-50 dark:bg-red-950",
  cached: "border-gray-400 bg-gray-50 dark:bg-gray-800",
  pending: "border-border bg-card",
  skipped: "border-amber-500 bg-amber-50 dark:bg-amber-950",
};

const STATUS_ICONS: Record<string, string> = {
  running: "⏳",
  done: "✓",
  error: "✗",
  cached: "↻",
  pending: "",
  skipped: "⊘",
};

// ── Port handle ──────────────────────────────────────────────────────────────

function PortHandle({ port, side }: { port: NodePort; side: "left" | "right" }) {
  const isConnected = false; // managed by React Flow internally
  const typeLabel = port.port_type.split(":").pop() || port.port_type;
  return (
    <div className={cn("flex items-center gap-1.5 px-1 py-0.5 text-xs", side === "right" && "justify-end")}>
      <Handle
        type={side === "left" ? "target" : "source"}
        position={side === "left" ? Position.Left : Position.Right}
        id={port.name}
        className={cn(
          "!w-2.5 !h-2.5 !border-2 !bg-background",
          port.required ? "!border-primary" : "!border-muted-foreground",
          !isConnected && port.required && "!border-amber-500"
        )}
      />
      <span className="text-muted-foreground truncate max-w-[100px]" title={`${port.name}: ${typeLabel}`}>
        {port.name}
      </span>
    </div>
  );
}

// ── Quick metrics footer ────────────────────────────────────────────────────

function NodeFooter({ status, durationMs, summary }: { status: string; durationMs?: number; summary?: Record<string, unknown> }) {
  if (status === "done" && summary) {
    const entries = Object.entries(summary).slice(0, 2);
    return (
      <div className="border-t px-2 py-1 text-[10px] text-muted-foreground">
        {entries.map(([k, v]) => (
          <span key={k} className="mr-2">
            {k}: {typeof v === "object" ? JSON.stringify(v).slice(0, 20) : String(v).slice(0, 20)}
          </span>
        ))}
        {durationMs ? <span>{durationMs}ms</span> : null}
      </div>
    );
  }
  if (status === "error" && (nodeData as any).error_message) {
    return (
      <div className="border-t px-2 py-1 text-[10px] text-red-500 bg-red-50 dark:bg-red-950/30">
        {(nodeData as any).error_message.slice(0, 60)}
      </div>
    );
  }
  return null;
}

// ── Main component ──────────────────────────────────────────────────────────

const BaseNode = memo(function BaseNode({ data, selected }: NodeProps) {
  const nodeData = data as unknown as WorkflowNodeData & { definition?: NodeDefinition };
  const def = nodeData.definition;
  const status = nodeData.status || "pending";

  return (
    <div
      className={cn(
        "rounded-lg border-2 bg-card shadow-sm min-w-[170px] max-w-[240px] transition-colors",
        selected && "border-primary ring-2 ring-primary/20",
        STATUS_STYLES[status] || STATUS_STYLES.pending
      )}
    >
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2 border-b">
        <span className="text-sm">{def?.icon ? def.icon : "○"}</span>
        <span className="flex-1 text-sm font-medium truncate">{nodeData.label || def?.label || nodeData.node_type}</span>
        {status !== "pending" && (
          <span className="text-xs" title={status}>
            {STATUS_ICONS[status] || ""}
          </span>
        )}
      </div>

      {/* Ports */}
      <div className="px-1 py-1.5 space-y-0.5">
        {def?.inputs.map((port) => (
          <PortHandle key={port.name} port={port} side="left" />
        ))}
        {def?.outputs.map((port) => (
          <PortHandle key={port.name} port={port} side="right" />
        ))}
      </div>

      {/* Footer */}
      <NodeFooter status={status} durationMs={nodeData.duration_ms} summary={(nodeData as any).summary} />
    </div>
  );
});

export default BaseNode;
