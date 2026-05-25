import { useState, useEffect } from "react";
import { Search, ArrowRight, Layers, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n";
import { authHeaders } from "@/lib/apiAuth";

interface AlphaItem {
  id: string;
  zoo: string;
  nickname: string;
  theme: string[];
  formula_latex?: string;
}

interface AlphaZooBrowserProps {
  onSelect: (code: string, name: string) => void;
}

export function AlphaZooBrowser({ onSelect }: AlphaZooBrowserProps) {
  const { t } = useI18n();
  const [alphas, setAlphas] = useState<AlphaItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [converting, setConverting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(authHeaders() as Record<string, string>),
    };
    fetch("/v1/indicator-lab/alpha/list?limit=100", { headers })
      .then((res) => res.json())
      .then((data) => setAlphas(data.alphas || []))
      .catch(() => setError("Failed to load alphas"))
      .finally(() => setLoading(false));
  }, []);

  const handleSelect = async (alpha: AlphaItem) => {
    setConverting(alpha.id);
    setError(null);
    try {
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
        ...(authHeaders() as Record<string, string>),
      };
      const res = await fetch(`/v1/indicator-lab/alpha/${encodeURIComponent(alpha.id)}/convert`, { headers });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      onSelect(data.code, data.nickname);
    } catch (e) {
      setError(`Failed to convert: ${e}`);
    } finally {
      setConverting(null);
    }
  };

  const filtered = alphas.filter((a) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      a.nickname.toLowerCase().includes(q) ||
      a.id.toLowerCase().includes(q) ||
      a.zoo.toLowerCase().includes(q) ||
      a.theme.some((t) => t.toLowerCase().includes(q))
    );
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-5 w-5 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="relative">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
        <input
          type="text"
          placeholder={t.azFilterPlaceholder || "Search alphas..."}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full text-sm rounded-lg border border-border bg-background pl-7 pr-3 py-2 focus:outline-none focus:border-primary/50 transition-all duration-150"
        />
      </div>

      {error && (
        <div className="px-3 py-2 text-xs rounded-lg bg-danger/10 text-danger">{error}</div>
      )}

      {filtered.length === 0 ? (
        <div className="text-sm text-muted-foreground text-center py-8">
          No alpha factors found
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map((alpha) => (
            <div
              key={alpha.id}
              className="card p-3 hover:border-primary/30 hover:shadow-sm transition-all cursor-pointer group"
              onClick={() => handleSelect(alpha)}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5">
                    <Layers className="h-3.5 w-3.5 text-primary shrink-0" />
                    <span className="text-sm font-medium truncate">{alpha.nickname}</span>
                  </div>
                  <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
                    <span className="px-1.5 py-0.5 text-xs rounded bg-muted text-muted-foreground font-mono">
                      {alpha.id}
                    </span>
                    {alpha.theme.slice(0, 2).map((th) => (
                      <span key={th} className="px-1.5 py-0.5 text-xs rounded bg-primary/10 text-primary capitalize">
                        {th}
                      </span>
                    ))}
                  </div>
                  {alpha.formula_latex && (
                    <p className="text-xs text-muted-foreground mt-1.5 truncate font-mono">
                      {alpha.formula_latex}
                    </p>
                  )}
                </div>
                <button
                  className={cn(
                    "p-1.5 rounded-md transition-all shrink-0",
                    converting === alpha.id
                      ? "text-primary"
                      : "text-muted-foreground opacity-0 group-hover:opacity-100 hover:text-primary hover:bg-primary/10"
                  )}
                  disabled={converting === alpha.id}
                  title="Load into editor"
                >
                  {converting === alpha.id ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <ArrowRight className="h-3.5 w-3.5" />
                  )}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
