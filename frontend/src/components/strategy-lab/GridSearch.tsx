/**
 * GridSearch — parameter grid scanning panel for strategy backtesting.
 *
 * Allows users to define 1–2 parameter ranges, generates the full grid of
 * combinations, runs backtests in parallel, and displays ranked results.
 *
 * Usage: embed inside StrategyLab or any backtest-enabled page.
 */

import { useCallback, useMemo, useState } from "react";
import { Play, Loader2, Table, Zap } from "lucide-react";
import { cn } from "@/lib/utils";

// ── Types ────────────────────────────────────────────────────────────────────

export interface GridParam {
  name: string;
  label: string;
  min: number;
  max: number;
  step: number;
}

interface GridResult {
  params: Record<string, number>;
  sharpe?: number;
  total_return?: number;
  max_drawdown?: number;
  annual_return?: number;
  win_rate?: number;
  trade_count?: number;
}

// ── Props ────────────────────────────────────────────────────────────────────

interface GridSearchProps {
  /** Available parameters that can be scanned. */
  parameters: GridParam[];
  /** Callback to run a single backtest with specific param values. */
  onRunBacktest: (params: Record<string, number>) => Promise<GridResult | null>;
  className?: string;
}

// ── Component ─────────────────────────────────────────────────────────────────

export function GridSearch({ parameters, onRunBacktest, className }: GridSearchProps) {
  const [selectedParams, setSelectedParams] = useState<string[]>([]);
  const [results, setResults] = useState<GridResult[]>([]);
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState({ done: 0, total: 0 });

  // Generate grid combinations
  const combinations = useMemo(() => {
    if (selectedParams.length === 0) return [];
    const axes: number[][] = [];
    for (const name of selectedParams) {
      const p = parameters.find((x) => x.name === name);
      if (!p) continue;
      const values: number[] = [];
      for (let v = p.min; v <= p.max + 1e-9; v += p.step) {
        values.push(Math.round(v * 1e6) / 1e6);
      }
      axes.push(values);
    }
    if (axes.length === 0) return [];
    // Cartesian product
    let combos: number[][] = [[]];
    for (const axis of axes) {
      const next: number[][] = [];
      for (const prefix of combos) {
        for (const val of axis) {
          next.push([...prefix, val]);
        }
      }
      combos = next;
    }
    return combos.map((vals) => {
      const params: Record<string, number> = {};
      selectedParams.forEach((name, i) => { params[name] = vals[i]; });
      return params;
    });
  }, [selectedParams, parameters]);

  const totalCombos = combinations.length;

  // Toggle a parameter in/out of the grid
  const toggleParam = (name: string) => {
    setSelectedParams((prev) =>
      prev.includes(name) ? prev.filter((n) => n !== name) : [...prev, name]
    );
    setResults([]);
  };

  // Run the grid
  const runGrid = useCallback(async () => {
    if (combinations.length === 0) return;
    setRunning(true);
    setResults([]);
    setProgress({ done: 0, total: combinations.length });

    const newResults: GridResult[] = [];
    let done = 0;
    const CONCURRENCY = 3;

    // Process in batches for controlled concurrency
    for (let i = 0; i < combinations.length; i += CONCURRENCY) {
      const batch = combinations.slice(i, i + CONCURRENCY);
      const batchResults = await Promise.all(
        batch.map((params) => onRunBacktest(params))
      );
      for (const r of batchResults) {
        if (r) newResults.push(r);
        done++;
      }
      setProgress({ done, total: combinations.length });
      setResults([...newResults].sort((a, b) => (b.sharpe || 0) - (a.sharpe || 0)));
    }

    setRunning(false);
  }, [combinations, onRunBacktest]);

  return (
    <div className={cn("space-y-3", className)}>
      {/* Parameter selector */}
      <div>
        <h4 className="text-xs font-semibold mb-1.5 uppercase text-muted-foreground">
          Grid Parameters
        </h4>
        <div className="flex flex-wrap gap-1.5">
          {parameters.map((p) => {
            const active = selectedParams.includes(p.name);
            return (
              <button
                key={p.name}
                onClick={() => toggleParam(p.name)}
                className={cn(
                  "text-[11px] px-2 py-0.5 rounded border transition-colors",
                  active
                    ? "bg-primary/10 border-primary text-primary"
                    : "bg-background border-border text-muted-foreground hover:border-primary/40"
                )}
              >
                {p.label} [{p.min}..{p.max}:{p.step}]
                {active && ` (${combinations.filter(c => c[p.name] !== undefined).length ||
                  Math.ceil((p.max - p.min) / p.step) + 1} vals)`}
              </button>
            );
          })}
        </div>
      </div>

      {/* Grid info */}
      {totalCombos > 0 && (
        <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
          <span>
            <Zap className="h-3 w-3 inline mr-0.5" />
            {totalCombos} combination{totalCombos !== 1 ? "s" : ""}
          </span>
          <button
            onClick={runGrid}
            disabled={running}
            className="flex items-center gap-1 px-2 py-0.5 rounded bg-primary text-primary-foreground text-[11px] hover:bg-primary/90 transition-colors disabled:opacity-50"
          >
            {running ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <Play className="h-3 w-3" />
            )}
            {running ? `Running (${progress.done}/${progress.total})` : "Run Grid"}
          </button>
        </div>
      )}

      {/* Results table */}
      {results.length > 0 && (
        <div className="border rounded overflow-hidden">
          <div className="flex items-center gap-1.5 px-2 py-1.5 bg-muted/50 border-b text-[11px] text-muted-foreground">
            <Table className="h-3 w-3" />
            Results (ranked by Sharpe)
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-[11px]">
              <thead>
                <tr className="border-b bg-muted/30">
                  <th className="px-2 py-1 text-left font-medium">#</th>
                  {selectedParams.map((name) => (
                    <th key={name} className="px-2 py-1 text-left font-medium">{name}</th>
                  ))}
                  <th className="px-2 py-1 text-right font-medium">Sharpe</th>
                  <th className="px-2 py-1 text-right font-medium">Return%</th>
                  <th className="px-2 py-1 text-right font-medium">MaxDD%</th>
                  <th className="px-2 py-1 text-right font-medium">Trades</th>
                </tr>
              </thead>
              <tbody>
                {results.slice(0, 50).map((r, i) => (
                  <tr
                    key={i}
                    className={cn(
                      "border-b last:border-0 hover:bg-muted/30 transition-colors",
                      i === 0 && "bg-green-50/30 dark:bg-green-950/20"
                    )}
                  >
                    <td className="px-2 py-1 text-muted-foreground">{i + 1}</td>
                    {selectedParams.map((name) => (
                      <td key={name} className="px-2 py-1 font-mono">{r.params[name]}</td>
                    ))}
                    <td className="px-2 py-1 text-right font-mono">
                      <span className={cn(
                        (r.sharpe || 0) > 1 ? "text-green-600" : (r.sharpe || 0) < 0 ? "text-red-500" : ""
                      )}>
                        {r.sharpe?.toFixed(2) || "—"}
                      </span>
                    </td>
                    <td className="px-2 py-1 text-right font-mono">{r.total_return?.toFixed(2) || "—"}</td>
                    <td className="px-2 py-1 text-right font-mono text-red-500">{r.max_drawdown?.toFixed(2) || "—"}</td>
                    <td className="px-2 py-1 text-right font-mono text-muted-foreground">{r.trade_count || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {results.length > 50 && (
            <p className="px-2 py-1 text-[10px] text-muted-foreground border-t">
              Showing top 50 of {results.length} results
            </p>
          )}
        </div>
      )}
    </div>
  );
}
