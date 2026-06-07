/**
 * RunSummaryPanel — slide-out panel showing key results from all output nodes
 * after a workflow run completes.  Appears on the right side of the canvas.
 */

import { useMemo, useState } from "react";
import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { useWorkflowStore } from "@/workflow/store/workflowStore";
import type { WorkflowNodeData } from "@/workflow/types/workflow";

const OUTPUT_CATEGORIES = new Set(["output", "analysis", "execution"]);

const NODE_ICONS: Record<string, string> = {
  backtest: "📊", score: "🏆", regime: "📈", experiment: "🧪",
  send_notification: "🔔", notify: "🔔", broker: "🔌",
  report: "📄", export: "📦", factor_persist: "💾",
  strategy_history: "📉", crowding: "📐", factor_to_strategy: "🧩",
};

function formatSummary(nodeType: string, summary: Record<string, unknown>): string[] {
  const lines: string[] = [];
  switch (nodeType) {
    case "backtest":
      if (summary.sharpe != null) lines.push(`Sharpe: ${Number(summary.sharpe).toFixed(2)}`);
      if (summary.total_return != null) lines.push(`Return: ${(Number(summary.total_return) * 100).toFixed(1)}%`);
      if (summary.max_drawdown != null) lines.push(`MaxDD: ${(Number(summary.max_drawdown) * 100).toFixed(1)}%`);
      if (summary.trade_count != null) lines.push(`Trades: ${summary.trade_count}`);
      break;
    case "score":
      lines.push(`${summary.overall ?? "?"} / ${summary.grade ?? "?"}`);
      break;
    case "regime":
      lines.push(`${summary.regime ?? "?"} · confidence: ${summary.confidence != null ? (Number(summary.confidence) * 100).toFixed(0) + "%" : "?"}`);
      break;
    case "experiment":
      lines.push(`${summary.total ?? "?"} variants · Best: ${summary.best_score ?? "?"}`);
      break;
    case "send_notification":
    case "notify": {
      const r = summary.results as Record<string, boolean> | undefined;
      if (r) Object.entries(r).forEach(([ch, ok]) => lines.push(`${ok ? "✅" : "❌"} ${ch}`));
      break;
    }
    default:
      lines.push("✓ Completed");
  }
  if (summary.duration_ms) lines.push(`${summary.duration_ms}ms`);
  return lines;
}

export default function RunSummaryPanel() {
  const runStatus = useWorkflowStore((s) => s.runStatus);
  const nodeResults = useWorkflowStore((s) => s.nodeResults);
  const nodes = useWorkflowStore((s) => s.nodes);
  const selectNode = useWorkflowStore((s) => s.selectNode);
  const [visible, setVisible] = useState(true);

  // Compute output nodes (hook must be before any early return)
  const outputNodes = useMemo(() => {
    return nodes.filter((n) => {
      const def = (n as any).definition;
      const cat = def?.category || "";
      return OUTPUT_CATEGORIES.has(cat) && nodeResults[n.id];
    });
  }, [nodes, nodeResults]);

  // Only show after a run completes
  if (runStatus !== "completed" && runStatus !== "error") return null;
  if (outputNodes.length === 0) return null;

  return (
    <div className={cn(
      "absolute right-0 top-0 bottom-0 w-72 bg-card border-l shadow-lg z-20 flex flex-col transition-transform",
      !visible && "translate-x-full"
    )}>
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b">
        <h3 className="text-xs font-semibold">Run Summary</h3>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setVisible(!visible)}
            className="p-0.5 rounded hover:bg-muted text-muted-foreground"
            title={visible ? "Hide" : "Show"}
          >
            <ChevronRight className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* Node results */}
      <div className="flex-1 overflow-auto p-2 space-y-1.5">
        {outputNodes.map((node) => {
          const result = nodeResults[node.id];
          if (!result) return null;
          const nd = (node as any).data as WorkflowNodeData | undefined;
          const def = (node as any).definition;
          const nodeType = nd?.node_type || "";
          const icon = NODE_ICONS[nodeType] || "📌";
          const label = def?.label || nodeType;
          const summary = result.summary || {};
          const lines = formatSummary(nodeType, summary as Record<string, unknown>);

          return (
            <div
              key={node.id}
              className={cn(
                "rounded-lg border p-2 text-xs cursor-pointer hover:bg-muted/30 transition-colors",
                result.status === "error" ? "border-red-200 bg-red-50/30 dark:border-red-800 dark:bg-red-950/20" :
                result.status === "done" ? "border-green-200 bg-green-50/20 dark:border-green-800 dark:bg-green-950/10" :
                "border-border"
              )}
              onClick={() => selectNode(node.id)}
            >
              <div className="flex items-center gap-1.5 mb-1">
                <span>{icon}</span>
                <span className="font-medium truncate">{label}</span>
                {result.status === "error" && <span className="text-down ml-auto">✗</span>}
                {result.status === "done" && <span className="text-green-500 ml-auto">✓</span>}
              </div>
              {lines.map((line, i) => (
                <div key={i} className="text-muted-foreground ml-5">{line}</div>
              ))}
              {result.error_message && (
                <div className="text-down ml-5 truncate">{result.error_message.slice(0, 60)}</div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
