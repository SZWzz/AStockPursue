import { useEffect, useState } from "react";
import { RotateCcw, Clock, GitCommit } from "lucide-react";
import { useI18n } from "@/lib/i18n";
import { authHeaders } from "@/lib/apiAuth";

interface CommitEntry {
  commit_hash: string;
  timestamp: string;
  message: string;
}

interface HistoryPanelProps {
  indicatorId: string;
}

export function HistoryPanel({ indicatorId }: HistoryPanelProps) {
  const { t } = useI18n();
  const [entries, setEntries] = useState<CommitEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [rolling, setRolling] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadHistory = async () => {
    if (!indicatorId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/indicator-lab/${indicatorId}/history`, { headers: authHeaders() });
      const data = await res.json();
      setEntries(data.history || []);
    } catch {
      setError("Failed to load history");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadHistory();
  }, [indicatorId]);

  const handleRollback = async (hash: string) => {
    setRolling(hash);
    setError(null);
    try {
      const res = await fetch(
        `/indicator-lab/${indicatorId}/rollback?commit_hash=${hash}`,
        { method: "POST", headers: authHeaders() }
      );
      if (res.ok) {
        loadHistory();
        window.location.reload(); // Reload to show restored code
      } else {
        setError("Rollback failed");
      }
    } catch {
      setError("Rollback failed");
    } finally {
      setRolling(null);
    }
  };

  if (!indicatorId) {
    return (
      <div className="text-xs text-muted-foreground p-3 text-center">
        {t.indicatorLabNoHistory}
      </div>
    );
  }

  return (
    <div className="space-y-1">
      {/* Refresh */}
      <div className="flex items-center justify-between px-1 pb-2">
        <span className="text-xs text-muted-foreground flex items-center gap-1">
          <Clock className="h-3 w-3" />
          {t.indicatorLabVersionHistory}
        </span>
        <button
          onClick={loadHistory}
          disabled={loading}
          className="text-[10px] text-muted-foreground hover:text-foreground transition-colors"
        >
          {loading ? "..." : t.indicatorLabRefresh}
        </button>
      </div>

      {error && (
        <div className="px-2 py-1 text-[10px] text-danger bg-danger/5 rounded">
          {error}
        </div>
      )}

      {entries.length === 0 && !loading && (
        <div className="text-xs text-muted-foreground py-2 text-center">
          No history yet. Git tracking starts on first save.
        </div>
      )}

      {entries.map((entry) => (
        <div
          key={entry.commit_hash}
          className="flex items-start gap-2 px-2 py-1.5 rounded hover:bg-muted/50 transition-colors group"
        >
          <GitCommit className="h-3 w-3 text-muted-foreground mt-0.5 shrink-0" />
          <div className="min-w-0 flex-1">
            <div className="text-xs truncate">{entry.message}</div>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="text-[10px] text-muted-foreground font-mono">
                {entry.commit_hash}
              </span>
              <span className="text-[10px] text-muted-foreground/60">
                {entry.timestamp?.slice(0, 16).replace("T", " ")}
              </span>
            </div>
          </div>
          <button
            onClick={() => handleRollback(entry.commit_hash)}
            disabled={rolling === entry.commit_hash}
            className="p-1 opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-primary rounded transition-all shrink-0"
            title={t.indicatorLabRollback}
          >
            <RotateCcw className="h-3 w-3" />
          </button>
        </div>
      ))}
    </div>
  );
}
