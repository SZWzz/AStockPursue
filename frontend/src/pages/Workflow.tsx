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
import { History, Clock, MoreHorizontal } from "lucide-react";
import { useWorkflowStore } from "@/workflow/store/workflowStore";
import { api } from "@/lib/api";
import WorkflowCanvas from "@/workflow/canvas/WorkflowCanvas";
import NodePalette from "@/workflow/canvas/NodePalette";
import NodePanel from "@/workflow/canvas/NodePanel";
import ResultsPanel from "@/workflow/canvas/ResultsPanel";

export default function WorkflowPage() {
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
          // Create new workflow in project
          const data = await api.createWorkflow(projectId, { name: "Untitled Workflow", description: "" });
          if (data && (data as any).id) {
            store.setWorkflowName("Untitled Workflow");
            // Navigate to the new workflow (replace URL)
            window.history.replaceState(null, "", `/workflow/${projectId}/${(data as any).id}`);
            // Reload state
            const newWfId = (data as any).id;
            // Update store with new workflow ID
            useWorkflowStore.setState({ workflowId: newWfId, isDirty: false });
          }
        }
      } catch (e: any) {
        console.error("Failed to load workflow:", e);
        setError(e.message || "Failed to load workflow");
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
      setError(e.message || "Failed to save");
    }
  };

  const handleRun = async () => {
    try {
      await store.runWorkflow();
    } catch (e: any) {
      setError(e.message || "Failed to run workflow");
    }
  };

  const handleStop = async () => {
    try {
      await store.stopRun();
    } catch (e: any) {
      setError(e.message || "Failed to stop workflow");
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
        <div className="flex items-center gap-3">
          <input
            type="text"
            value={store.workflowName}
            onChange={(e) => store.setWorkflowName(e.target.value)}
            className="text-sm font-medium bg-transparent border-none outline-none focus:border-b focus:border-primary w-48"
          />
          {store.isDirty && <span className="text-[10px] text-amber-500">Unsaved</span>}
        </div>

        <div className="flex items-center gap-1.5">
          <button
            onClick={() => { setShowHistory(!showHistory); if (workflowId) api.listWorkflowVersions(workflowId).then((d: any) => setVersions(d?.versions || [])).catch(() => {}); }}
            className="px-2 py-1 text-xs rounded border hover:bg-muted transition-colors flex items-center gap-1"
            title="Version History"
          >
            <History className="h-3 w-3" />
          </button>
          <button
            onClick={handleValidate}
            className="px-2 py-1 text-xs rounded border hover:bg-muted transition-colors"
          >
            Validate
          </button>
          <button
            onClick={handleSave}
            disabled={store.isSaving}
            className="px-2 py-1 text-xs rounded bg-muted hover:bg-muted/80 transition-colors"
          >
            {store.isSaving ? "Saving..." : "Save"}
          </button>
          {store.runStatus === "running" ? (
            <button
              onClick={handleStop}
              className="px-3 py-1 text-xs rounded bg-red-500 text-white hover:bg-red-600 transition-colors"
            >
              Stop
            </button>
          ) : (
            <button
              onClick={handleRun}
              className="px-3 py-1 text-xs rounded bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
            >
              Run
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="px-3 py-1 bg-red-50 dark:bg-red-950 text-red-600 text-xs border-b border-red-200 dark:border-red-800">
          {error}
          <button onClick={() => setError("")} className="ml-2 underline">Dismiss</button>
        </div>
      )}

      {/* Version History panel */}
      {showHistory && (
        <div className="px-3 py-2 border-b bg-card text-xs space-y-1 max-h-32 overflow-y-auto">
          <div className="flex items-center justify-between">
            <span className="font-semibold">Version History</span>
            <button onClick={() => setShowHistory(false)} className="text-muted-foreground hover:text-foreground">✕</button>
          </div>
          {versions.length === 0 ? (
            <p className="text-muted-foreground">No versions yet — run the workflow to create snapshots</p>
          ) : (
            versions.map((v: any, i: number) => (
              <div key={v.run_id} className="flex items-center justify-between py-0.5">
                <span>Run {v.run_id.slice(0, 8)} — {v.status} — {v.started_at?.slice(0, 16) || "unknown"}</span>
                <button
                  onClick={() => { if (workflowId) api.restoreWorkflowVersion(workflowId, v.run_id).then(() => store.loadWorkflow(workflowId)).catch(() => {}); }}
                  className="text-primary hover:underline"
                >
                  Restore
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
            <span className="font-semibold">Schedule Workflow</span>
            <button onClick={() => setShowSchedule(false)} className="text-muted-foreground hover:text-foreground">✕</button>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={cronExpr}
              onChange={(e) => setCronExpr(e.target.value)}
              placeholder="Cron expression (e.g. 0 9 * * 1-5)"
              className="flex-1 px-2 py-1 rounded border bg-background"
            />
            <button
              onClick={() => { if (workflowId) api.scheduleWorkflow(workflowId, { cron_expression: cronExpr, name: store.workflowName }).then(() => { setShowSchedule(false); alert("Scheduled!"); }).catch((e) => setError(e.message)); }}
              className="px-2 py-1 rounded bg-primary text-primary-foreground hover:bg-primary/90"
            >
              <Clock className="h-3 w-3 inline mr-1" />
              Schedule
            </button>
          </div>
          <p className="text-[10px] text-muted-foreground">Uses the system scheduler to run this workflow on a recurring schedule.</p>
        </div>
      )}

      {/* Main area */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: Node palette (240px) */}
        <div className="w-56 flex-shrink-0">
          <NodePalette />
        </div>

        {/* Centre: Canvas */}
        <div className="flex-1">
          <WorkflowCanvas />
        </div>

        {/* Right: Node config panel (280px) */}
        <div className="w-[280px] flex-shrink-0">
          <NodePanel />
        </div>
      </div>

      {/* Bottom: Results panel */}
      <ResultsPanel />
    </div>
  );
}
