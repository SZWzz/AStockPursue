import { useEffect, useState, useCallback } from "react";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { Store, Download, Star, Search, TrendingUp } from "lucide-react";

interface Strategy {
  id: string;
  title: string;
  description: string;
  market: string;
  category: string;
  tags: string[];
  backtest_sharpe?: number;
  backtest_return?: number;
  installs_count: number;
  rating_avg: number;
  rating_count: number;
  created_at: string;
}

const MARKETS: Record<string, string> = { equity_cn: "A-Share", equity_us: "US", equity_hk: "HK", crypto: "Crypto" };
const CATEGORIES = ["trend", "reversal", "grid", "arbitrage", "multiFactor"];

export function Marketplace() {
  const { t } = useI18n();
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [loading, setLoading] = useState(false);
  const [market, setMarket] = useState("");
  const [category, setCategory] = useState("");
  const [sort, setSort] = useState("rating");
  const [search, setSearch] = useState("");
  const [detail, setDetail] = useState<Strategy | null>(null);
  const [code, setCode] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await (api as any).browseMarketplace({ market, category, sort, limit: 30 });
      setStrategies(data?.strategies || []);
    } catch { setStrategies([]); }
    setLoading(false);
  }, [market, category, sort]);

  useEffect(() => { load(); }, [load]);

  const handleInstall = async (id: string) => {
    try {
      await (api as any).installMarketplaceStrategy(id);
      setStrategies((prev) => prev.map((s) => s.id === id ? { ...s, installs_count: s.installs_count + 1 } : s));
    } catch { /* ignore */ }
  };

  const handleRate = async (id: string, rating: number) => {
    try {
      await (api as any).rateMarketplaceStrategy(id, { rating });
      load();
    } catch { /* ignore */ }
  };

  const handleView = async (id: string) => {
    try {
      const data = await (api as any).getMarketplaceStrategy(id);
      setDetail(data);
      setCode(data?.code || "");
    } catch { /* ignore */ }
  };

  const filtered = strategies.filter((s) => !search || s.title.toLowerCase().includes(search.toLowerCase()) || s.description.toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="flex flex-col h-full p-4 gap-3">
      <h1 className="text-lg font-bold flex items-center gap-2"><Store className="h-5 w-5" />{t.marketplace || "Strategy Marketplace"}</h1>

      {/* Filters */}
      <div className="flex items-center gap-2 text-xs">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search strategies..."
            className="w-full border rounded pl-7 pr-2 py-1.5 bg-background" />
        </div>
        <select value={market} onChange={(e) => setMarket(e.target.value)} className="border rounded px-2 py-1.5 bg-background">
          <option value="">All Markets</option>
          {Object.entries(MARKETS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <select value={category} onChange={(e) => setCategory(e.target.value)} className="border rounded px-2 py-1.5 bg-background">
          <option value="">All Categories</option>
          {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <select value={sort} onChange={(e) => setSort(e.target.value)} className="border rounded px-2 py-1.5 bg-background">
          <option value="rating">Top Rated</option>
          <option value="installs">Most Installed</option>
          <option value="newest">Newest</option>
        </select>
      </div>

      {/* Grid */}
      <div className="flex-1 overflow-auto">
        {loading ? <div className="text-center text-muted-foreground py-8">Loading...</div> :
          filtered.length === 0 ? <div className="text-center text-muted-foreground py-8">No strategies found</div> :
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {filtered.map((s) => (
                <div key={s.id} className="border rounded-xl p-3 hover:border-primary/30 transition cursor-pointer space-y-2" onClick={() => handleView(s.id)}>
                  <div className="flex items-start justify-between">
                    <h3 className="text-sm font-semibold truncate">{s.title}</h3>
                    <div className="flex items-center gap-0.5 text-amber-500 text-xs shrink-0">
                      <Star className="h-3 w-3 fill-amber-500" />{s.rating_avg?.toFixed?.(1) || "—"} ({s.rating_count})
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground line-clamp-2">{s.description || "No description"}</p>
                  <div className="flex items-center gap-2 text-[10px]">
                    <span className="px-1.5 py-0.5 rounded bg-muted">{MARKETS[s.market] || s.market}</span>
                    <span className="px-1.5 py-0.5 rounded bg-muted">{s.category}</span>
                    {s.backtest_sharpe != null && (
                      <span className={cn("px-1.5 py-0.5 rounded", s.backtest_sharpe > 1 ? "bg-success/10 text-success" : "bg-muted")}>
                        Sharpe {s.backtest_sharpe?.toFixed?.(2)}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
                    <TrendingUp className="h-3 w-3" />{s.installs_count} installs
                    {s.tags?.slice(0, 3).map((tag) => <span key={tag} className="text-[10px] text-muted-foreground">#{tag}</span>)}
                  </div>
                </div>
              ))}
            </div>}
      </div>

      {/* Detail modal */}
      {detail && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setDetail(null)}>
          <div className="bg-card border rounded-2xl w-full max-w-2xl max-h-[85vh] overflow-y-auto p-5 space-y-4" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-bold">{detail.title}</h2>
            <p className="text-sm text-muted-foreground">{detail.description}</p>
            <div className="flex gap-2 text-xs">
              <span>Market: {MARKETS[detail.market] || detail.market}</span>
              <span>Category: {detail.category}</span>
              {detail.backtest_sharpe != null && <span>Sharpe: {detail.backtest_sharpe?.toFixed?.(2)}</span>}
              {detail.backtest_return != null && <span>Return: {(detail.backtest_return * 100)?.toFixed?.(1)}%</span>}
            </div>

            {/* Code preview */}
            <pre className="bg-muted rounded-lg p-3 text-xs font-mono max-h-60 overflow-auto">{code.slice(0, 3000)}{code.length > 3000 ? "\n... (truncated)" : ""}</pre>

            {/* Rating */}
            <div className="flex items-center gap-1">
              <span className="text-xs text-muted-foreground">Rate:</span>
              {[1, 2, 3, 4, 5].map((r) => (
                <button key={r} onClick={() => handleRate(detail.id, r)}
                  className={cn("p-0.5", r <= (detail.rating_avg || 0) ? "text-amber-500" : "text-muted-foreground hover:text-amber-500")}>
                  <Star className={cn("h-4 w-4", r <= (detail.rating_avg || 0) ? "fill-amber-500" : "")} />
                </button>
              ))}
              <span className="text-xs text-muted-foreground ml-1">{detail.rating_avg?.toFixed?.(1)} ({detail.rating_count} ratings)</span>
            </div>

            <div className="flex gap-2">
              <button onClick={() => handleInstall(detail.id)}
                className="flex items-center gap-1 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium">
                <Download className="h-4 w-4" />{t.marketplaceInstall || "Install to Strategy Lab"}
              </button>
              <button onClick={() => setDetail(null)} className="px-4 py-2 border rounded-lg text-sm hover:bg-muted">Close</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
