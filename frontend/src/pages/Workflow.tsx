/**
 * WorkflowPage — top-level page for the n8n-style workflow editor.
 *
 * Layout: toolbar (top) | palette (left) | canvas (centre) | panel (right) | results (bottom)
 *
 * Route: /workflow/:projectId/:workflowId
 * Query param: ?new=true to create a new workflow in the project
 */

import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { History, Clock, Download, Upload, PlaySquare, Layers } from "lucide-react";
import { useWorkflowStore } from "@/workflow/store/workflowStore";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { Breadcrumb } from "@/components/layout/Breadcrumb";
import WorkflowCanvas from "@/workflow/canvas/WorkflowCanvas";
import NodePalette from "@/workflow/canvas/NodePalette";
import ResultsPanel from "@/workflow/canvas/ResultsPanel";

export default function WorkflowPage() {
  const { t } = useI18n();
  const { projectId, workflowId } = useParams<{ projectId: string; workflowId: string }>();
  const [searchParams] = useSearchParams();
  const isNew = searchParams.get("new") === "true";

  const store = useWorkflowStore();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showHistory, setShowHistory] = useState(false);
  const [versions, setVersions] = useState<any[]>([]);
  const [showSchedule, setShowSchedule] = useState(false);
  const [cronExpr, setCronExpr] = useState("0 9 * * 1-5");
  const [showBatch, setShowBatch] = useState(false);
  const [batchParams, setBatchParams] = useState("");
  const [batchResults, setBatchResults] = useState<any[] | null>(null);
  const [batchError, setBatchError] = useState("");
  const [showReplay, setShowReplay] = useState(false);
  const [replayHistory, setReplayHistory] = useState<any[]>([]);

  // Load node definitions + workflow data
  useEffect(() => {
    const init = async () => {
      setLoading(true);
      setError("");
      try {
        // Fetch node type definitions
        await store.fetchNodeDefinitions();

        if (projectId) {
          store.setProjectId(projectId);
        }

        if (workflowId && !isNew) {
          await store.loadWorkflow(workflowId);
        } else if (projectId && isNew) {
          // Create new workflow with date-based name
          const now = new Date();
          const defaultName = `Workflow ${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')} ${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`;
          const data = await api.createWorkflow(projectId, { name: defaultName, description: "" });
          if (data && (data as any).id) {
            store.setWorkflowName(defaultName);
            window.history.replaceState(null, "", `/workflow/${projectId}/${(data as any).id}`);
            const newWfId = (data as any).id;
            useWorkflowStore.setState({ workflowId: newWfId, isDirty: false });
          }
        }
      } catch (e: any) {
        console.error("Failed to load workflow:", e);
        setError(e.message || (t as any).wfFailedLoad);
      } finally {
        setLoading(false);
      }
    };
    init();
  }, [projectId, workflowId, isNew]);

  // ── Toolbar actions ────────────────────────────────────────────────────

  const handleSave = async () => {
    try {
      await store.saveWorkflow();
    } catch (e: any) {
      setError(e.message || (t as any).wfFailedSave);
    }
  };

  const handleRun = async () => {
    try {
      await store.runWorkflow();
    } catch (e: any) {
      setError(e.message || (t as any).wfFailedRun);
    }
  };

  const handleStop = async () => {
    try {
      await store.stopRun();
    } catch (e: any) {
      setError(e.message || (t as any).wfFailedStop);
    }
  };

  const handleValidate = () => {
    const errors = store.validateWorkflow();
    if (errors.length === 0) {
      alert("Workflow is valid!");
    } else {
      alert(errors.map((e) => `${e.nodeId ? `Node ${e.nodeId.slice(0, 8)}: ` : ""}${e.message}`).join("\n"));
    }
  };

  const handleExport = async () => {
    if (!workflowId) return;
    try {
      const data = await api.exportWorkflow(workflowId);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${store.workflowName || "workflow"}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      setError(e.message || "Export failed");
    }
  };

  const handleImport = async (file: File) => {
    if (!projectId) return;
    try {
      const text = await file.text();
      const json = JSON.parse(text);
      if (workflowId && json.nodes?.length) {
        // Merge mode: import into current canvas with ID remapping
        store.importNodes({ nodes: json.nodes, edges: json.edges || [] }, { x: 50, y: 50 });
      } else {
        // New workflow mode
        const result = await api.importWorkflow(projectId, {
          name: json.name || file.name.replace(/\.json$/, ""),
          nodes: json.nodes || [],
          edges: json.edges || [],
        });
        if (result?.id && projectId) {
          window.location.href = `/workflow/${projectId}/${result.id}`;
        } else {
          window.location.reload();
        }
      }
    } catch (e: any) {
      setError(e.message || (t as any).wfImportError);
    }
  };

  const handleBatch = async () => {
    if (!workflowId) return;
    try {
      const paramGrid = JSON.parse(batchParams);
      const results = await api.batchRunWorkflow(workflowId, { param_grid: paramGrid });
      setBatchResults(results?.results || []);
    } catch (e: any) {
      setError(e.message || "Batch run failed");
    }
  };

  const handleReplay = async (runId: string) => {
    if (!runId) return;
    try {
      const result = await api.replayRun(runId);
      if (result?.run_id) {
        setShowReplay(false);
      }
    } catch (e: any) {
      setError(e.message || "Replay failed");
    }
  };

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "s") {
        e.preventDefault();
        handleSave();
      }
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
        e.preventDefault();
        handleRun();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  // ── Auto-save (3s debounce) ──
  useEffect(() => {
    if (!store.isDirty || !workflowId) return;
    const timer = setTimeout(() => {
      store.saveWorkflow().catch(() => {});
    }, 3000);
    return () => clearTimeout(timer);
  }, [store.isDirty, store.nodes, store.edges, workflowId]);

  // ── Warn before leaving with unsaved changes ──
  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (store.isDirty) {
        e.preventDefault();
      }
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [store.isDirty]);

  // ── Render ─────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="h-screen flex items-center justify-center bg-background">
        <p className="text-muted-foreground">Loading workflow...</p>
      </div>
    );
  }

  return (
    <div className="h-[calc(100vh-3rem)] flex flex-col bg-background">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-3 py-1.5 border-b bg-card">
        <div className="flex items-center gap-2">
          <Breadcrumb
            items={[
              { label: (t as any).projects || "Projects", to: "/projects" },
              { label: store.projectId ? `Project ${store.projectId.slice(0, 8)}` : "Project" },
              { label: store.workflowName || "Workflow" },
            ]}
          />
          {store.isDirty && <span className="text-[10px] text-amber-500 ml-2">{(t as any).wfUnsaved}</span>}
        </div>

        <div className="flex items-center gap-1.5">
          <button
            onClick={() => { setShowHistory(!showHistory); if (workflowId) api.listWorkflowVersions(workflowId).then((d: any) => setVersions(d?.versions || [])).catch(() => {}); }}
            className="px-2 py-1 text-xs rounded border hover:bg-muted transition-colors flex items-center gap-1"
            title={(t as any).wfVersionHistory}
          >
            <History className="h-3 w-3" />
          </button>
          <button
            onClick={handleValidate}
            className="px-2 py-1 text-xs rounded border hover:bg-muted transition-colors"
          >
            {(t as any).wfValidate}
          </button>
          <button
            onClick={handleExport}
            className="px-2 py-1 text-xs rounded border hover:bg-muted transition-colors flex items-center gap-1"
            title={(t as any).wfExport}
          >
            <Download className="h-3 w-3" />
          </button>
          <label
            className="px-2 py-1 text-xs rounded border hover:bg-muted transition-colors flex items-center gap-1 cursor-pointer"
            title={(t as any).wfImport}
          >
            <Upload className="h-3 w-3" />
            <input type="file" accept=".json" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) handleImport(f); }} />
          </label>
          <button
            onClick={() => setShowBatch(!showBatch)}
            className="px-2 py-1 text-xs rounded border hover:bg-muted transition-colors flex items-center gap-1"
            title={(t as any).wfBatch}
          >
            <Layers className="h-3 w-3" />
          </button>
          <button
            onClick={() => {
              setShowReplay(!showReplay);
              if (!showReplay && workflowId) {
                api.listWorkflowVersions(workflowId).then((d: any) => setReplayHistory(d?.versions || [])).catch(() => {});
              }
            }}
            className="px-2 py-1 text-xs rounded border hover:bg-muted transition-colors flex items-center gap-1"
            title={(t as any).wfReplay}
          >
            <PlaySquare className="h-3 w-3" />
          </button>
          <button
            onClick={handleSave}
            disabled={store.isSaving}
            className="px-2 py-1 text-xs rounded bg-muted hover:bg-muted/80 transition-colors"
          >
            {store.isSaving ? (t as any).wfSaving : (t as any).wfSave}
          </button>
          {store.runStatus === "running" ? (
            <button
              onClick={handleStop}
              className="px-3 py-1 text-xs rounded bg-red-500 text-white hover:bg-red-600 transition-colors"
            >
              {(t as any).wfStop}
            </button>
          ) : (
            <button
              onClick={handleRun}
              className="px-3 py-1 text-xs rounded bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
            >
              {(t as any).wfRun}
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="px-3 py-1 bg-red-50 dark:bg-red-950 text-down text-xs border-b border-red-200 dark:border-red-800">
          {error}
          <button onClick={() => setError("")} className="ml-2 underline">{(t as any).wfDismiss}</button>
        </div>
      )}

      {/* Version History panel */}
      {showHistory && (
        <div className="px-3 py-2 border-b bg-card text-xs space-y-1 max-h-32 overflow-y-auto">
          <div className="flex items-center justify-between">
            <span className="font-semibold">{(t as any).wfVersionHistory}</span>
            <button onClick={() => setShowHistory(false)} className="text-muted-foreground hover:text-foreground">✕</button>
          </div>
          {versions.length === 0 ? (
            <p className="text-muted-foreground">{(t as any).wfNoVersions}</p>
          ) : (
            versions.map((v: any) => (
              <div key={v.run_id} className="flex items-center justify-between py-0.5">
                <span>Run {v.run_id.slice(0, 8)} — {v.status} — {v.started_at?.slice(0, 16) || "unknown"}</span>
                <button
                  onClick={() => { if (workflowId) api.restoreWorkflowVersion(workflowId, v.run_id).then(() => store.loadWorkflow(workflowId)).catch(() => {}); }}
                  className="text-primary hover:underline"
                >
                  {(t as any).wfRestore}
                </button>
              </div>
            ))
          )}
        </div>
      )}

      {/* Schedule panel */}
      {showSchedule && (
        <div className="px-3 py-2 border-b bg-card text-xs space-y-2">
          <div className="flex items-center justify-between">
            <span className="font-semibold">{(t as any).wfSchedule}</span>
            <button onClick={() => setShowSchedule(false)} className="text-muted-foreground hover:text-foreground">✕</button>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={cronExpr}
              onChange={(e) => setCronExpr(e.target.value)}
              placeholder={(t as any).wfScheduleCron}
              className="flex-1 px-2 py-1 rounded border bg-background"
            />
            <button
              onClick={() => { if (workflowId) api.scheduleWorkflow(workflowId, { cron_expression: cronExpr, name: store.workflowName }).then(() => { setShowSchedule(false); alert((t as any).wfScheduled); }).catch((e) => setError(e.message)); }}
              className="px-2 py-1 rounded bg-primary text-primary-foreground hover:bg-primary/90"
            >
              <Clock className="h-3 w-3 inline mr-1" />
              {(t as any).wfScheduleBtn}
            </button>
          </div>
          <p className="text-[10px] text-muted-foreground">{(t as any).wfScheduleHint}</p>
        </div>
      )}

      {/* Batch panel */}
      {showBatch && (
        <div className="px-3 py-2 border-b bg-card text-xs space-y-2">
          <div className="flex items-center justify-between">
            <span className="font-semibold">{(t as any).wfBatchTitle}</span>
            <button onClick={() => { setShowBatch(false); setBatchResults(null); }} className="text-muted-foreground hover:text-foreground">✕</button>
          </div>
          <textarea
            value={batchParams}
            onChange={(e) => {
              const val = e.target.value;
              setBatchParams(val);
              try {
                const parsed = JSON.parse(val);
                const valid = typeof parsed === "object" && parsed !== null && Object.values(parsed).every((v) => Array.isArray(v));
                setBatchError(valid ? "" : "Each value must be an array, e.g. {\"key\": [1,2,3]}");
              } catch {
                setBatchError(val.trim() ? "Invalid JSON" : "");
              }
            }}
            placeholder='{"window": [10, 20, 30], "top_n": [5, 10]}'
            className={`w-full px-2 py-1 rounded border bg-background font-mono text-[11px] h-16 ${batchError ? "border-red-400" : ""}`}
          />
          {batchError && <p className="text-[10px] text-red-500">{batchError}</p>}
          <button
            onClick={handleBatch}
            disabled={!!batchError || !batchParams.trim()}
            className="px-2 py-1 rounded bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Layers className="h-3 w-3 inline mr-1" />
            Run Batch
          </button>
          {batchResults && (
            <div className="mt-2 overflow-auto max-h-40">
              <table className="w-full text-[10px]">
                <thead><tr className="border-b">{Object.keys(batchResults[0] || {}).map((k) => <th key={k} className="px-1 py-0.5 text-left">{k}</th>)}</tr></thead>
                <tbody>{batchResults.map((r: any, i: number) => <tr key={i} className="border-b">{Object.values(r).map((v: any, j: number) => <td key={j} className="px-1 py-0.5">{typeof v === "number" ? v.toFixed(4) : String(v)}</td>)}</tr>)}</tbody>
              </table>
              <button
                onClick={() => {
                  try {
                    const parsed = JSON.parse(batchParams);
                    const keys = Object.keys(parsed);
                    if (keys.length >= 2) {
                      store.addNode("param_heatmap", { x: 300, y: 300 });
                      const nodes = store.nodes;
                      const lastNode = nodes[nodes.length - 1];
                      if (lastNode) {
                        store.updateNodeConfig(lastNode.id, {
                          param1_name: keys[0], param1_range: parsed[keys[0]],
                          param2_name: keys[1], param2_range: parsed[keys[1]],
                          metric: "sharpe",
                        });
                      }
                    }
                  } catch {}
                }}
                className="mt-1 text-[10px] text-primary hover:underline"
              >
                Export to ParamHeatmap node
              </button>
            </div>
          )}
        </div>
      )}

      {/* Replay panel */}
      {showReplay && (
        <div className="px-3 py-2 border-b bg-card text-xs space-y-2 max-h-40 overflow-y-auto">
          <div className="flex items-center justify-between">
            <span className="font-semibold">{(t as any).wfReplayTitle}</span>
            <button onClick={() => setShowReplay(false)} className="text-muted-foreground hover:text-foreground">✕</button>
          </div>
          {replayHistory.length === 0 ? (
            <p className="text-muted-foreground">No execution history yet.</p>
          ) : (
            replayHistory.map((run: any) => (
              <div key={run.run_id} className="flex items-center justify-between py-0.5">
                <span className="truncate">
                  {run.run_id.slice(0, 8)} — {run.status} — {run.started_at?.slice(0, 16) || "unknown"}
                </span>
                <button
                  onClick={() => handleReplay(run.run_id)}
                  className="text-primary hover:underline shrink-0 ml-2"
                >
                  Replay
                </button>
              </div>
            ))
          )}
        </div>
      )}

      {/* Main area */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: Node palette */}
        <div className="w-56 flex-shrink-0">
          <NodePalette />
        </div>

        {/* Canvas (full width — right panel removed) */}
        <div className="flex-1">
          <WorkflowCanvas />
        </div>
      </div>

      {/* Bottom: Results panel */}
      <ResultsPanel />
    </div>
  );
}
