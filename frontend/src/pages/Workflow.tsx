/**
 * WorkflowPage — top-level page for the n8n-style workflow editor.
 *
 * Layout: toolbar (top) | palette (left) | canvas (centre) | panel (right) | results (bottom)
 *
 * Route: /workflow/:projectId/:workflowId
 * Query param: ?new=true to create a new workflow in the project
 */

import { useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { History, Clock, ArrowLeft } from "lucide-react";
import { useWorkflowStore } from "@/workflow/store/workflowStore";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import WorkflowCanvas from "@/workflow/canvas/WorkflowCanvas";
import NodePalette from "@/workflow/canvas/NodePalette";
import ResultsPanel from "@/workflow/canvas/ResultsPanel";

export default function WorkflowPage() {
  const navigate = useNavigate();
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
        <div className="flex items-center gap-2">
          {/* Back to project */}
          <button
            onClick={() => store.projectId ? navigate(`/projects`) : navigate(-1)}
            className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
            title={(t as any).backToWorkflow || "Back to Projects"}
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
          <input
            type="text"
            value={store.workflowName}
            onChange={(e) => store.setWorkflowName(e.target.value)}
            className="text-sm font-medium bg-transparent border-none outline-none focus:border-b focus:border-primary w-48"
          />
          {store.isDirty && <span className="text-[10px] text-amber-500">{(t as any).wfUnsaved}</span>}
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
