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
  ExternalLink, Play, X,
} from "lucide-react";
import { StockInput } from "@/components/indicator-lab/StockInput";

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

// ── Full-editor link map (moved from NodePanel) ──────────────────────────

const FULL_EDITOR_MAP: Record<string, string> = {
  strategy: "/strategy-lab", alpha_zoo: "/alpha-zoo", gp_evolution: "/factor-mining",
  indicator: "/indicator-lab", screener: "/screener", attribution: "/attribution",
  paper_trading: "/paper-trading", agent: "/agent",
  correlation: "/correlation", comparison: "/compare",
  news_sentiment: "/sentiment", macro_sentiment: "/sentiment",
  order: "/trading", options_pricing: "/options",
  chart_data: "/strategy-lab", report: "/agent", factor_persist: "/factor-mining",
};

// Extract most differentiating config param for upstream label display
function _diffParam(cfg: Record<string, unknown>): string {
  if (!cfg || Object.keys(cfg).length === 0) return "";
  // Ordered by priority: window, period, top_n, threshold, mode
  const keys = ["window", "periods", "top_n", "threshold", "mode", "column"];
  for (const k of keys) {
    const v = cfg[k];
    if (v !== undefined && v !== "" && v !== null) return `${k}=${v}`;
  }
  // Fallback: first non-empty value
  for (const [k, v] of Object.entries(cfg)) {
    if (v !== undefined && v !== "" && v !== null && k !== "strategy_source")
      return `${k}=${v}`;
  }
  return "";
}

function getFullEditorPath(nodeType: string, nodeData: any): string | null {
  const path = FULL_EDITOR_MAP[nodeType];
  if (!path) return null;
  if (nodeType === "backtest") return nodeData?.run_id ? `/runs/${nodeData.run_id}` : null;
  return path;
}

// ── Icon map ──────────────────────────────────────────────────────────────

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

// ── Port type color map ────────────────────────────────────────────────────

// Border color for ReactFlow handle dots
const PORT_HANDLE_COLORS: Record<string, string> = {
  df_ohlcv: "!border-orange-400 !bg-orange-50 dark:!bg-orange-950",
  df_factor: "!border-blue-400 !bg-blue-50 dark:!bg-blue-950",
  df_returns: "!border-cyan-400 !bg-cyan-50 dark:!bg-cyan-950",
  signal: "!border-green-400 !bg-green-50 dark:!bg-green-950",
  backtest_result: "!border-purple-400 !bg-purple-50 dark:!bg-purple-950",
  factor_result: "!border-indigo-400 !bg-indigo-50 dark:!bg-indigo-950",
  stock_list: "!border-gray-400 !bg-gray-50 dark:!bg-gray-800",
  params: "!border-yellow-400 !bg-yellow-50 dark:!bg-yellow-950",
  attribution: "!border-rose-400 !bg-rose-50 dark:!bg-rose-950",
  technical_indicator: "!border-teal-400 !bg-teal-50 dark:!bg-teal-950",
  correlation_matrix: "!border-pink-400 !bg-pink-50 dark:!bg-pink-950",
  sentiment: "!border-red-300 !bg-red-50 dark:!bg-red-950",
  comparison_result: "!border-violet-400 !bg-violet-50 dark:!bg-violet-950",
  any: "!border-muted-foreground !bg-muted",
};

// Fill color for the colored dot next to port labels
const PORT_DOT_COLORS: Record<string, string> = {
  df_ohlcv: "bg-orange-400",
  df_factor: "bg-blue-400",
  df_returns: "bg-cyan-400",
  signal: "bg-green-400",
  backtest_result: "bg-purple-400",
  factor_result: "bg-indigo-400",
  stock_list: "bg-gray-400",
  params: "bg-yellow-400",
  attribution: "bg-rose-400",
  technical_indicator: "bg-teal-400",
  correlation_matrix: "bg-pink-400",
  sentiment: "bg-red-300",
  comparison_result: "bg-violet-400",
  any: "bg-muted-foreground",
};

// Abbreviated port type labels shown next to port name
const PORT_TYPE_LABELS: Record<string, string> = {
  df_ohlcv: "行情", df_factor: "因子", df_returns: "收益",
  signal: "信号", backtest_result: "回测", factor_result: "因子结果",
  stock_list: "股票", params: "参数", attribution: "归因",
  technical_indicator: "指标", correlation_matrix: "相关",
  sentiment: "情绪", comparison_result: "对比",
};

// ── Port handle ──────────────────────────────────────────────────────────────

function PortHandle({ port, side, dotIndex, upstreamLabel }: {
  port: NodePort; side: "left" | "right"; dotIndex: number;
  upstreamLabel?: string;
}) {
  const { t } = useI18n();
  const pt = port.port_type;
  const handleColor = PORT_HANDLE_COLORS[pt] || "!border-muted-foreground !bg-background";
  const dotColor = PORT_DOT_COLORS[pt] || "bg-muted-foreground";
  const typeLabel = PORT_TYPE_LABELS[pt] || "";
  const portLabel = (t as any)[`wfPort_${port.name}`] || port.name;
  const isSolid = dotIndex % 2 === 0;
  return (
    <div className={cn("flex items-center gap-1.5 px-1 py-1 text-xs group/port cursor-crosshair rounded hover:bg-muted/30 transition-colors", side === "right" && "flex-row-reverse")}>
      <Handle
        type={side === "left" ? "target" : "source"}
        position={side === "left" ? Position.Left : Position.Right}
        id={port.name}
        title={`${port.name}: ${pt}${port.required ? " (required)" : ""}`}
        className={cn(
          "!w-[16px] !h-[16px] !border-[3px] !rounded-full hover:!w-[22px] hover:!h-[22px] transition-all",
          handleColor
        )}
      />
      <span className="flex items-center gap-1 text-xs text-muted-foreground">
        <span className={cn("w-2 h-2 rounded-full shrink-0", isSolid ? dotColor : "bg-transparent border-2")} />
        <span className="shrink-0">{portLabel}</span>
        {upstreamLabel && (
          <span className="text-[9px] text-primary/60 whitespace-nowrap shrink-0">← {upstreamLabel}</span>
        )}
        {typeLabel && <span className="text-[9px] opacity-50">{typeLabel}</span>}
      </span>
    </div>
  );
}

// ── Quick metrics footer (type-aware result badges) ──────────────────────────

const NODE_BADGE_FORMATTERS: Record<string, (s: Record<string, unknown>) => string> = {
  backtest: (s) => {
    const parts: string[] = [];
    if (s.sharpe != null) parts.push(`Sharpe: ${Number(s.sharpe).toFixed(2)}`);
    if (s.total_return != null) parts.push(`Ret: ${(Number(s.total_return) * 100).toFixed(1)}%`);
    if (s.trade_count != null) parts.push(`${s.trade_count} trades`);
    return parts.join(" · ") || "Backtest done";
  },
  score: (s) => {
    const o = s.overall != null ? Number(s.overall).toFixed(0) : "?";
    const g = s.grade || "?";
    return `${o}/${g}`;
  },
  regime: (s) => `${s.regime || "?"} · ${s.confidence != null ? (Number(s.confidence) * 100).toFixed(0) + "%" : "?"}`,
  experiment: (s) => `${s.total || "?"} variants · Best: ${s.best_score != null ? s.best_score : "?"}`,
  send_notification: (s) => {
    const r = s.results as Record<string, boolean> | undefined;
    if (!r) return "No channels";
    return Object.entries(r).map(([ch, ok]) => ok ? `✅ ${ch}` : `❌ ${ch}`).join(" · ");
  },
  broker: (s) => `${s.connected ? "🟢" : "🔴"} ${s.position_count != null ? s.position_count + " pos" : ""}`,
  notify: () => "Notified",
  report: (s) => `${s.format || "Report"} generated`,
  export: (s) => `${s.format || "File"} exported`,
  factor_persist: (s) => `${s.saved != null ? s.saved : "?"} factors saved`,
};

function formatNodeBadge(nodeType: string, summary: Record<string, unknown>): string {
  const fmt = NODE_BADGE_FORMATTERS[nodeType];
  if (fmt) return fmt(summary);
  // Generic: show first 2 scalar values
  const entries = Object.entries(summary)
    .filter(([, v]) => typeof v !== "object" || v === null)
    .slice(0, 2);
  if (entries.length === 0) return "✓ Done";
  return entries.map(([k, v]) => `${k}: ${String(v).slice(0, 20)}`).join(" · ");
}

function NodeFooter({ nodeType, status, durationMs, summary, errorMessage }: {
  nodeType: string; status: string; durationMs?: number; summary?: Record<string, unknown>; errorMessage?: string;
}) {
  if (status === "done" && summary) {
    const badge = formatNodeBadge(nodeType, summary);
    return (
      <div className="border-t border-green-200 dark:border-green-800 px-2 py-1 text-[10px] text-muted-foreground bg-green-50/30 dark:bg-green-950/20 flex items-center gap-1">
        <span className="text-green-500 shrink-0">✓</span>
        <span className="truncate">{badge}</span>
        {durationMs ? <span className="text-muted-foreground/50 ml-auto shrink-0">{durationMs}ms</span> : null}
      </div>
    );
  }
  if (status === "error" && errorMessage) {
    return (
      <div className="border-t border-red-200 dark:border-red-800 px-2 py-1 text-[10px] text-down dark:text-down bg-red-50 dark:bg-red-950/30">
        ✗ {errorMessage.slice(0, 80)}
      </div>
    );
  }
  if (status === "running") {
    return (
      <div className="border-t border-blue-200 dark:border-blue-800 px-2 py-1 text-[10px] text-blue-500 bg-blue-50/30 dark:bg-blue-950/20 animate-pulse">
        ⏳ Running...
      </div>
    );
  }
  if (status === "cached") {
    return (
      <div className="border-t border-gray-200 px-2 py-1 text-[10px] text-muted-foreground bg-gray-50/30 dark:bg-gray-800/30">
        ↻ From cache
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

  // Show all config_schema fields inline on the card — no click-to-edit needed
  const inlineFields = Object.entries(schema).filter(
    ([, field]) => (field as any).type !== undefined
  );
  if (inlineFields.length === 0) return null;

  return (
    <div
      className="px-2 py-1.5 border-b space-y-1 bg-muted/20 nodrag"
      onMouseDown={stopPropagation}
      onClick={stopPropagation}
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
              <label htmlFor={fieldId} className="text-[10px] text-muted-foreground w-16 shrink-0 truncate" title={label}>
                {label}
              </label>
              <select
                id={fieldId}
                value={String(value)}
                onChange={(e) => onChange(e.target.value)}
                className="flex-1 min-w-0 px-1.5 py-0.5 text-[11px] rounded border bg-background focus:outline-none focus:ring-1 focus:ring-primary"
              >
                {f.enum_labels ? (
                  f.enum.map((v: string) => (
                    <option key={v} value={v}>{f.enum_labels[v] || v}</option>
                  ))
                ) : (
                  f.enum.map((v: string) => {
                    const ev = (t as any)[`wfEnum_${v}`] || v;
                    return <option key={v} value={v}>{ev}</option>;
                  })
                )}
              </select>
            </div>
          );
        }

        // Stock code input with autocomplete
        if (f.type === "stock_codes" || f.type === "stock_code") {
          const label = paramLabel(f, key);
          return (
            <div key={key} className="flex items-center gap-1.5">
              <label htmlFor={fieldId} className="text-[10px] text-muted-foreground w-16 shrink-0 truncate" title={label}>
                {label}
              </label>
              <div className="flex-1 min-w-0">
                <StockInput
                  value={String(value)}
                  onChange={(val) => onChange(val)}
                  multi={f.type === "stock_codes"}
                  placeholder={f.description || "搜索股票..."}
                />
              </div>
            </div>
          );
        }

        // Number input
        if (f.type === "number" || f.type === "integer") {
          const label = paramLabel(f, key);
          return (
            <div key={key} className="flex items-center gap-1.5">
              <label htmlFor={fieldId} className="text-[10px] text-muted-foreground w-16 shrink-0 truncate" title={label}>
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
            <label htmlFor={fieldId} className="text-[10px] text-muted-foreground w-16 shrink-0 truncate" title={label}>
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
  const nodeShortId = "#" + nodeData.id.slice(0, 4);

  // Subscribe to edges + nodes so port labels update live when connections change
  const edges = useWorkflowStore((s) => (s as any).edges) || [];
  const nodes = useWorkflowStore((s) => (s as any).nodes) || [];

  // Resolve upstream node labels for connected input ports
  const upstreamByPort: Record<string, string> = (() => {
    try {
      const nodeById: Record<string, any> = {};
      for (const n of nodes) nodeById[n.id] = n;
      const map: Record<string, string> = {};
      for (const e of edges) {
        if (e.target === nodeData.id) {
          const src = nodeById[e.source];
          if (src) {
            const d = src.data || {};
            const label = d.label || d.node_type || "";
            const cfg = d.config || (src as any).config || {};
            const cfgHint = _diffParam(cfg);
            const tag = cfgHint ? `${label}(${cfgHint})` : label;
            const port = e.target_port || e.targetHandle || "";
            map[port] = `#${e.source.slice(0,4)} ${tag}`;
          }
        }
      }
      return map;
    } catch { return {}; }
  })();

  return (
    <div
      className={cn(
        "rounded-lg border-2 bg-card shadow-sm min-w-[320px] transition-colors",
        selected && "border-primary ring-2 ring-primary/20",
        STATUS_STYLES[status] || STATUS_STYLES.pending
      )}
    >
      {/* Header */}
      <div className="flex items-center gap-1.5 px-2.5 py-1.5 border-b group/card">
        <span className="text-[9px] text-muted-foreground font-mono shrink-0">{nodeShortId}</span>
        <NodeIcon name={def?.icon} className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        <span className="flex-1 text-xs font-medium truncate">{nodeLabel}</span>
        {status !== "pending" && (
          <span className="text-[10px]" title={status}>
            {STATUS_ICONS[status] || ""}
          </span>
        )}
        {/* Action buttons — visible on hover */}
        <div className="flex items-center gap-0.5 opacity-0 group-hover/card:opacity-100 transition-opacity">
          {/* Quick tool link — opens the corresponding standalone page */}
          {def?.quick_tool_route && (
            <button
              onClick={(e) => { e.stopPropagation(); window.open(def.quick_tool_route, '_blank'); }}
              className="p-0.5 rounded hover:bg-primary/10 text-muted-foreground hover:text-primary transition-colors"
              title="Open in Quick Tool"
            >
              <ExternalLink className="h-3 w-3" />
            </button>
          )}
          {getFullEditorPath(nodeData.node_type, nodeData) && (
            <button
              onClick={(e) => { e.stopPropagation(); const p = getFullEditorPath(nodeData.node_type, nodeData); if (p) window.open(p, '_blank'); }}
              className="p-0.5 rounded hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
              title="Full Editor"
            >
              <ExternalLink className="h-3 w-3" />
            </button>
          )}
          <button
            onClick={(e) => { e.stopPropagation(); useWorkflowStore.getState().runSingleNode(nodeData.id); }}
            className="p-0.5 rounded hover:bg-primary/10 text-muted-foreground hover:text-primary transition-colors"
            title="Run this node"
          >
            <Play className="h-3 w-3" />
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); useWorkflowStore.getState().removeNode(nodeData.id); }}
            className="p-0.5 rounded hover:bg-down/10 dark:hover:bg-red-950/50 text-muted-foreground hover:text-down transition-colors"
            title="Delete node"
          >
            <X className="h-3 w-3" />
          </button>
        </div>
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
        {(() => {
          // Compute alternating solid/hollow indices per side+type
          const inputCounts: Record<string, number> = {};
          const outputCounts: Record<string, number> = {};
          return (
            <>
              {def?.inputs.map((port) => {
                const idx = inputCounts[port.port_type] || 0;
                inputCounts[port.port_type] = idx + 1;
                return <PortHandle key={port.name} port={port} side="left" dotIndex={idx}
                  upstreamLabel={upstreamByPort[port.name]} />;
              })}
              {def?.outputs.map((port) => {
                const idx = outputCounts[port.port_type] || 0;
                outputCounts[port.port_type] = idx + 1;
                return <PortHandle key={port.name} port={port} side="right" dotIndex={idx} />;
              })}
            </>
          );
        })()}
      </div>

      {/* Footer — type-aware result badge */}
      <NodeFooter nodeType={nodeData.node_type} status={status} durationMs={(nodeData as any).duration_ms} summary={(nodeData as any).summary} errorMessage={(nodeData as any).error_message} />
    </div>
  );
});

export default BaseNode;
