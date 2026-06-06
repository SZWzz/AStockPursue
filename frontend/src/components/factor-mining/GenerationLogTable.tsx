import { useState } from "react";
import { cn } from "@/lib/utils";
import type { GenerationSnapshot } from "@/types/api";
import { ExpressionTreeViewer } from "./ExpressionTreeViewer";
import { ChevronDown, ChevronRight, TrendingUp } from "lucide-react";

interface Props {
  generations: GenerationSnapshot[];
  className?: string;
}

export function GenerationLogTable({ generations, className }: Props) {
  const [expandedGen, setExpandedGen] = useState<number | null>(null);

  if (generations.length === 0) {
    return (
      <div className={cn("border rounded-xl p-3", className)}>
        <h3 className="text-sm font-semibold mb-2">Generation Log</h3>
        <p className="text-xs text-muted-foreground">
          Start an evolution run to see per-generation details.
        </p>
      </div>
    );
  }

  // Show most recent generations first (reversed)
  const recent = [...generations].reverse().slice(0, 20);

  return (
    <div className={cn("border rounded-xl flex flex-col", className)}>
      <div className="px-3 py-1.5 border-b bg-muted/30 text-xs font-medium flex items-center gap-2">
        <TrendingUp className="h-3 w-3" />
        Generation Log
        <span className="text-muted-foreground font-normal">
          ({generations.length} generations)
        </span>
      </div>
      <div className="overflow-auto flex-1" style={{ maxHeight: 400 }}>
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-card border-b z-10">
            <tr className="text-muted-foreground">
              <th className="text-left py-1.5 px-2 w-8"></th>
              <th className="text-right py-1.5 px-2">Gen</th>
              <th className="text-right py-1.5 px-2">Best IC</th>
              <th className="text-right py-1.5 px-2">Mean Fit</th>
              <th className="text-right py-1.5 px-2">Diversity</th>
              <th className="text-right py-1.5 px-2">Time</th>
              <th className="text-left py-1.5 px-2">Best Formula</th>
            </tr>
          </thead>
          <tbody>
            {recent.map((g) => (
              <>
                <tr
                  key={g.generation}
                  className={cn(
                    "border-b hover:bg-muted/50 cursor-pointer transition",
                    expandedGen === g.generation && "bg-muted/30"
                  )}
                  onClick={() => setExpandedGen(expandedGen === g.generation ? null : g.generation)}
                >
                  <td className="py-1 px-2 text-center">
                    {expandedGen === g.generation ? (
                      <ChevronDown className="h-3 w-3 inline" />
                    ) : (
                      <ChevronRight className="h-3 w-3 inline" />
                    )}
                  </td>
                  <td className="py-1 px-2 text-right font-mono font-medium">{g.generation}</td>
                  <td className={cn("py-1 px-2 text-right font-mono", g.best_ic > 0 ? "text-up" : "text-down")}>
                    {g.best_ic.toFixed(4)}
                  </td>
                  <td className="py-1 px-2 text-right font-mono">{g.mean_fitness.toFixed(4)}</td>
                  <td className="py-1 px-2 text-right font-mono text-muted-foreground">{g.diversity.toFixed(4)}</td>
                  <td className="py-1 px-2 text-right font-mono text-muted-foreground">
                    {g.gen_seconds ? `${g.gen_seconds.toFixed(1)}s` : "-"}
                  </td>
                  <td className="py-1 px-2 font-mono text-[10px] max-w-[250px] truncate" title={g.best_formula}>
                    {g.best_formula || "-"}
                  </td>
                </tr>
                {expandedGen === g.generation && g.best_expression_json && (
                  <tr key={`${g.generation}-expanded`} className="bg-muted/20">
                    <td colSpan={7} className="py-2 px-4">
                      <div className="flex gap-4">
                        <div className="flex-1">
                          <div className="text-[10px] text-muted-foreground mb-1">Expression Tree</div>
                          <ExpressionTreeViewer tree={g.best_expression_json as any} />
                        </div>
                        <div className="w-48 shrink-0 space-y-1 text-[10px]">
                          <div className="font-medium text-muted-foreground">Stats</div>
                          <div className="flex justify-between">
                            <span>Best Fitness</span>
                            <span className="font-mono">{g.best_fitness.toFixed(4)}</span>
                          </div>
                          <div className="flex justify-between">
                            <span>Std Fitness</span>
                            <span className="font-mono">{g.std_fitness.toFixed(4)}</span>
                          </div>
                          <div className="flex justify-between">
                            <span>Complexity</span>
                            <span className="font-mono">{g.best_complexity || "-"}</span>
                          </div>
                          <div className="flex justify-between">
                            <span>Data Source</span>
                            <span className={cn("font-mono", g.data_source === "real" ? "text-up" : "text-amber-600")}>
                              {g.data_source || "-"}
                            </span>
                          </div>
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
