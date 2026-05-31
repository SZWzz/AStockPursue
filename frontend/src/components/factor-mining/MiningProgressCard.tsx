import { cn } from "@/lib/utils";

interface Props {
  status: string;
  currentGeneration: number;
  totalGenerations: number;
  bestIC: number;
  className?: string;
}

export function MiningProgressCard({
  status,
  currentGeneration,
  totalGenerations,
  bestIC,
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

  return (
    <div className={cn("border rounded-xl p-3", className)}>
      <div className="flex items-center justify-between mb-2">
        <span className={cn("text-sm font-medium", statusColor)}>{statusLabel}</span>
        {bestIC !== 0 && (
          <span className="text-xs text-muted-foreground">
            Best IC: <span className={bestIC > 0 ? "text-success" : "text-destructive"}>{bestIC.toFixed(4)}</span>
          </span>
        )}
      </div>
      {status === "running" && (
        <div className="w-full bg-muted rounded-full h-2 overflow-hidden">
          <div
            className="h-full bg-primary rounded-full transition-all duration-500 ease-out"
            style={{ width: `${Math.max(percentage, 2)}%` }}
          />
        </div>
      )}
      {status === "idle" && (
        <p className="text-xs text-muted-foreground">Configure parameters and start evolution.</p>
      )}
    </div>
  );
}
