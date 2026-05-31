import { cn } from "@/lib/utils";
import { ExpressionTreeViewer } from "./ExpressionTreeViewer";
import { Zap, TrendingUp, BarChart3, Hash } from "lucide-react";

interface LiveBestFactorProps {
  formula: string;
  expressionJson?: Record<string, unknown>;
  bestIc: number;
  complexity: number;
  generation: number;
  className?: string;
}

export function LiveBestFactor({
  formula,
  expressionJson,
  bestIc,
  complexity,
  generation,
  className,
}: LiveBestFactorProps) {
  if (!formula) {
    return (
      <div className={cn("border rounded-xl p-4", className)}>
        <h3 className="text-sm font-semibold mb-2 flex items-center gap-1.5">
          <Zap className="h-4 w-4 text-amber-500" />
          Best Factor
        </h3>
        <p className="text-xs text-muted-foreground">Waiting for first generation...</p>
      </div>
    );
  }

  return (
    <div className={cn("border rounded-xl p-3 flex flex-col gap-2", className)}>
      <h3 className="text-sm font-semibold flex items-center gap-1.5">
        <Zap className="h-4 w-4 text-amber-500" />
        Best Factor — Gen {generation}
      </h3>

      {/* Formula */}
      <div className="bg-muted/50 rounded-lg p-2">
        <code className="text-xs font-mono break-all leading-relaxed">{formula}</code>
      </div>

      {/* Expression Tree */}
      {expressionJson && (
        <div className="border rounded-lg p-2 bg-card">
          <ExpressionTreeViewer tree={expressionJson as any} />
        </div>
      )}

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-2 text-xs">
        <div className="flex items-center gap-1 bg-emerald-500/10 border border-emerald-500/20 rounded px-2 py-1">
          <TrendingUp className="h-3 w-3 text-emerald-500" />
          <span className="text-muted-foreground">IC</span>
          <span className={cn("font-mono font-semibold ml-auto", bestIc > 0 ? "text-emerald-600" : "text-red-500")}>
            {bestIc.toFixed(4)}
          </span>
        </div>
        <div className="flex items-center gap-1 bg-blue-500/10 border border-blue-500/20 rounded px-2 py-1">
          <Hash className="h-3 w-3 text-blue-500" />
          <span className="text-muted-foreground">Complexity</span>
          <span className="font-mono font-semibold ml-auto">{complexity}</span>
        </div>
        <div className="flex items-center gap-1 bg-purple-500/10 border border-purple-500/20 rounded px-2 py-1">
          <BarChart3 className="h-3 w-3 text-purple-500" />
          <span className="text-muted-foreground">Gen</span>
          <span className="font-mono font-semibold ml-auto">{generation}</span>
        </div>
      </div>
    </div>
  );
}
