import { useState, useCallback } from "react";
import { Play, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n";
import { api, type OptimizeProgress } from "@/lib/api";

interface OptimizeParam {
  name: string;
  type: string;
  default: unknown;
  description: string;
}

interface Props {
  verifyResult: {
    params: OptimizeParam[];
  } | null;
  codes: string;
  strategyCode: string;
  onSymbolsChange: (codes: string) => void;
}

/** Strategy-aware parameter optimization panel for Strategy Lab. */
export function StrategyOptimizePanel({
  verifyResult,
  codes,
  strategyCode,
  onSymbolsChange,
}: Props) {
  const { t } = useI18n();
  const params = verifyResult?.params?.filter((p) => p.type === "int" || p.type === "float" || p.type === "number") || [];
  const [ranges, setRanges] = useState<Record<string, { min: number; max: number; step: number }>>({});
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState<OptimizeProgress | null>(null);
  const [result, setResult] = useState<{ best_params: Record<string, number>; best_score: number } | null>(null);

  // Init ranges from param defaults
  const initRanges = useCallback(() => {
    const r: Record<string, { min: number; max: number; step: number }> = {};
    for (const p of params) {
      const d = Number(p.default) || 10;
      r[p.name] = { min: Math.max(1, Math.floor(d * 0.3)), max: Math.ceil(d * 3), step: 1 };
    }
    setRanges(r);
  }, [verifyResult]);

  if (!verifyResult || params.length === 0) {
    return (
      <div className="text-center py-8 space-y-3">
        <p className="text-xs text-muted-foreground">
          {(t as Record<string, string>).strategyLabNoVerify || "请先验证策略，提取参数后再进行优化"}
        </p>
        <p className="text-[10px] text-muted-foreground/60">
          点击工具栏的 Verify 按钮验证当前策略代码
        </p>
      </div>
    );
  }

  const codeList = codes.split(/[,;\s]+/).filter(Boolean);
  const canRun = codeList.length > 0 && Object.keys(ranges).length > 0 && !running;

  const runOptimize = async () => {
    setRunning(true);
    setResult(null);
    setProgress(null);

    // Build grid search space from ranges
    const searchParams: Record<string, number[]> = {};
    for (const [name, r] of Object.entries(ranges)) {
      const values: number[] = [];
      for (let v = r.min; v <= r.max; v += r.step) {
        values.push(Math.round(v * 100) / 100);
      }
      if (values.length <= 30) searchParams[name] = values;
    }

    if (Object.keys(searchParams).length === 0) {
      setRunning(false);
      return;
    }

    try {
      const res = await api.startOptimize({
        method: "grid",
        params: searchParams,
        codes: codeList,
        strategy_code: strategyCode,
      });

      // Poll for results
      const interval = setInterval(async () => {
        try {
          const p = await api.getOptimizeResult(res.job_id);
          const pct = p.result ? 100 : p.status === "running" ? 50 : 0;
          setProgress({ job_id: res.job_id, progress: pct, status: p.status });
          if (p.result) {
            clearInterval(interval);
            setResult({
              best_params: p.result.best_params as Record<string, number>,
              best_score: p.result.best_score as number,
            });
            setRunning(false);
          }
          if (p.status === "failed") {
            clearInterval(interval);
            setRunning(false);
          }
        } catch {
          clearInterval(interval);
          setRunning(false);
        }
      }, 2000);
    } catch {
      setRunning(false);
    }
  };

  return (
    <div className="space-y-3 text-xs">
      {/* Init ranges button */}
      {Object.keys(ranges).length === 0 && (
        <button onClick={initRanges} className="w-full py-2 rounded-lg border border-dashed text-muted-foreground hover:text-foreground hover:border-primary/30 transition-colors">
          初始化参数范围
        </button>
      )}

      {/* Symbols input */}
      <div className="space-y-1">
        <label className="text-[10px] font-medium text-muted-foreground">标的代码</label>
        <input
          type="text"
          value={codes}
          onChange={(e) => onSymbolsChange(e.target.value)}
          placeholder="600519.SH, 000001.SZ"
          className="w-full text-xs rounded border px-2 py-1 bg-background font-mono"
        />
      </div>

      {/* Parameter ranges */}
      {Object.keys(ranges).length > 0 && (
        <div className="space-y-2">
          <div className="text-[10px] font-medium text-muted-foreground">
            参数搜索范围 ({Object.keys(ranges).length})
          </div>
          {params.map((p) => {
            const r = ranges[p.name];
            if (!r) return null;
            return (
              <div key={p.name} className="flex items-center gap-1.5 bg-muted/30 rounded-lg px-2 py-1.5">
                <span className="font-mono font-medium w-24 truncate text-[11px]" title={p.description}>{p.name}</span>
                <input type="number" value={r.min} onChange={(e) => setRanges((prev) => ({ ...prev, [p.name]: { ...r, min: Number(e.target.value) } }))} className="w-12 text-[10px] rounded border px-1 py-0.5 bg-background text-center" />
                <span className="text-muted-foreground">–</span>
                <input type="number" value={r.max} onChange={(e) => setRanges((prev) => ({ ...prev, [p.name]: { ...r, max: Number(e.target.value) } }))} className="w-12 text-[10px] rounded border px-1 py-0.5 bg-background text-center" />
                <span className="text-[10px] text-muted-foreground">步长</span>
                <input type="number" value={r.step} min={0.01} step={0.1} onChange={(e) => setRanges((prev) => ({ ...prev, [p.name]: { ...r, step: Number(e.target.value) || 1 } }))} className="w-10 text-[10px] rounded border px-1 py-0.5 bg-background text-center" />
              </div>
            );
          })}
        </div>
      )}

      {/* Run button */}
      <button
        onClick={runOptimize}
        disabled={!canRun}
        className={cn(
          "w-full flex items-center justify-center gap-2 py-1.5 rounded-lg text-xs font-medium transition",
          canRun ? "bg-primary text-primary-foreground hover:bg-primary/90" : "bg-muted text-muted-foreground cursor-not-allowed"
        )}
      >
        {running ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
        {running ? "优化中..." : "运行网格搜索优化"}
      </button>

      {/* Progress */}
      {progress && running && (
        <div className="space-y-1">
          <div className="flex justify-between text-[10px] text-muted-foreground">
            <span>{progress.status}</span>
            <span>{progress.progress}%</span>
          </div>
          <div className="w-full h-1.5 rounded-full bg-muted overflow-hidden">
            <div className="h-full rounded-full bg-primary transition-all duration-500" style={{ width: `${progress.progress}%` }} />
          </div>
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="border rounded-lg p-3 space-y-2">
          <div className="text-[11px] font-semibold">最优参数</div>
          <div className="space-y-1">
            {Object.entries(result.best_params).map(([k, v]) => (
              <div key={k} className="flex justify-between text-[11px]">
                <span className="text-muted-foreground">{k}</span>
                <span className="font-mono font-medium">{typeof v === "number" ? v.toFixed(2) : String(v)}</span>
              </div>
            ))}
          </div>
          <div className="flex justify-between text-[11px] pt-1 border-t">
            <span className="text-muted-foreground">最优得分</span>
            <span className="font-mono font-medium text-primary">{result.best_score.toFixed(4)}</span>
          </div>
        </div>
      )}
    </div>
  );
}
