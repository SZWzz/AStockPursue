/**
 * BaseNode — shared wrapper for all workflow node types on the canvas.
 *
 * Renders icon, label, status badge, input/output handles, inline config
 * widgets (for fields marked `inline: true` in config_schema), and a
 * quick-metrics footer.  The actual computation logic lives on the backend;
 * this component is purely presentational.
 */

import { memo, useCallback } from "react";
import { Handle, NodeProps, Position } from "@xyflow/react";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n";
import { useWorkflowStore } from "@/workflow/store/workflowStore";
import type { NodeDefinition, NodePort, WorkflowNodeData } from "@/workflow/types/workflow";
import {
  Target, BarChart3, Layers, Database, Microscope, PieChart, Filter,
  TrendingUp, MessageSquare, Bot, GitBranch, FlaskConical, GitCompare,
  Newspaper, Globe, Send, FileText, CircleDollarSign, Bell, Download,
} from "lucide-react";

// ── i18n helpers ──────────────────────────────────────────────────────────────

function tNode(t: Record<string, string>, nodeType: string, fallback: string): string {
  const key = `wfNode_${nodeType}`;
  return (t as any)[key] || fallback;
}

// ── Icon map (backend sends Lucide icon name strings) ────────────────────────

const ICON_MAP: Record<string, React.ComponentType<any>> = {
  Target, BarChart3, Layers, Database, Microscope, PieChart, Filter,
  TrendingUp, MessageSquare, Bot, GitBranch, FlaskConical, GitCompare,
  Newspaper, Globe, Send, FileText, CircleDollarSign, Bell, Download,
};

function NodeIcon({ name, className }: { name?: string; className?: string }) {
  if (!name) return <span className={className}>○</span>;
  const Icon = ICON_MAP[name];
  return Icon ? <Icon className={className} /> : <span className={className}>○</span>;
}

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
    <div className={cn("flex items-center gap-1.5 px-1 py-1 text-xs group/port cursor-crosshair rounded hover:bg-muted/50 transition-colors", side === "right" && "flex-row-reverse")}>
      <Handle
        type={side === "left" ? "target" : "source"}
        position={side === "left" ? Position.Left : Position.Right}
        id={port.name}
        title={`${port.name} (${typeLabel})${port.required ? " — required" : ""}`}
        className={cn(
          "!w-[14px] !h-[14px] !border-[2.5px] !bg-background !rounded-full hover:!w-[20px] hover:!h-[20px] hover:!border-primary transition-all",
          port.required ? "!border-primary" : "!border-muted-foreground",
          !isConnected && port.required && "!border-amber-500 !animate-pulse"
        )}
      />
      <span className="text-muted-foreground truncate max-w-[100px]" title={`${port.name}: ${typeLabel}`}>
        {port.name}
      </span>
    </div>
  );
}

// ── Quick metrics footer ────────────────────────────────────────────────────

function NodeFooter({ status, durationMs, summary, errorMessage }: { status: string; durationMs?: number; summary?: Record<string, unknown>; errorMessage?: string }) {
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
  if (status === "error" && errorMessage) {
    return (
      <div className="border-t px-2 py-1 text-[10px] text-red-500 bg-red-50 dark:bg-red-950/30">
        {errorMessage.slice(0, 60)}
      </div>
    );
  }
  return null;
}

// ── Inline parameter widgets ──────────────────────────────────────────────────

function InlineParams({
  schema,
  config,
  nodeId,
}: {
  schema: Record<string, any>;
  config: Record<string, unknown>;
  nodeId: string;
}) {
  const updateNodeConfig = useWorkflowStore((s) => s.updateNodeConfig);
  const { t } = useI18n();

  const stopPropagation = useCallback((e: React.SyntheticEvent) => {
    e.stopPropagation();
  }, []);

  // Translate config_schema title via i18n (wfParam_{titleNoSpaces} → fallback to title)
  const paramLabel = (field: any, key: string) => {
    const titleKey = (field.title || "").replace(/\s+/g, "");
    return (t as any)[`wfParam_${titleKey}`] || field.title || key;
  };

  const inlineFields = Object.entries(schema).filter(
    ([, field]) => (field as any).inline === true
  );
  if (inlineFields.length === 0) return null;

  return (
    <div
      className="px-2 py-1.5 border-b space-y-1 bg-muted/20"
      onMouseDown={stopPropagation}
      onDoubleClick={stopPropagation}
      onKeyDown={stopPropagation}
    >
      {inlineFields.map(([key, field]) => {
        const f = field as any;
        const value = config[key] ?? f.default ?? "";
        const fieldId = `inline-${nodeId}-${key}`;

        const onChange = (newVal: unknown) => {
          updateNodeConfig(nodeId, { ...config, [key]: newVal });
        };

        // Select dropdown
        if (f.enum) {
          const label = (t as any)[`wfParam_${f.title}`] || f.title || key;
          return (
            <div key={key} className="flex items-center gap-1.5">
              <label htmlFor={fieldId} className="text-[10px] text-muted-foreground w-12 shrink-0 truncate" title={label}>
                {label}
              </label>
              <select
                id={fieldId}
                value={String(value)}
                onChange={(e) => onChange(e.target.value)}
                className="flex-1 min-w-0 px-1.5 py-0.5 text-[11px] rounded border bg-background focus:outline-none focus:ring-1 focus:ring-primary"
              >
                {f.enum.map((v: string) => {
                  const ev = (t as any)[`wfEnum_${v}`] || v;
                  return <option key={v} value={v}>{ev}</option>;
                })}
              </select>
            </div>
          );
        }

        // Number input
        if (f.type === "number" || f.type === "integer") {
          const label = paramLabel(f, key);
          return (
            <div key={key} className="flex items-center gap-1.5">
              <label htmlFor={fieldId} className="text-[10px] text-muted-foreground w-12 shrink-0 truncate" title={label}>
                {label}
              </label>
              <input
                id={fieldId}
                type="number"
                value={value as number}
                onChange={(e) => onChange(f.type === "integer" ? parseInt(e.target.value, 10) || 0 : parseFloat(e.target.value) || 0)}
                min={f.minimum}
                max={f.maximum}
                step={f.type === "integer" ? 1 : 0.01}
                className="flex-1 min-w-0 px-1.5 py-0.5 text-[11px] rounded border bg-background focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>
          );
        }

        // Fallback: text input
        const label = paramLabel(f, key);
        return (
          <div key={key} className="flex items-center gap-1.5">
            <label htmlFor={fieldId} className="text-[10px] text-muted-foreground w-12 shrink-0 truncate" title={label}>
              {label}
            </label>
            <input
              id={fieldId}
              type="text"
              value={String(value)}
              onChange={(e) => onChange(e.target.value)}
              className="flex-1 min-w-0 px-1.5 py-0.5 text-[11px] rounded border bg-background focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>
        );
      })}
    </div>
  );
}

// ── Main component ──────────────────────────────────────────────────────────

const BaseNode = memo(function BaseNode({ data, selected }: NodeProps) {
  const nodeData = data as unknown as WorkflowNodeData & { definition?: NodeDefinition };
  const def = nodeData.definition;
  const status = (nodeData as any).status || "pending";
  const { t } = useI18n();

  const nodeLabel = tNode(t, nodeData.node_type, def?.label || nodeData.label || nodeData.node_type);

  return (
    <div
      className={cn(
        "rounded-lg border-2 bg-card shadow-sm min-w-[170px] max-w-[280px] transition-colors",
        selected && "border-primary ring-2 ring-primary/20",
        STATUS_STYLES[status] || STATUS_STYLES.pending
      )}
    >
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2 border-b">
        <NodeIcon name={def?.icon} className="h-4 w-4 shrink-0 text-muted-foreground" />
        <span className="flex-1 text-sm font-medium truncate">{nodeLabel}</span>
        {status !== "pending" && (
          <span className="text-xs" title={status}>
            {STATUS_ICONS[status] || ""}
          </span>
        )}
      </div>

      {/* Inline params — config fields marked inline: true in config_schema */}
      {def?.config_schema && (
        <InlineParams
          schema={def.config_schema}
          config={nodeData.config || {}}
          nodeId={nodeData.id}
        />
      )}

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
      <NodeFooter status={status} durationMs={(nodeData as any).duration_ms} summary={(nodeData as any).summary} errorMessage={(nodeData as any).error_message} />
    </div>
  );
});

export default BaseNode;
