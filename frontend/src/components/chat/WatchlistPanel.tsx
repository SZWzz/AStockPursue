import { useCallback, useEffect, useState } from "react";
import { Plus, RefreshCw, X, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n";
import { authHeaders } from "@/lib/apiAuth";

interface WatchlistItem {
  id: number;
  symbol: string;
  name: string;
  market: string;
}

interface PriceInfo {
  price: number;
  change_pct: number;
  name: string;
  error?: string;
}

interface WatchlistPanelProps {
  collapsed: boolean;
  onAnalyze: (prompt: string) => void;
}

export function WatchlistPanel({ collapsed, onAnalyze }: WatchlistPanelProps) {
  const { t } = useI18n();
  const [symbols, setSymbols] = useState<WatchlistItem[]>([]);
  const [prices, setPrices] = useState<Record<string, PriceInfo>>({});
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const loadWatchlist = useCallback(async () => {
    try {
      const res = await fetch("/v1/api/watchlist", { headers: authHeaders() });
      const data = await res.json();
      setSymbols(data.symbols || []);
    } catch { /* ignore */ }
  }, []);

  const loadPrices = useCallback(async () => {
    try {
      const res = await fetch("/v1/api/watchlist/prices", { headers: authHeaders() });
      const data = await res.json();
      setPrices(data.prices || {});
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { loadWatchlist(); }, [loadWatchlist]);
  useEffect(() => { if (symbols.length > 0) loadPrices(); }, [symbols.length, loadPrices]);

  const addSymbol = async () => {
    const s = input.trim().toUpperCase();
    if (!s) return;
    setLoading(true);
    try {
      await fetch("/v1/api/watchlist", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ symbol: s }),
      });
      setInput("");
      await loadWatchlist();
      // Fetch price for new symbol immediately
      setTimeout(() => loadPrices(), 500);
    } catch { /* ignore */ }
    setLoading(false);
  };

  const removeSymbol = async (symbol: string) => {
    await fetch(`/v1/api/watchlist/${symbol}`, { method: "DELETE", headers: authHeaders() });
    loadWatchlist();
  };

  const fmtPrice = (p: number) => {
    if (!p) return "—";
    return p >= 100 ? p.toFixed(2) : p >= 1 ? p.toFixed(4) : p.toFixed(6);
  };

  if (collapsed) return null;

  return (
    <div className="flex flex-col flex-1 min-h-0">
      {/* Add input */}
      <form
        onSubmit={(e) => { e.preventDefault(); addSymbol(); }}
        className="flex gap-1 px-3 py-2 border-b shrink-0"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={t.watchlistPlaceholder || "600519, AAPL..."}
          className="flex-1 min-w-0 rounded border bg-background px-2 py-1 text-[11px] outline-none focus:border-primary"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="p-1 rounded text-muted-foreground hover:text-primary hover:bg-primary/10 transition disabled:opacity-50"
        >
          <Plus className="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          onClick={loadPrices}
          className="p-1 rounded text-muted-foreground hover:text-primary hover:bg-primary/10 transition"
          title={t.watchlistRefresh || "Refresh"}
        >
          <RefreshCw className="h-3.5 w-3.5" />
        </button>
      </form>

      {/* Symbol list */}
      <div className="flex-1 overflow-auto">
        {symbols.length === 0 ? (
          <div className="p-4 text-center text-[11px] text-muted-foreground/60">
            {t.watchlistNoData || "No watchlist yet."}
          </div>
        ) : (
          symbols.map((item) => {
            const p = prices[item.symbol];
            const isUp = p && p.change_pct > 0;
            const isDown = p && p.change_pct < 0;
            return (
              <button
                key={item.id}
                onClick={() => onAnalyze(`分析 ${item.symbol} 的近期走势和交易机会`)}
                className="w-full flex items-center gap-2 px-3 py-2 hover:bg-muted/50 transition text-left group border-b border-border/30"
              >
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-medium truncate">{item.name || item.symbol}</div>
                  <div className="text-[10px] text-muted-foreground font-mono">{item.symbol}</div>
                </div>
                <div className="text-right shrink-0">
                  <div className={cn(
                    "text-xs font-mono font-medium",
                    isUp && "text-up",
                    isDown && "text-down",
                  )}>
                    {p ? fmtPrice(p.price) : "..."}
                  </div>
                  {p && p.change_pct !== 0 ? (
                    <div className={cn(
                      "flex items-center gap-0.5 text-[10px]",
                      isUp && "text-up",
                      isDown && "text-down",
                    )}>
                      {isUp ? <TrendingUp className="h-2.5 w-2.5" /> : isDown ? <TrendingDown className="h-2.5 w-2.5" /> : <Minus className="h-2.5 w-2.5" />}
                      {p.change_pct > 0 ? "+" : ""}{p.change_pct.toFixed(2)}%
                    </div>
                  ) : (
                    <div className="text-[10px] text-muted-foreground">—</div>
                  )}
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); removeSymbol(item.symbol); }}
                  className="p-0.5 opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-danger rounded transition-all shrink-0"
                >
                  <X className="h-3 w-3" />
                </button>
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}
