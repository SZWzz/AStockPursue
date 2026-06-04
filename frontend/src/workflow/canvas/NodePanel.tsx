/**
 * NodePanel — right sidebar showing config form for the selected node.
 *
 * When a node on the canvas is selected, this panel displays its type info,
 * a dynamic config form (generated from the node's JSON Schema), input
 * connection status, and the last-run output preview.
 */

import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { ExternalLink } from "lucide-react";
import { useWorkflowStore } from "@/workflow/store/workflowStore";

// ── Node type → full-screen editor page mapping ──────────────────────────────
const FULL_EDITOR_MAP: Record<string, { label: string; path: string }> = {
  strategy: { label: "Strategy Lab", path: "/strategy-lab" },
  alpha_zoo: { label: "Alpha Zoo", path: "/alpha-zoo" },
  factor_mining: { label: "Factor Mining", path: "/factor-mining" },
  indicator: { label: "Indicator Lab", path: "/indicator-lab" },
  screener: { label: "Screener", path: "/screener" },
  attribution: { label: "Attribution", path: "/attribution" },
  paper_trading: { label: "Paper Trading", path: "/paper-trading" },
  agent: { label: "Agent", path: "/agent" },
  backtest: { label: "Run Detail", path: "" },  // dynamic path
};

function getFullEditorPath(nodeType: string, _nodeData: any): string | null {
  const mapping = FULL_EDITOR_MAP[nodeType];
  if (!mapping) return null;
  if (nodeType === "backtest") {
    // Link to run detail if a run_id is available
    const runId = _nodeData?.run_id;
    return runId ? `/runs/${runId}` : null;
  }
  return mapping.path;
}

export default function NodePanel() {
  const navigate = useNavigate();
  const selectedNodeId = useWorkflowStore((s) => s.selectedNodeId);
  const nodes = useWorkflowStore((s) => s.nodes);
  const updateNodeConfig = useWorkflowStore((s) => s.updateNodeConfig);
  const edges = useWorkflowStore((s) => s.edges);

  const selectedNode = useMemo(
    () => nodes.find((n) => n.id === selectedNodeId),
    [nodes, selectedNodeId]
  );

  if (!selectedNode) {
    return (
      <div className="h-full flex items-center justify-center border-l bg-card text-sm text-muted-foreground p-4 text-center">
        Select a node on the canvas to configure it
      </div>
    );
  }

  const nodeData = selectedNode.data as any;
  const def = nodeData.definition;
  const config = nodeData.config || {};
  const status = nodeData.status || "pending";

  // Find connected inputs
  const connectedInputs = edges
    .filter((e) => e.target === selectedNodeId)
    .map((e) => e.targetHandle);

  return (
    <div className="h-full flex flex-col border-l bg-card overflow-y-auto">
      {/* Header */}
      <div className="p-3 border-b">
        <div className="flex items-center gap-2">
          <span>{def?.icon || "○"}</span>
          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-semibold">{nodeData.label || def?.label || nodeData.node_type}</h3>
            <p className="text-[11px] text-muted-foreground">{def?.description}</p>
          </div>
        </div>
        <div className="mt-2 flex items-center gap-2">
          <span className="text-[11px] px-1.5 py-0.5 rounded bg-muted">
            {status}
          </span>
          {/* Open in Full Editor */}
          {(() => {
            const editorPath = getFullEditorPath(nodeData.node_type, nodeData);
            if (editorPath) {
              return (
                <button
                  onClick={() => navigate(editorPath)}
                  className="flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded border hover:bg-muted transition-colors text-muted-foreground hover:text-foreground"
                  title={`Open in ${FULL_EDITOR_MAP[nodeData.node_type]?.label || "full editor"}`}
                >
                  <ExternalLink className="h-3 w-3" />
                  Full Editor
                </button>
              );
            }
            return null;
          })()}
        </div>
        {nodeData.error_message && (
          <p className="text-[11px] text-red-500 mt-1">{nodeData.error_message}</p>
        )}
      </div>

      {/* Config form */}
      {def?.config_schema && Object.keys(def.config_schema).length > 0 && (
        <div className="p-3 border-b">
          <h4 className="text-xs font-semibold mb-2 uppercase text-muted-foreground">Configuration</h4>
          {Object.entries(def.config_schema as Record<string, any>).map(([key, schema]) => (
            <div key={key} className="mb-2">
              <label className="text-xs text-muted-foreground block mb-0.5">{schema.title || key}</label>
              {schema.type === "string" && schema.enum ? (
                <select
                  value={(config[key] as string) || schema.default || ""}
                  onChange={(e) => updateNodeConfig(selectedNodeId!, { ...config, [key]: e.target.value })}
                  className="w-full px-2 py-1 text-xs rounded border bg-background"
                >
                  {schema.enum.map((v: string) => (
                    <option key={v} value={v}>{v}</option>
                  ))}
                </select>
              ) : schema.type === "number" || schema.type === "integer" ? (
                <input
                  type="number"
                  value={config[key] ?? schema.default ?? ""}
                  onChange={(e) => updateNodeConfig(selectedNodeId!, { ...config, [key]: Number(e.target.value) })}
                  className="w-full px-2 py-1 text-xs rounded border bg-background"
                  min={schema.minimum}
                  max={schema.maximum}
                />
              ) : (
                <input
                  type="text"
                  value={(config[key] as string) || schema.default || ""}
                  onChange={(e) => updateNodeConfig(selectedNodeId!, { ...config, [key]: e.target.value })}
                  className="w-full px-2 py-1 text-xs rounded border bg-background"
                />
              )}
            </div>
          ))}
        </div>
      )}

      {/* Input mapping */}
      {def?.inputs && def.inputs.length > 0 && (
        <div className="p-3 border-b">
          <h4 className="text-xs font-semibold mb-2 uppercase text-muted-foreground">Inputs</h4>
          {def.inputs.map((port: any) => (
            <div key={port.name} className="flex items-center justify-between text-xs mb-1">
              <span className={port.required ? "font-medium" : "text-muted-foreground"}>
                {port.name}
              </span>
              <span className="text-[10px] text-muted-foreground">
                {connectedInputs.includes(port.name) ? "Connected" : port.required ? "⚠ Required" : "Optional"}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Output preview */}
      {status === "done" && nodeData.summary && (
        <div className="p-3">
          <h4 className="text-xs font-semibold mb-2 uppercase text-muted-foreground">Output</h4>
          <pre className="text-[10px] bg-muted p-2 rounded overflow-x-auto max-h-40">
            {JSON.stringify(nodeData.summary, null, 1)}
          </pre>
        </div>
      )}

      {/* Actions */}
      <div className="p-3 border-t mt-auto space-y-1.5">
        {status === "error" && (
          <button
            onClick={() => useWorkflowStore.getState().runSingleNode(selectedNodeId!)}
            className="w-full py-1 text-xs rounded bg-amber-500 text-white hover:bg-amber-600 transition-colors"
          >
            ⟳ Retry This Node
          </button>
        )}
        <button
          onClick={() => useWorkflowStore.getState().runSingleNode(selectedNodeId!)}
          className="w-full py-1 text-xs rounded bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          {status === "error" ? "Run Again" : status === "done" ? "Re-run" : "Run This Node"}
        </button>
      </div>
    </div>
  );
}
