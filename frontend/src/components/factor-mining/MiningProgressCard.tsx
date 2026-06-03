import { cn } from "@/lib/utils";
import { Database, AlertTriangle, CheckCircle2 } from "lucide-react";

interface Props {
  status: string;
  currentGeneration: number;
  totalGenerations: number;
  bestIC: number;
  dataSource?: string;
  dataSourceDetail?: string;
  className?: string;
}

export function MiningProgressCard({
  status,
  currentGeneration,
  totalGenerations,
  bestIC,
  dataSource,
  dataSourceDetail,
  className,
}: Props) {
  const percentage = totalGenerations > 0
    ? Math.round((currentGeneration / totalGenerations) * 100)
    : 0;

  const statusLabel =
    status === "idle" ? "Not started"
    : status === "starting" ? "Initializing..."
    : status === "running" ? `Generation ${currentGeneration}/${totalGenerations}`
    : status === "completed" ? "Completed ✓"
    : status === "cancelled" ? "Cancelled"
    : status === "error" ? "Error ✗"
    : status;

  const statusColor =
    status === "running" ? "text-primary"
    : status === "completed" ? "text-success"
    : status === "error" || status === "cancelled" ? "text-destructive"
    : "text-muted-foreground";

  const dataSourceBadge = dataSource ? (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium",
        dataSource === "real"
          ? "bg-emerald-500/10 text-emerald-600 border border-emerald-500/20"
          : "bg-amber-500/10 text-amber-600 border border-amber-500/20"
      )}
      title={dataSourceDetail || dataSource}
    >
      {dataSource === "real" ? (
        <CheckCircle2 className="h-3 w-3" />
      ) : (
        <AlertTriangle className="h-3 w-3" />
      )}
      {dataSource === "real" ? "Real Data" : "Mock Data ⚠"}
      {dataSourceDetail && (
        <span className="text-[9px] opacity-70 ml-0.5 max-w-[120px] truncate">
          {dataSourceDetail}
        </span>
      )}
    </span>
  ) : null;

  return (
    <div className={cn("border rounded-xl p-3", className)}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className={cn("text-sm font-medium", statusColor)}>{statusLabel}</span>
          {dataSourceBadge}
        </div>
        {bestIC !== 0 && (
          <span className="text-xs text-muted-foreground">
            Best IC: <span className={bestIC > 0 ? "text-success" : "text-destructive"}>{bestIC.toFixed(4)}</span>
          </span>
        )}
      </div>

      {/* Prominent warning when running on mock data */}
      {dataSource === "mock" && status === "running" && (
        <div className="mb-2 p-2 rounded-lg bg-amber-500/10 border border-amber-500/20 text-xs text-amber-700 dark:text-amber-400">
          <strong>⚠ Running on MOCK data</strong> — no real OHLCV data could be loaded.
          All factor IC values will be ≈ 0, and generations will produce identical results.
          Check that DataStore is configured and data sources (mootdx/eastmoney) are reachable.
          {dataSourceDetail && <div className="mt-1 text-[10px] opacity-70">Reason: {dataSourceDetail}</div>}
        </div>
      )}

      {status === "running" && (
        <div className="w-full bg-muted rounded-full h-2 overflow-hidden">
          <div
            className="h-full bg-primary rounded-full transition-all duration-500 ease-out"
            style={{ width: `${Math.max(percentage, 2)}%` }}
          />
        </div>
      )}
      {status === "idle" && (
        <p className="text-xs text-muted-foreground flex items-center gap-1">
          <Database className="h-3 w-3" />
          Configure parameters and start evolution.
        </p>
      )}
    </div>
  );
}
