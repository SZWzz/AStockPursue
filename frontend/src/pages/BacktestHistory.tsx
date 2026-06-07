import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { BacktestRunSummary } from "@/types/api";
import {
  Search, Trash2, Calendar,
  ArrowUpDown, Tag, BarChart3, RefreshCw, ChevronLeft, ChevronRight,
} from "lucide-react";

const PAGE_SIZE = 25;

type SortKey = "date" | "sharpe" | "return" | "drawdown" | "win_rate" | "trades";

const SORT_OPTIONS: { key: SortKey; label: string }[] = [
  { key: "date", label: "日期" },
  { key: "sharpe", label: "Sharpe" },
  { key: "return", label: "收益" },
  { key: "drawdown", label: "回撤" },
  { key: "win_rate", label: "胜率" },
  { key: "trades", label: "交易数" },
];

const PERF_COLORS: Record<string, string> = {
  excellent: "text-emerald-400",
  good: "text-green-500",
  positive: "text-muted-foreground",
  negative: "text-red-400",
};

export function BacktestHistory() {
  const navigate = useNavigate();
  const [runs, setRuns] = useState<BacktestRunSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [sortBy, setSortBy] = useState<SortKey>("date");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [search, setSearch] = useState("");
  const [tagFilter, setTagFilter] = useState("");
  const [page, setPage] = useState(0);
  const [total, setTotal] = useState(0);

  const loadRuns = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.listBacktestHistory(PAGE_SIZE, page * PAGE_SIZE);
      setRuns(data.runs || []);
      setTotal(data.total || 0);
    } catch {
      setRuns([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => {
    loadRuns();
  }, [loadRuns]);

  // Client-side filter + sort
  const filtered = runs
    .filter((r) => {
      if (search) {
        const q = search.toLowerCase();
        const nameMatch = (r.run_name || "").toLowerCase().includes(q);
        const typeMatch = (r.run_type || "").toLowerCase().includes(q);
        if (!nameMatch && !typeMatch) return false;
      }
      if (tagFilter) {
        const tags = r.tags || [];
        if (!tags.some((tg) => tg.toLowerCase().includes(tagFilter.toLowerCase()))) {
          return false;
        }
      }
      return true;
    })
    .sort((a, b) => {
      const m = sortDir === "asc" ? 1 : -1;
      const ma = a.metrics || {};
      const mb = b.metrics || {};
      switch (sortBy) {
        case "sharpe":
          return ((ma.sharpe_ratio || ma.sharpe || 0) - (mb.sharpe_ratio || mb.sharpe || 0)) * m;
        case "return":
          return ((ma.total_return || 0) - (mb.total_return || 0)) * m;
        case "drawdown":
          return ((mb.max_drawdown || 0) - (ma.max_drawdown || 0)) * m; // lower is better
        case "win_rate":
          return ((ma.win_rate || 0) - (mb.win_rate || 0)) * m;
        case "trades":
          return ((ma.trade_count || 0) - (mb.trade_count || 0)) * m;
        case "date":
        default:
          return (new Date(a.created_at).getTime() - new Date(b.created_at).getTime()) * m;
      }
    });

  const toggleSort = (key: SortKey) => {
    if (sortBy === key) {
      setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    } else {
      setSortBy(key);
      setSortDir("desc");
    }
  };

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("Delete this backtest run?")) return;
    try {
      await api.deleteBacktestHistory(id);
      loadRuns();
    } catch {
      // silently fail
    }
  };

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const getPerfTier = (r: BacktestRunSummary): string => {
    const s = r.metrics?.sharpe_ratio || r.metrics?.sharpe || 0;
    if (s >= 2) return "excellent";
    if (s >= 1) return "good";
    if (s >= 0) return "positive";
    return "negative";
  };

  return (
    <div className="flex flex-col h-full p-4 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold">回测历史</h1>
          <p className="text-xs text-muted-foreground">
            所有回测结果自动保存 · 共 {total} 条记录
          </p>
        </div>
        <button
          onClick={loadRuns}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border hover:bg-muted transition-colors"
        >
          <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} />
          刷新
        </button>
      </div>

      {/* Toolbar */}
      <div className="flex items-center gap-3">
        {/* Search */}
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <input
            type="text"
            placeholder="搜索名称/类型..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-7 pr-3 py-1.5 text-xs rounded-lg border bg-background focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>
        {/* Tag filter */}
        <div className="relative flex-1 max-w-[180px]">
          <Tag className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <input
            type="text"
            placeholder="标签筛选..."
            value={tagFilter}
            onChange={(e) => setTagFilter(e.target.value)}
            className="w-full pl-7 pr-3 py-1.5 text-xs rounded-lg border bg-background focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>
        {/* Sort */}
        <div className="flex items-center gap-1.5">
          <span className="text-[11px] text-muted-foreground">排序:</span>
          {SORT_OPTIONS.map((opt) => (
            <button
              key={opt.key}
              onClick={() => toggleSort(opt.key)}
              className={cn(
                "px-2 py-1 text-[11px] rounded-md transition-colors",
                sortBy === opt.key
                  ? "bg-primary/10 text-primary font-medium"
                  : "hover:bg-muted text-muted-foreground"
              )}
            >
              {opt.label}
              {sortBy === opt.key && (
                <ArrowUpDown className="inline-block ml-0.5 h-3 w-3" />
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto rounded-lg border">
        {loading ? (
          <div className="flex items-center justify-center h-48 text-muted-foreground text-sm">
            <RefreshCw className="animate-spin h-4 w-4 mr-2" />
            加载中...
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-muted-foreground text-sm space-y-2">
            <BarChart3 className="h-8 w-8 opacity-30" />
            <p>暂无回测记录</p>
            <p className="text-xs">运行任意回测后结果将自动出现在这里</p>
          </div>
        ) : (
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-muted/50 border-b">
              <tr>
                <th className="text-left px-3 py-2 font-medium text-muted-foreground">名称</th>
                <th className="text-left px-3 py-2 font-medium text-muted-foreground">类型</th>
                <th className="text-right px-3 py-2 font-medium text-muted-foreground">
                  <button onClick={() => toggleSort("date")} className="hover:text-foreground">
                    <Calendar className="inline h-3 w-3 mr-1" />
                    日期
                  </button>
                </th>
                <th className="text-right px-3 py-2 font-medium text-muted-foreground">
                  <button onClick={() => toggleSort("sharpe")} className="hover:text-foreground">Sharpe</button>
                </th>
                <th className="text-right px-3 py-2 font-medium text-muted-foreground">
                  <button onClick={() => toggleSort("return")} className="hover:text-foreground">年化收益</button>
                </th>
                <th className="text-right px-3 py-2 font-medium text-muted-foreground">
                  <button onClick={() => toggleSort("drawdown")} className="hover:text-foreground">最大回撤</button>
                </th>
                <th className="text-right px-3 py-2 font-medium text-muted-foreground">
                  <button onClick={() => toggleSort("win_rate")} className="hover:text-foreground">胜率</button>
                </th>
                <th className="text-right px-3 py-2 font-medium text-muted-foreground">
                  <button onClick={() => toggleSort("trades")} className="hover:text-foreground">交易数</button>
                </th>
                <th className="text-left px-3 py-2 font-medium text-muted-foreground">标签</th>
                <th className="w-10"></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((run) => {
                const m = run.metrics || {};
                const sharpe = m.sharpe_ratio || m.sharpe || 0;
                const tier = getPerfTier(run);
                return (
                  <tr
                    key={run.id}
                    onClick={() => navigate(`/runs/${run.id}`)}
                    className="border-b hover:bg-muted/30 cursor-pointer transition-colors"
                  >
                    <td className="px-3 py-2 font-medium truncate max-w-[180px]">
                      {run.run_name || "(未命名)"}
                    </td>
                    <td className="px-3 py-2 text-muted-foreground">{run.run_type}</td>
                    <td className="px-3 py-2 text-right text-muted-foreground whitespace-nowrap">
                      {run.created_at?.slice(0, 10)}
                    </td>
                    <td className={cn("px-3 py-2 text-right tabular-nums", PERF_COLORS[tier])}>
                      {sharpe.toFixed(2)}
                    </td>
                    <td className={cn(
                      "px-3 py-2 text-right tabular-nums",
                      (m.annual_return || m.total_return || 0) >= 0 ? "text-up" : "text-down"
                    )}>
                      {((m.annual_return || m.total_return || 0) * 100).toFixed(1)}%
                    </td>
                    <td className="px-3 py-2 text-right text-down tabular-nums">
                      {((m.max_drawdown || 0) * 100).toFixed(1)}%
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">
                      {((m.win_rate || 0) * 100).toFixed(1)}%
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums text-muted-foreground">
                      {m.trade_count || 0}
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex gap-1 flex-wrap max-w-[200px]">
                        {(run.tags || []).slice(0, 4).map((tg) => (
                          <span
                            key={tg}
                            onClick={(e) => {
                              e.stopPropagation();
                              setTagFilter(tg);
                            }}
                            className="px-1.5 py-0.5 text-[10px] rounded bg-muted text-muted-foreground hover:bg-primary/10 hover:text-primary cursor-pointer transition-colors"
                          >
                            {tg}
                          </span>
                        ))}
                        {(run.tags || []).length > 4 && (
                          <span className="text-[10px] text-muted-foreground">
                            +{(run.tags || []).length - 4}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-2 py-2">
                      <button
                        onClick={(e) => handleDelete(run.id, e)}
                        className="p-1 rounded hover:bg-red-500/10 hover:text-red-400 transition-colors"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-3 text-xs">
          <button
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            className="p-1 rounded hover:bg-muted disabled:opacity-30"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <span className="text-muted-foreground">
            {page + 1} / {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1}
            className="p-1 rounded hover:bg-muted disabled:opacity-30"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      )}
    </div>
  );
}
