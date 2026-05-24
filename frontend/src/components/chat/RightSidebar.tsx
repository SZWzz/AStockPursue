import { ChevronsRight, ChevronsLeft, Star, Lightbulb } from "lucide-react";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n";
import { WatchlistPanel } from "./WatchlistPanel";
import { ExamplePrompts } from "./ExamplePrompts";

interface RightSidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  onAnalyze: (prompt: string) => void;
  onSelectExample: (prompt: string) => void;
}

export function RightSidebar({ collapsed, onToggle, onAnalyze, onSelectExample }: RightSidebarProps) {
  const { t } = useI18n();
  return (
    <aside
      aria-label="Right sidebar"
      className={cn(
        "border-l bg-card flex flex-col shrink-0 transition-all duration-200 overflow-hidden",
        collapsed ? "w-0 border-l-0" : "w-72"
      )}
    >
      {/* Toggle + Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b shrink-0">
        <button
          onClick={onToggle}
          className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition"
          title={t.sidebarCollapse || "收起"}
          aria-label={t.sidebarCollapse || "Collapse sidebar"}
          aria-expanded={!collapsed}
        >
          <ChevronsRight className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Watchlist section */}
      <div className="flex flex-col flex-1 min-h-0">
        {/* Watchlist header */}
        <div className="flex items-center gap-1.5 px-3 py-1.5 border-b border-border/30 shrink-0">
          <Star className="h-3 w-3 text-primary" />
          <span className="text-xs font-semibold uppercase tracking-wider">{t.watchlist || "自选"}</span>
        </div>
        <div className="flex-1 min-h-0 flex flex-col">
          <WatchlistPanel collapsed={false} onAnalyze={onAnalyze} />
        </div>

        {/* Examples divider */}
        <div className="flex items-center gap-1.5 px-3 py-1.5 border-y border-border/30 shrink-0">
          <Lightbulb className="h-3 w-3 text-warning" />
          <span className="text-xs font-semibold uppercase tracking-wider">{t.tryExamples || "示例"}</span>
        </div>
        <ExamplePrompts onSelect={onSelectExample} />
      </div>

      {/* Collapsed toggle (shown when collapsed, outside sidebar) */}
      {collapsed && (
        <button
          onClick={onToggle}
          className="fixed right-0 top-1/2 -translate-y-1/2 z-40 p-1.5 rounded-lg rounded-l-md border border-r-0 bg-card text-muted-foreground hover:text-foreground hover:bg-muted transition shadow-sm"
          title="Expand sidebar"
          aria-label={t.sidebarExpand || "Expand sidebar"}
          aria-expanded={false}
        >
          <ChevronsLeft className="h-4 w-4" />
        </button>
      )}
    </aside>
  );
}
