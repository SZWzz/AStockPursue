import { cn } from "@/lib/utils";
import type { FactorCandidate } from "@/types/api";

interface Props {
  candidates: FactorCandidate[];
  loading: boolean;
  onValidate: (id: string) => void;
  onPromote: (id: string) => void;
  onDelete: (id: string) => void;
  className?: string;
}

export function CandidatesTable({ candidates, loading, onValidate, onPromote, onDelete, className }: Props) {
  if (loading) {
    return (
      <div className={cn("text-xs text-muted-foreground py-4 text-center", className)}>
        Loading candidates...
      </div>
    );
  }

  if (candidates.length === 0) {
    return (
      <div className={cn("text-xs text-muted-foreground py-4 text-center", className)}>
        No candidates yet. Run a GP or LLM mining job to discover factors.
      </div>
    );
  }

  return (
    <div className={cn("overflow-x-auto", className)}>
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b text-muted-foreground">
            <th className="text-left py-2 px-2 font-medium">Name</th>
            <th className="text-left py-2 px-2 font-medium">Formula</th>
            <th className="text-right py-2 px-2 font-medium">Train IC</th>
            <th className="text-right py-2 px-2 font-medium">Test IC</th>
            <th className="text-right py-2 px-2 font-medium">Test IR</th>
            <th className="text-center py-2 px-2 font-medium">Complexity</th>
            <th className="text-center py-2 px-2 font-medium">Status</th>
            <th className="text-center py-2 px-2 font-medium">Actions</th>
          </tr>
        </thead>
        <tbody>
          {candidates.map((c) => (
            <tr key={c.id} className="border-b hover:bg-muted/50">
              <td className="py-1.5 px-2 font-medium">{c.name || c.id?.slice(0, 8)}</td>
              <td className="py-1.5 px-2 font-mono text-[11px] max-w-[300px] truncate" title={c.formula}>
                {c.formula}
              </td>
              <td className={cn("py-1.5 px-2 text-right", (c.train_ic || 0) > 0 ? "text-success" : "text-destructive")}>
                {(c.train_ic || 0).toFixed(4)}
              </td>
              <td className={cn("py-1.5 px-2 text-right", (c.test_ic || 0) > 0 ? "text-success" : "text-destructive")}>
                {(c.test_ic || 0).toFixed(4)}
              </td>
              <td className="py-1.5 px-2 text-right">{(c.test_ir || 0).toFixed(2)}</td>
              <td className="py-1.5 px-2 text-center">
                <span className={cn("px-1.5 py-0.5 rounded text-[10px]", c.complexity <= 10 ? "bg-success/10 text-success" : c.complexity <= 25 ? "bg-warning/10 text-warning" : "bg-destructive/10 text-destructive")}>
                  {c.complexity || 0}
                </span>
              </td>
              <td className="py-1.5 px-2 text-center">
                {c.is_promoted ? (
                  <span className="text-success text-[10px]">Promoted</span>
                ) : (
                  <span className="text-muted-foreground text-[10px]">Pending</span>
                )}
              </td>
              <td className="py-1.5 px-2">
                <div className="flex gap-1 justify-center">
                  <button onClick={() => onValidate(c.id)} className="px-2 py-0.5 rounded bg-muted hover:bg-muted/70 text-[10px]">
                    Validate
                  </button>
                  {!c.is_promoted && (
                    <button onClick={() => onPromote(c.id)} className="px-2 py-0.5 rounded bg-primary/10 hover:bg-primary/20 text-primary text-[10px]">
                      Promote
                    </button>
                  )}
                  <button onClick={() => onDelete(c.id)} className="px-2 py-0.5 rounded bg-destructive/10 hover:bg-destructive/20 text-destructive text-[10px]">
                    Del
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
