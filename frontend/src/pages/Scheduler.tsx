import { useEffect, useState, useCallback } from "react";
import { useI18n } from "@/lib/i18n";
import { useSchedulerStore } from "@/stores/schedulerStore";
import { cn } from "@/lib/utils";
import { Clock, Plus, Play, Pause, Trash2, RotateCw, ChevronDown, ChevronRight } from "lucide-react";

const TASK_TYPE_KEYS: Record<string, string> = {
  auto_backtest: "schedAutoBacktest",
  data_health_check: "schedDataHealth",
  watchlist_alert: "schedWatchlist",
  signal_report: "schedSignalReport",
  factor_mining: "schedFactorMining",
  screener_run: "schedScreener",
};

const CRON_PRESET_KEYS = [
  { i18nKey: "schedWeekday", expr: "0 9 * * 1-5" },
  { i18nKey: "schedAfterClose", expr: "30 15 * * *" },
  { i18nKey: "schedEveryHour", expr: "0 * * * *" },
  { i18nKey: "schedMonday", expr: "0 8 * * 1" },
  { i18nKey: "schedEvery30Min", expr: "*/30 * * * *" },
];

export function Scheduler() {
  const { t } = useI18n();
  const store = useSchedulerStore();
  const [showCreate, setShowCreate] = useState(false);
  const [newTask, setNewTask] = useState({ name: "", task_type: "auto_backtest", cron_expression: "0 9 * * 1-5" });
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => { store.loadTasks(); }, []);

  const handleCreate = useCallback(async () => {
    if (!newTask.name.trim()) return;
    await store.createTask(newTask);
    setShowCreate(false);
    setNewTask({ name: "", task_type: "auto_backtest", cron_expression: "0 9 * * 1-5" });
  }, [newTask, store]);

  const toggleExpand = (id: string) => {
    if (expandedId === id) { setExpandedId(null); return; }
    setExpandedId(id);
    store.loadExecutions(id);
  };

  return (
    <div className="flex flex-col h-full p-4 gap-3">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold flex items-center gap-2"><Clock className="h-5 w-5" />{t.scheduler || "Scheduled Tasks"}</h1>
        <button onClick={() => setShowCreate(true)} className="flex items-center gap-1 px-3 py-1.5 bg-primary text-primary-foreground rounded text-sm">
          <Plus className="h-4 w-4" />{t.schedulerNew || "New Task"}
        </button>
      </div>

      {/* Create form */}
      {showCreate && (
        <div className="border rounded-xl p-4 space-y-3 bg-muted/10">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-muted-foreground block mb-1">{t.schedulerName || "Name"}</label>
              <input value={newTask.name} onChange={(e) => setNewTask({ ...newTask, name: e.target.value })}
                placeholder="e.g. Daily backtest" className="w-full border rounded px-2 py-1.5 text-sm bg-background" />
            </div>
            <div>
              <label className="text-xs text-muted-foreground block mb-1">{t.schedulerType || "Type"}</label>
              <select value={newTask.task_type} onChange={(e) => setNewTask({ ...newTask, task_type: e.target.value })}
                className="w-full border rounded px-2 py-1.5 text-sm bg-background">
                {Object.entries(TASK_TYPE_KEYS).map(([value, i18nKey]) => <option key={value} value={value}>{(t as any)[i18nKey] || value}</option>)}
              </select>
            </div>
          </div>
          <div>
            <label className="text-xs text-muted-foreground block mb-1">Cron Expression</label>
            <div className="flex gap-2 items-center">
              <input value={newTask.cron_expression} onChange={(e) => setNewTask({ ...newTask, cron_expression: e.target.value })}
                className="flex-1 border rounded px-2 py-1.5 text-sm bg-background font-mono" />
              <select onChange={(e) => setNewTask({ ...newTask, cron_expression: e.target.value })} className="border rounded px-2 py-1.5 text-xs bg-background">
                <option value="">Presets...</option>
                {CRON_PRESET_KEYS.map((cp) => <option key={cp.expr} value={cp.expr}>{(t as any)[cp.i18nKey] || cp.expr}</option>)}
              </select>
            </div>
          </div>
          <div className="flex gap-2">
            <button onClick={handleCreate} className="px-4 py-1.5 bg-primary text-primary-foreground rounded text-sm">Create</button>
            <button onClick={() => setShowCreate(false)} className="px-4 py-1.5 border rounded text-sm hover:bg-muted">Cancel</button>
          </div>
        </div>
      )}

      {/* Task list */}
      <div className="flex-1 overflow-auto space-y-2">
        {store.tasks.length === 0 && !store.loading && (
          <div className="flex items-center justify-center h-32 text-muted-foreground text-sm">
            {t.schedulerNoTasks || "No scheduled tasks yet"}
          </div>
        )}
        {store.tasks.map((task) => (
          <div key={task.id} className="border rounded-xl overflow-hidden">
            <div className="flex items-center gap-3 p-3 hover:bg-muted/20 transition">
              <button onClick={() => toggleExpand(task.id)} className="p-0.5">{expandedId === task.id ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}</button>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium truncate">{task.name}</div>
                <div className="text-xs text-muted-foreground font-mono">{task.cron_expression}</div>
              </div>
              <span className="text-[10px] px-2 py-0.5 rounded bg-muted text-muted-foreground uppercase">{task.task_type.replace(/_/g, " ")}</span>
              <span className={cn("w-2 h-2 rounded-full", task.enabled ? "bg-success" : "bg-muted-foreground")} />
              <div className="flex gap-1">
                <button onClick={() => store.toggleTask(task.id, !task.enabled)}
                  className={cn("p-1 rounded hover:bg-muted", task.enabled ? "text-warning" : "text-success")}>
                  {task.enabled ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
                </button>
                <button onClick={() => store.runNow(task.id)} className="p-1 rounded hover:bg-muted text-primary"><RotateCw className="h-3.5 w-3.5" /></button>
                <button onClick={() => store.deleteTask(task.id)} className="p-1 rounded hover:bg-muted text-destructive"><Trash2 className="h-3.5 w-3.5" /></button>
              </div>
            </div>
            {expandedId === task.id && (
              <div className="border-t bg-muted/10 p-3 text-xs">
                <h4 className="font-semibold mb-1">Execution History</h4>
                {store.executionsLoading ? <span className="text-muted-foreground">Loading...</span> :
                  store.executions.length === 0 ? <span className="text-muted-foreground">No executions yet</span> :
                    store.executions.map((ex) => (
                      <div key={ex.id} className="flex items-center gap-2 py-1 border-b last:border-0">
                        <span className={cn("w-1.5 h-1.5 rounded-full", ex.status === "completed" ? "bg-success" : ex.status === "failed" ? "bg-destructive" : "bg-warning")} />
                        <span className="text-muted-foreground w-20">{ex.started_at ? new Date(ex.started_at).toLocaleTimeString() : ""}</span>
                        <span className={cn("px-1.5 py-0.5 rounded text-[10px]", ex.status === "completed" ? "bg-success/10 text-success" : "bg-destructive/10 text-destructive")}>{ex.status}</span>
                        {ex.error_message && <span className="text-destructive truncate">{ex.error_message}</span>}
                        {ex.output_log && <span className="text-muted-foreground truncate flex-1">{ex.output_log}</span>}
                      </div>
                    ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
