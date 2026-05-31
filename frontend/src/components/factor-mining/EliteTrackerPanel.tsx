import { cn } from "@/lib/utils";
import type { EliteEntry } from "@/types/api";
import { Crown, TrendingUp, Hash, Clock } from "lucide-react";

interface Props {
  elites: EliteEntry[];
  className?: string;
}

export function EliteTrackerPanel({ elites, className }: Props) {
  if (elites.length === 0) {
    return (
      <div className={cn("border rounded-xl p-3", className)}>
        <h3 className="text-sm font-semibold mb-2 flex items-center gap-1.5">
          <Crown className="h-4 w-4 text-amber-500" />
          Elite Tracker
        </h3>
        <p className="text-xs text-muted-foreground">
          Factors that survive 3+ generations will appear here.
        </p>
      </div>
    );
  }

  return (
    <div className={cn("border rounded-xl p-3 flex flex-col gap-2", className)}>
      <h3 className="text-sm font-semibold flex items-center gap-1.5">
        <Crown className="h-4 w-4 text-amber-500" />
        Elite Tracker
        <span className="text-xs text-muted-foreground font-normal">({elites.length} survivors)</span>
      </h3>

      <div className="space-y-1.5 max-h-[320px] overflow-y-auto">
        {elites.map((elite, i) => (
          <div
            key={i}
            className={cn(
              "border rounded-lg p-2 text-xs hover:bg-muted/50 transition",
              elite.survival_gens >= 8 ? "border-amber-500/40 bg-amber-500/5" : ""
            )}
          >
            {/* Formula (truncated) */}
            <code className="text-[11px] font-mono block truncate mb-1.5" title={elite.formula}>
              {elite.formula}
            </code>

            {/* Stats row */}
            <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
              <span className={cn(
                "flex items-center gap-0.5 font-semibold px-1.5 py-0.5 rounded",
                elite.survival_gens >= 8
                  ? "bg-amber-500/10 text-amber-600"
                  : elite.survival_gens >= 5
                    ? "bg-purple-500/10 text-purple-600"
                    : "bg-blue-500/10 text-blue-600"
              )}>
                <Clock className="h-2.5 w-2.5" />
                {elite.survival_gens} gens
              </span>
              <span className="flex items-center gap-0.5">
                <TrendingUp className="h-2.5 w-2.5" />
                IC: {elite.best_ic.toFixed(4)}
              </span>
              <span className="flex items-center gap-0.5">
                <Hash className="h-2.5 w-2.5" />
                Cplx: {elite.complexity}
              </span>
              <span className="ml-auto">
                G{elite.first_seen_gen}→G{elite.last_seen_gen}
              </span>
            </div>

            {/* Survival bar */}
            <div className="mt-1.5 w-full bg-muted rounded-full h-1 overflow-hidden">
              <div
                className={cn(
                  "h-full rounded-full transition-all",
                  elite.survival_gens >= 8 ? "bg-amber-500"
                    : elite.survival_gens >= 5 ? "bg-purple-500"
                      : "bg-blue-500"
                )}
                style={{ width: `${Math.min(100, (elite.survival_gens / 10) * 100)}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
