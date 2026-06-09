/**
 * NodePanel — right sidebar showing config form for the selected node.
 *
 * When a node on the canvas is selected, this panel displays its type info,
 * a dynamic config form (generated from the node's JSON Schema), input
 * connection status, and the last-run output preview.
 */

import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ExternalLink, Trash2 } from "lucide-react";
import { useWorkflowStore } from "@/workflow/store/workflowStore";
import { useI18n } from "@/lib/i18n";
import { StockInput } from "@/components/indicator-lab/StockInput";

// ── i18n helpers ──────────────────────────────────────────────────────────────

function tNode(t: Record<string, string>, nodeType: string, fallback: string): string {
  const key = `wfNode_${nodeType}`;
  return (t as any)[key] || fallback;
}
function tNodeDesc(t: Record<string, string>, nodeType: string, fallback: string): string {
  const key = `wfNode_${nodeType}_desc`;
  return (t as any)[key] || fallback;
}

// ── Node type → full-screen editor page mapping ──────────────────────────────
const FULL_EDITOR_MAP: Record<string, { label: string; path: string }> = {
  strategy: { label: "Strategy Lab", path: "/strategy-lab" },
  alpha_zoo: { label: "Alpha Zoo", path: "/alpha-zoo" },
  gp_evolution: { label: "Factor Mining", path: "/factor-mining" },
  indicator: { label: "Indicator Lab", path: "/indicator-lab" },
  screener: { label: "Screener", path: "/screener" },
  attribution: { label: "Attribution", path: "/attribution" },
  paper_trading: { label: "Paper Trading", path: "/paper-trading" },
  agent: { label: "Agent", path: "/agent" },
  backtest: { label: "Run Detail", path: "" },  // dynamic path
  correlation: { label: "Correlation", path: "/correlation" },
  comparison: { label: "Compare", path: "/compare" },
  news_sentiment: { label: "Sentiment", path: "/sentiment" },
  macro_sentiment: { label: "Sentiment", path: "/sentiment" },
  order: { label: "Trading", path: "/trading" },
  options_pricing: { label: "Options", path: "/options" },
  chart_data: { label: "Strategy Lab", path: "/strategy-lab" },
  report: { label: "Agent", path: "/agent" },
  factor_persist: { label: "Factor Mining", path: "/factor-mining" },
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
  const { t } = useI18n();

  const selectedNode = useMemo(
    () => nodes.find((n) => n.id === selectedNodeId),
    [nodes, selectedNodeId]
  );

  if (!selectedNode) {
    return (
      <div className="h-full flex items-center justify-center border-l bg-card text-sm text-muted-foreground p-4 text-center">
        {((t as any).wfNode_selectHint || "Select a node on the canvas to configure it")}
      </div>
    );
  }

  const nodeData = selectedNode.data as any;
  const def = nodeData.definition;
  const config = nodeData.config || {};
  const status = nodeData.status || "pending";
  const nodeType = nodeData.node_type || def?.node_type || "";

  // Translate label & description (i18n first, fallback to backend hardcoded)
  const displayLabel = tNode(t, nodeType, nodeData.label || def?.label || nodeType);
  const displayDesc = tNodeDesc(t, nodeType, def?.description || "");

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
            <h3 className="text-sm font-semibold">{displayLabel}</h3>
            <p className="text-[11px] text-muted-foreground">{displayDesc}</p>
          </div>
        </div>
        <div className="mt-2 flex items-center gap-2">
          <span className="text-[11px] px-1.5 py-0.5 rounded bg-muted">
            {status === "error" ? ((t as any).wfNode_error || "error") : status}
          </span>
          {/* Open in Full Editor */}
          {(() => {
            const editorPath = getFullEditorPath(nodeData.node_type, nodeData);
            if (editorPath) {
              const store = useWorkflowStore.getState();
              const returnTo = store.projectId && store.workflowId
                ? `/workflow/${store.projectId}/${store.workflowId}`
                : "";
              const href = returnTo ? `${editorPath}?returnTo=${encodeURIComponent(returnTo)}` : editorPath;
              return (
                <button
                  onClick={() => navigate(href)}
                  className="flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded border hover:bg-muted transition-colors text-muted-foreground hover:text-foreground"
                  title={`${((t as any).wfNode_fullEditor || "Full Editor")}: ${FULL_EDITOR_MAP[nodeData.node_type]?.label || ""}`}
                >
                  <ExternalLink className="h-3 w-3" />
                  {((t as any).wfNode_fullEditor || "Full Editor")}
                </button>
              );
            }
            return null;
          })()}
        </div>
        {nodeData.error_message && (
          <p className="text-[11px] text-down mt-1">{nodeData.error_message}</p>
        )}
      </div>

      {/* Strategy picker (special for strategy node) */}
      {nodeData.node_type === "strategy" && (
        <StrategyPicker config={config} onUpdate={(patch) => updateNodeConfig(selectedNodeId!, { ...config, ...patch })} />
      )}

      {/* Workflow picker (special for sub_workflow node) */}
      {nodeData.node_type === "sub_workflow" && (
        <>
          <WorkflowPicker config={config} onUpdate={(patch) => updateNodeConfig(selectedNodeId!, { ...config, ...patch })} projectId={useWorkflowStore.getState().projectId} />
          <MappingEditor
            title="Input Mapping"
            configKey="input_mapping"
            config={config}
            onUpdate={(patch) => updateNodeConfig(selectedNodeId!, { ...config, ...patch })}
          />
          <MappingEditor
            title="Output Mapping"
            configKey="output_mapping"
            config={config}
            onUpdate={(patch) => updateNodeConfig(selectedNodeId!, { ...config, ...patch })}
          />
        </>
      )}

      {/* Config form */}
      {def?.config_schema && Object.keys(def.config_schema).length > 0 && (
        <div className="p-3 border-b">
          <h4 className="text-xs font-semibold mb-2 uppercase text-muted-foreground">{((t as any).wfNode_configuration || "Configuration")}</h4>
          {Object.entries(def.config_schema as Record<string, any>)
            .filter(([key]) => {
              if (key === "saved_strategy_id" || key === "strategy_source") return false;
              const source = (config.strategy_source as string) || "template";
              if (source === "saved" && (key === "strategy_template" || key === "custom_code")) return false;
              if (source === "custom" && key === "strategy_template") return false;
              if (source === "template" && key === "custom_code") return false;
              return true;
            })
            .map(([key, schema]) => (
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
              ) : schema.type === "stock_codes" ? (
                <StockInput
                  value={(config[key] as string) || schema.default || ""}
                  onChange={(val) => updateNodeConfig(selectedNodeId!, { ...config, [key]: val })}
                  multi={true}
                  placeholder={schema.description || "搜索或输入代码..."}
                />
              ) : schema.type === "stock_code" ? (
                <StockInput
                  value={(config[key] as string) || schema.default || ""}
                  onChange={(val) => updateNodeConfig(selectedNodeId!, { ...config, [key]: val })}
                  multi={false}
                  placeholder={schema.description || "搜索或输入代码..."}
                />
              ) : schema.type === "number" || schema.type === "integer" ? (
                <input
                  type="number"
                  value={config[key] ?? schema.default ?? ""}
                  onChange={(e) => updateNodeConfig(selectedNodeId!, { ...config, [key]: Number(e.target.value) })}
                  className="w-full px-2 py-1 text-xs rounded border bg-background"
                  min={schema.minimum}
                  max={schema.maximum}
                />
              ) : schema.type === "boolean" ? (
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={!!config[key]}
                    onChange={(e) => updateNodeConfig(selectedNodeId!, { ...config, [key]: e.target.checked })}
                    className="rounded border-muted"
                  />
                  <span className="text-xs text-muted-foreground">{schema.title || key}</span>
                </label>
              ) : schema.type === "array" ? (
                schema.items?.enum ? (
                  <div className="flex flex-wrap gap-1">
                    {(schema.items.enum as string[]).map((opt: string) => {
                      const arr = Array.isArray(config[key]) ? config[key] as string[] : (schema.default as string[]) || [];
                      const checked = arr.includes(opt);
                      return (
                        <label key={opt} className="flex items-center gap-1 text-xs cursor-pointer">
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => {
                              const next = checked ? arr.filter((v: string) => v !== opt) : [...arr, opt];
                              updateNodeConfig(selectedNodeId!, { ...config, [key]: next });
                            }}
                            className="rounded border-muted"
                          />
                          {opt}
                        </label>
                      );
                    })}
                  </div>
                ) : (
                  <div className="space-y-1">
                    {(() => {
                      const arr = Array.isArray(config[key]) ? config[key] as (string | number)[] : [];
                      return arr.map((item, idx) => (
                        <div key={idx} className="flex items-center gap-1">
                          <input
                            type={schema.items?.type === "number" || schema.items?.type === "integer" ? "number" : "text"}
                            value={item}
                            onChange={(e) => {
                              const next = [...arr];
                              next[idx] = schema.items?.type === "number" || schema.items?.type === "integer" ? Number(e.target.value) : e.target.value;
                              updateNodeConfig(selectedNodeId!, { ...config, [key]: next });
                            }}
                            className="flex-1 px-2 py-0.5 text-xs rounded border bg-background"
                          />
                          <button
                            onClick={() => {
                              const next = arr.filter((_: any, i: number) => i !== idx);
                              updateNodeConfig(selectedNodeId!, { ...config, [key]: next });
                            }}
                            className="text-destructive hover:text-destructive/80 text-xs px-1"
                          >✕</button>
                        </div>
                      ));
                    })()}
                    <button
                      onClick={() => {
                        const arr = Array.isArray(config[key]) ? config[key] as any[] : [];
                        const defaultVal = schema.items?.type === "number" || schema.items?.type === "integer" ? 0 : "";
                        updateNodeConfig(selectedNodeId!, { ...config, [key]: [...arr, defaultVal] });
                      }}
                      className="text-xs text-primary hover:underline"
                    >+ Add item</button>
                  </div>
                )
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
          <h4 className="text-xs font-semibold mb-2 uppercase text-muted-foreground">{((t as any).wfNode_inputs || "Inputs")}</h4>
          {def.inputs.map((port: any) => (
            <div key={port.name} className="flex items-center justify-between text-xs mb-1">
              <span className={port.required ? "font-medium" : "text-muted-foreground"}>
                {port.name}
              </span>
              <span className="text-[10px] text-muted-foreground">
                {connectedInputs.includes(port.name)
                  ? ((t as any).wfNode_connected || "Connected")
                  : port.required
                    ? ((t as any).wfNode_required || "⚠ Required")
                    : ((t as any).wfNode_optional || "Optional")}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Output preview */}
      {status === "done" && nodeData.summary && (
        <div className="p-3">
          <h4 className="text-xs font-semibold mb-2 uppercase text-muted-foreground">{((t as any).wfNode_output || "Output")}</h4>
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
            {((t as any).wfNode_retryThis || "⟳ Retry This Node")}
          </button>
        )}
        <button
          onClick={() => useWorkflowStore.getState().runSingleNode(selectedNodeId!)}
          className="w-full py-1 text-xs rounded bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          {status === "error"
            ? ((t as any).wfNode_runAgain || "Run Again")
            : status === "done"
              ? ((t as any).wfNode_reRun || "Re-run")
              : ((t as any).wfNode_runThis || "Run This Node")}
        </button>
        <button
          onClick={() => { useWorkflowStore.getState().removeNode(selectedNodeId!); }}
          className="w-full py-1 text-xs rounded border border-red-300 text-down hover:bg-red-50 dark:hover:bg-red-950/30 transition-colors flex items-center justify-center gap-1"
        >
          <Trash2 className="h-3 w-3" />
          {((t as any).wfDeleteNode || "Delete Node")}
        </button>
      </div>
    </div>
  );
}

// ── Strategy Picker (for strategy node) ──────────────────────────────────────

function StrategyPicker({ config, onUpdate }: { config: Record<string, unknown>; onUpdate: (patch: Record<string, unknown>) => void }) {
  const [saved, setSaved] = useState<{ id: string; name: string }[]>([]);
  const [loading, setLoading] = useState(false);
  const source = (config.strategy_source as string) || "template";

  useEffect(() => {
    if (source === "saved") {
      setLoading(true);
      import("@/lib/api").then(({ api }) =>
        api.listStrategyOptions().then((data: any) => {
          setSaved(data?.strategies || []);
        }).catch(() => {}).finally(() => setLoading(false))
      );
    }
  }, [source]);

  return (
    <div className="p-3 border-b space-y-2">
      <h4 className="text-xs font-semibold uppercase text-muted-foreground">Strategy Source</h4>

      <div className="flex gap-1">
        {(["template", "saved", "custom"] as const).map((s) => (
          <button
            key={s}
            onClick={() => onUpdate({ strategy_source: s })}
            className={`flex-1 text-xs px-2 py-1 rounded border transition-colors ${
              source === s
                ? "bg-primary text-primary-foreground border-primary"
                : "bg-background text-muted-foreground hover:bg-muted border-border"
            }`}
          >
            {{ template: "Template", saved: "Saved", custom: "Custom" }[s]}
          </button>
        ))}
      </div>

      {source === "saved" && (
        <div>
          {loading ? (
            <p className="text-xs text-muted-foreground">Loading saved strategies…</p>
          ) : saved.length === 0 ? (
            <p className="text-xs text-muted-foreground">No saved strategies. Save one in Strategy Lab first.</p>
          ) : (
            <select
              value={(config.saved_strategy_id as string) || ""}
              onChange={(e) => onUpdate({ saved_strategy_id: e.target.value })}
              className="w-full px-2 py-1 text-xs rounded border bg-background"
            >
              <option value="">-- Select a strategy --</option>
              {saved.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          )}
        </div>
      )}
    </div>
  );
}

function WorkflowPicker({ config, onUpdate, projectId }: { config: Record<string, unknown>; onUpdate: (patch: Record<string, unknown>) => void; projectId?: string | null }) {
  const [workflows, setWorkflows] = useState<{ id: string; name: string }[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (projectId) {
      setLoading(true);
      import("@/lib/api").then(({ api }) =>
        api.listWorkflows(projectId).then((data: any) => {
          setWorkflows(data || []);
        }).catch(() => {}).finally(() => setLoading(false))
      );
    }
  }, [projectId]);

  return (
    <div className="p-3 border-b space-y-2">
      <h4 className="text-xs font-semibold uppercase text-muted-foreground">Sub-Workflow</h4>
      {loading ? (
        <p className="text-xs text-muted-foreground">Loading workflows…</p>
      ) : workflows.length === 0 ? (
        <p className="text-xs text-muted-foreground">No workflows in this project.</p>
      ) : (
        <select
          value={(config.workflow_id as string) || ""}
          onChange={(e) => onUpdate({ workflow_id: e.target.value })}
          className="w-full px-2 py-1 text-xs rounded border bg-background"
        >
          <option value="">-- Select a workflow --</option>
          {workflows.map((w) => (
            <option key={w.id} value={w.id}>{w.name}</option>
          ))}
        </select>
      )}
    </div>
  );
}

function MappingEditor({ title, configKey, config, onUpdate }: {
  title: string; configKey: string; config: Record<string, unknown>; onUpdate: (patch: Record<string, unknown>) => void;
}) {
  const mapping = (config[configKey] as Record<string, string>) || {};
  const entries = Object.entries(mapping);

  const addEntry = () => onUpdate({ [configKey]: { ...mapping, "": "" } });
  const removeEntry = (key: string) => {
    const next = { ...mapping };
    delete next[key];
    onUpdate({ [configKey]: next });
  };
  const updateKey = (oldKey: string, newKey: string) => {
    const next: Record<string, string> = {};
    for (const [k, v] of Object.entries(mapping)) {
      next[k === oldKey ? newKey : k] = v;
    }
    onUpdate({ [configKey]: next });
  };
  const updateValue = (key: string, val: string) => {
    onUpdate({ [configKey]: { ...mapping, [key]: val } });
  };

  return (
    <div className="p-3 border-b space-y-1">
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-semibold uppercase text-muted-foreground">{title}</h4>
        <button onClick={addEntry} className="text-[10px] text-primary hover:underline">+ Add</button>
      </div>
      {entries.length === 0 && <p className="text-[10px] text-muted-foreground">No mappings configured</p>}
      {entries.map(([k, v]) => (
        <div key={k} className="flex items-center gap-1">
          <input value={k} onChange={(e) => updateKey(k, e.target.value)} placeholder="from" className="flex-1 px-1 py-0.5 text-[10px] rounded border bg-background" />
          <span className="text-muted-foreground text-[10px]">→</span>
          <input value={v} onChange={(e) => updateValue(k, e.target.value)} placeholder="to" className="flex-1 px-1 py-0.5 text-[10px] rounded border bg-background" />
          <button onClick={() => removeEntry(k)} className="text-destructive text-[10px] px-0.5">✕</button>
        </div>
      ))}
    </div>
  );
}
