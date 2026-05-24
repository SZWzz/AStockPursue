import { useState, useMemo } from "react";
import { Search, ArrowRight, Code } from "lucide-react";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n";

export interface BuiltinIndicator {
  key: string;
  name: string;
  description: string;
  category: string;
  code: string;
}

interface BuiltinIndicatorsProps {
  indicators: BuiltinIndicator[];
  onSelect: (indicator: BuiltinIndicator) => void;
  loading?: boolean;
}

const CATEGORY_COLORS: Record<string, string> = {
  trend: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  momentum: "bg-purple-500/10 text-purple-400 border-purple-500/20",
  volatility: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  volume: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  pattern: "bg-rose-500/10 text-rose-400 border-rose-500/20",
  multi: "bg-cyan-500/10 text-cyan-400 border-cyan-500/20",
};

export function BuiltinIndicators({ indicators, onSelect, loading }: BuiltinIndicatorsProps) {
  const { t } = useI18n();
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");

  const categories = useMemo(() => {
    const cats = new Set(indicators.map((ind) => ind.category));
    return Array.from(cats).sort();
  }, [indicators]);

  const filtered = useMemo(() => {
    return indicators.filter((ind) => {
      if (categoryFilter !== "all" && ind.category !== categoryFilter) return false;
      if (search) {
        const q = search.toLowerCase();
        if (!ind.name.toLowerCase().includes(q) && !ind.description.toLowerCase().includes(q)) {
          return false;
        }
      }
      return true;
    });
  }, [indicators, categoryFilter, search]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="animate-spin h-4 w-4 border-2 border-primary border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Search */}
      <div className="relative">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
        <input
          type="text"
          placeholder={t.azFilterPlaceholder}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full text-sm rounded-lg border border-border bg-background pl-7 pr-3 py-2 focus:outline-none focus:border-primary/50 transition-all duration-150"
        />
      </div>

      {/* Category chips */}
      <div className="flex flex-wrap gap-1.5">
        <button
          onClick={() => setCategoryFilter("all")}
          className={cn(
            "px-2.5 py-1 text-xs rounded-full border transition-colors",
            categoryFilter === "all"
              ? "bg-primary/10 text-primary border-primary/30 font-medium"
              : "text-muted-foreground border-border hover:border-muted-foreground/30"
          )}
        >
          {t.strategyLabAllCategories}
        </button>
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => setCategoryFilter(cat)}
            className={cn(
              "px-2.5 py-1 text-xs rounded-full border capitalize transition-colors",
              categoryFilter === cat
                ? "bg-primary/10 text-primary border-primary/30 font-medium"
                : "text-muted-foreground border-border hover:border-muted-foreground/30"
            )}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* Indicator list */}
      {filtered.length === 0 ? (
        <div className="text-sm text-muted-foreground text-center py-8">
          {t.indicatorLabNoBuiltins}
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map((ind) => (
            <div
              key={ind.key}
              className="card p-3 hover:border-primary/30 hover:shadow-sm transition-all cursor-pointer group"
              onClick={() => onSelect(ind)}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5">
                    <Code className="h-3.5 w-3.5 text-primary shrink-0" />
                    <span className="text-sm font-medium truncate">{ind.name}</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                    {ind.description}
                  </p>
                  <span
                    className={cn(
                      "inline-block mt-2 px-2 py-0.5 text-xs rounded border capitalize",
                      CATEGORY_COLORS[ind.category] || "text-muted-foreground border-border"
                    )}
                  >
                    {ind.category}
                  </span>
                </div>
                <button
                  className="p-1.5 rounded-md text-muted-foreground opacity-0 group-hover:opacity-100 hover:text-primary hover:bg-primary/10 transition-all shrink-0"
                  title={t.indicatorLabUseBuiltin}
                >
                  <ArrowRight className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
