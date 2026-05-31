import { useState, useEffect, useCallback } from "react";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";

interface VersionSummary {
  id: string;
  version_num: number;
  title: string;
  change_note: string;
  code_size: number;
  created_at: string;
}

interface VersionDetail extends VersionSummary {
  code: string;
  diff_prev: string;
}

interface Props {
  strategyId: number | null;
  currentCode?: string;
  onRevert?: (code: string) => void;
  className?: string;
}

export function VersionDiffViewer({ strategyId, onRevert, className }: Props) {
  const [versions, setVersions] = useState<VersionSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<VersionDetail | null>(null);
  const [diffMode, setDiffMode] = useState<"prev" | "compare">("prev");
  const [compareA, setCompareA] = useState<number | null>(null);
  const [compareB, setCompareB] = useState<number | null>(null);
  const [compareDiff, setCompareDiff] = useState("");
  const [reverting, setReverting] = useState(false);

  const loadVersions = useCallback(async () => {
    if (!strategyId) return;
    setLoading(true);
    try {
      const data = await (api as any).listStrategyVersions(strategyId);
      setVersions(data || []);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [strategyId]);

  useEffect(() => {
    loadVersions();
  }, [loadVersions]);

  const loadVersionDetail = async (versionNum: number) => {
    if (!strategyId) return;
    try {
      const data = await (api as any).getStrategyVersion(strategyId, versionNum);
      setSelected(data);
    } catch {
      // ignore
    }
  };

  const loadCompareDiff = async () => {
    if (!strategyId || compareA == null || compareB == null) return;
    try {
      const data = await (api as any).getStrategyVersionDiff(strategyId, compareA, compareB);
      setCompareDiff(data?.diff || "");
    } catch {
      setCompareDiff("");
    }
  };

  const handleRevert = async (versionNum: number) => {
    if (!strategyId || reverting) return;
    setReverting(true);
    try {
      const data = await (api as any).revertStrategyVersion(strategyId, versionNum);
      const detail = await (api as any).getStrategyVersion(strategyId, data.version_num);
      if (detail?.code && onRevert) {
        onRevert(detail.code);
      }
      await loadVersions();
    } catch {
      // ignore
    } finally {
      setReverting(false);
    }
  };

  // Render diff lines with coloring
  const renderDiff = (diff: string) => {
    if (!diff) return <p className="text-xs text-muted-foreground p-2">No changes</p>;
    return (
      <pre className="text-xs font-mono p-2 overflow-x-auto max-h-96 overflow-y-auto bg-muted rounded">
        {diff.split("\n").map((line, i) => {
          let lineClass = "";
          if (line.startsWith("+") && !line.startsWith("+++")) lineClass = "text-success bg-success/5";
          else if (line.startsWith("-") && !line.startsWith("---")) lineClass = "text-destructive bg-destructive/5";
          else if (line.startsWith("@@")) lineClass = "text-primary font-semibold";
          return <div key={i} className={lineClass}>{line}</div>;
        })}
      </pre>
    );
  };

  if (!strategyId) {
    return <div className={cn("text-xs text-muted-foreground p-3", className)}>Select a strategy to view versions.</div>;
  }

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-semibold">Version History ({versions.length})</h4>
        <button onClick={loadVersions} disabled={loading} className="px-2 py-0.5 text-xs rounded bg-muted hover:bg-muted/70">
          {loading ? "Loading..." : "Refresh"}
        </button>
      </div>

      {/* Version list */}
      <div className="max-h-48 overflow-y-auto border rounded">
        {versions.length === 0 && (
          <p className="text-xs text-muted-foreground p-2">No versions yet. Save your strategy to create the first version.</p>
        )}
        {versions.map((v) => (
          <div
            key={v.id}
            onClick={() => loadVersionDetail(v.version_num)}
            className={cn(
              "flex items-center justify-between px-2 py-1.5 text-xs cursor-pointer border-b hover:bg-muted/50 transition",
              selected?.version_num === v.version_num && "bg-primary/5 border-primary/20"
            )}
          >
            <div>
              <span className="font-medium">v{v.version_num}</span>
              <span className="text-muted-foreground ml-2">{v.title}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-muted-foreground">{v.code_size}B</span>
              <span className="text-[10px] text-muted-foreground">
                {v.created_at ? new Date(v.created_at).toLocaleDateString() : ""}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Diff view */}
      {selected && (
        <div className="border rounded p-2">
          <div className="flex gap-2 mb-2 text-xs">
            <button
              onClick={() => setDiffMode("prev")}
              className={cn("px-2 py-0.5 rounded", diffMode === "prev" ? "bg-primary text-primary-foreground" : "bg-muted")}
            >
              Diff vs Previous
            </button>
            <button
              onClick={() => setDiffMode("compare")}
              className={cn("px-2 py-0.5 rounded", diffMode === "compare" ? "bg-primary text-primary-foreground" : "bg-muted")}
            >
              Compare Versions
            </button>
            <div className="flex-1" />
            <button
              onClick={() => handleRevert(selected.version_num)}
              disabled={reverting}
              className="px-2 py-0.5 rounded bg-destructive/10 text-destructive hover:bg-destructive/20 disabled:opacity-50"
            >
              {reverting ? "Reverting..." : `Revert to v${selected.version_num}`}
            </button>
          </div>

          {diffMode === "prev" && renderDiff(selected.diff_prev)}
          {diffMode === "compare" && (
            <div className="flex flex-col gap-2">
              <div className="flex gap-2 items-center text-xs">
                <select
                  value={compareA ?? ""}
                  onChange={(e) => setCompareA(e.target.value ? +e.target.value : null)}
                  className="border rounded px-1 py-0.5 bg-background"
                >
                  <option value="">Select version A</option>
                  {versions.map((v) => (
                    <option key={v.id} value={v.version_num}>v{v.version_num} - {v.title}</option>
                  ))}
                </select>
                <span className="text-muted-foreground">vs</span>
                <select
                  value={compareB ?? ""}
                  onChange={(e) => setCompareB(e.target.value ? +e.target.value : null)}
                  className="border rounded px-1 py-0.5 bg-background"
                >
                  <option value="">Select version B</option>
                  {versions.map((v) => (
                    <option key={v.id} value={v.version_num}>v{v.version_num} - {v.title}</option>
                  ))}
                </select>
                <button
                  onClick={loadCompareDiff}
                  disabled={compareA == null || compareB == null}
                  className="px-2 py-0.5 rounded bg-primary text-primary-foreground text-xs disabled:opacity-50"
                >
                  Compare
                </button>
              </div>
              {compareDiff && renderDiff(compareDiff)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
