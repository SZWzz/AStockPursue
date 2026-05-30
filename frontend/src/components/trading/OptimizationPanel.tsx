import { useState, useRef, useCallback, useEffect } from "react";
import { Loader2, Play, Square } from "lucide-react";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n";
import { api, type OptimizeProgress } from "@/lib/api";

interface Props {
  symbol: string;
}

/** Parameter optimisation launcher with SSE progress bar and result display. */
export function OptimizationPanel({ symbol }: Props) {
  const { t } = useI18n();
  const [method, setMethod] = useState("grid");
  const [progress, setProgress] = useState<OptimizeProgress | null>(null);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [running, setRunning] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);
  const cleanupRef = useRef<(() => void) | null>(null);

  const stopSSE = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  }, []);

  useEffect(() => {
    cleanupRef.current = stopSSE;
    return () => { cleanupRef.current?.(); };
  }, [stopSSE]);

  const start = async () => {
    if (!symbol) return;
    setResult(null);
    setProgress(null);
    setRunning(true);
    try {
      const res = await api.startOptimize({
        method: method as "grid" | "random" | "bayesian",
        params: { symbol, period: "30" },
        codes: [symbol],
      });
      const jId = res.job_id;

      // Connect SSE
      try {
        const url = await api.optimizeStreamUrl(jId);
        const es = new EventSource(url);
        eventSourceRef.current = es;
        es.onmessage = (e) => {
          try {
            const p: OptimizeProgress = JSON.parse(e.data);
            setProgress(p);
            if (p.status === "completed" || p.status === "failed") {
              es.close();
              eventSourceRef.current = null;
              setRunning(false);
              if (p.status === "completed") {
                api.getOptimizeResult(jId).then((r) => setResult(r.result ?? null));
              }
            }
          } catch { /* ignore */ }
        };
        es.onerror = () => {
          es.close();
          eventSourceRef.current = null;
          setRunning(false);
        };
      } catch { /* ignore SSE */ }
    } catch (e) {
      setRunning(false);
    }
  };

  const stop = () => {
    stopSSE();
    setRunning(false);
  };

  const progressPct = progress?.progress ?? 0;

  return (
    <div className="flex flex-col h-full p-3 space-y-3 overflow-auto">
      {/* Controls */}
      <div className="flex items-center gap-2">
        <select
          value={method}
          onChange={(e) => setMethod(e.target.value)}
          className="text-xs rounded border px-2 py-1.5 bg-background"
        >
          <option value="grid">{t.tradingOptimizeMethodGrid || "网格搜索"}</option>
          <option value="random">{t.tradingOptimizeMethodRandom || "随机搜索"}</option>
          <option value="bayesian">{t.tradingOptimizeMethodBayesian || "贝叶斯优化"}</option>
        </select>
        <button
          onClick={running ? stop : start}
          disabled={!symbol}
          className={cn(
            "flex items-center gap-1 px-3 py-1.5 text-xs rounded font-medium transition",
            running
              ? "bg-down/10 text-down border border-down/30"
              : "bg-primary text-primary-foreground hover:bg-primary/90",
            !symbol && "opacity-50 cursor-not-allowed"
          )}
        >
          {running
            ? <><Square className="h-3 w-3" /> {t.cancel || "停止"}</>
            : <><Play className="h-3 w-3" /> {t.tradingOptimizeRun || "运行优化"}</>
          }
        </button>
        {!symbol && <span className="text-[10px] text-muted-foreground">{t.tradingNoSymbol || "请先选择标的"}</span>}
      </div>

      {/* Progress bar */}
      {(running || progress) && (
        <div className="space-y-1">
          <div className="flex justify-between text-[10px] text-muted-foreground">
            <span>{progress?.status === "completed" ? "完成" : progress?.status === "failed" ? "失败" : "优化中..."}</span>
            <span>{progressPct}%</span>
          </div>
          <div className="w-full h-2 rounded bg-muted overflow-hidden">
            <div
              className={cn(
                "h-full rounded transition-all duration-300",
                progress?.status === "failed" ? "bg-down" : progress?.status === "completed" ? "bg-up" : "bg-primary"
              )}
              style={{ width: `${progressPct}%` }}
            />
          </div>
        </div>
      )}

      {running && (
        <div className="flex justify-center py-2">
          <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
        </div>
      )}

      {/* Result */}
      {result && (
        <div className="border rounded-lg p-3 space-y-1.5">
          <div className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">{t.tradingOptimizeResult || "优化结果"}</div>
          {Object.entries(result).map(([k, v]) => (
            <div key={k} className="flex justify-between text-xs">
              <span className="text-muted-foreground">{k}</span>
              <span className="font-mono font-medium">{typeof v === "number" ? v.toFixed(4) : String(v)}</span>
            </div>
          ))}
        </div>
      )}

      {!running && !result && !progress && (
        <div className="flex-1 flex items-center justify-center text-[11px] text-muted-foreground/60">
          选择优化方法和标的后开始
        </div>
      )}
    </div>
  );
}
