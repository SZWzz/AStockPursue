import { useState, useMemo } from "react";
import { Search, ArrowRight, TrendingUp, Activity, Grid3X3, Shuffle, Layers, Gauge } from "lucide-react";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n";

export interface TemplateItem {
  key: string;
  name: string;
  description: string;
  category: string;
  difficulty: string;
  tags: string[];
}

interface TemplateBrowserProps {
  templates: TemplateItem[];
  onSelect: (template: TemplateItem) => void;
  loading?: boolean;
  emptyText?: string;
}

const CATEGORY_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  trend: TrendingUp,
  reversal: Activity,
  grid: Grid3X3,
  arbitrage: Shuffle,
  martingale: Layers,
  multiFactor: Gauge,
};

const DIFFICULTY_COLORS: Record<string, string> = {
  beginner: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  intermediate: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  advanced: "bg-rose-500/10 text-rose-400 border-rose-500/20",
};

export function TemplateBrowser({ templates, onSelect, loading, emptyText }: TemplateBrowserProps) {
  const { t } = useI18n();
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");

  const categories = useMemo(() => {
    const cats = new Set(templates.map((tpl) => tpl.category));
    return Array.from(cats).sort();
  }, [templates]);

  const filtered = useMemo(() => {
    return templates.filter((tpl) => {
      if (categoryFilter !== "all" && tpl.category !== categoryFilter) return false;
      if (search) {
        const q = search.toLowerCase();
        const matchName = tpl.name.toLowerCase().includes(q);
        const matchDesc = tpl.description.toLowerCase().includes(q);
        const matchTag = tpl.tags.some((tag) => tag.toLowerCase().includes(q));
        if (!matchName && !matchDesc && !matchTag) return false;
      }
      return true;
    });
  }, [templates, categoryFilter, search]);

  const getCategoryLabel = (cat: string): string => {
    const key = `strategyLabCategory_${cat}` as keyof typeof t;
    return (t as Record<string, string>)[key] || cat;
  };

  const getDifficultyLabel = (diff: string): string => {
    const key = `strategyLabDifficulty_${diff}` as keyof typeof t;
    return (t as Record<string, string>)[key] || diff;
  };

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

      {/* Category filter chips */}
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
        {categories.map((cat) => {
          const Icon = CATEGORY_ICONS[cat];
          return (
            <button
              key={cat}
              onClick={() => setCategoryFilter(cat)}
              className={cn(
                "flex items-center gap-1 px-2.5 py-1 text-xs rounded-full border transition-colors",
                categoryFilter === cat
                  ? "bg-primary/10 text-primary border-primary/30 font-medium"
                  : "text-muted-foreground border-border hover:border-muted-foreground/30"
              )}
            >
              {Icon && <Icon className="h-3 w-3" />}
              {getCategoryLabel(cat)}
            </button>
          );
        })}
      </div>

      {/* Template cards */}
      {filtered.length === 0 ? (
        <div className="text-sm text-muted-foreground text-center py-8">
          {emptyText || t.strategyLabNoTemplates}
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map((tpl) => {
            const Icon = CATEGORY_ICONS[tpl.category] || Activity;
            return (
              <div
                key={tpl.key}
                className="card p-3.5 hover:border-primary/30 hover:shadow-sm transition-all cursor-pointer group"
                onClick={() => onSelect(tpl)}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5">
                      <Icon className="h-3.5 w-3.5 text-primary shrink-0" />
                      <span className="text-sm font-medium truncate">{tpl.name}</span>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                      {tpl.description}
                    </p>
                    <div className="flex items-center gap-1.5 mt-2 flex-wrap">
                      <span
                        className={cn(
                          "px-2 py-0.5 text-xs rounded border",
                          DIFFICULTY_COLORS[tpl.difficulty] || "text-muted-foreground border-border"
                        )}
                      >
                        {getDifficultyLabel(tpl.difficulty)}
                      </span>
                      {tpl.tags.slice(0, 3).map((tag) => (
                        <span
                          key={tag}
                          className="px-2 py-0.5 text-xs rounded bg-muted text-muted-foreground"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>
                  <button
                    className="p-1.5 rounded-md text-muted-foreground opacity-0 group-hover:opacity-100 hover:text-primary hover:bg-primary/10 transition-all shrink-0"
                    title={t.strategyLabUseTemplate}
                  >
                    <ArrowRight className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
