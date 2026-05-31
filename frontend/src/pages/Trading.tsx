import { useEffect, useCallback, useState, useRef } from "react";
import { TrendingUp, Newspaper, ListOrdered, Building2, Bell, RefreshCw, BarChart3 } from "lucide-react";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n";
import { useTradingStore } from "@/stores/tradingStore";
import { useSSE } from "@/hooks/useSSE";
import { api, type NewsItem, type StockSentiment } from "@/lib/api";
import { Skeleton } from "@/components/common/Skeleton";
import { CandlestickChart } from "@/components/charts/CandlestickChart";
import { MinuteLineChart } from "@/components/trading/MinuteLineChart";
import { TradingWatchlist } from "@/components/trading/TradingWatchlist";
import { IndexTickerBar } from "@/components/trading/IndexTickerBar";
import { OrderPanel } from "@/components/trading/OrderPanel";
import { BrokerPanel } from "@/components/trading/BrokerPanel";
import { NotifyConfigPanel } from "@/components/trading/NotifyConfigPanel";
import { StockFundamentalsPanel } from "@/components/trading/StockFundamentalsPanel";

type Tab = "news" | "orders" | "broker" | "notify" | "fundamentals";

const TABS: { id: Tab; labelKey: string; icon: typeof TrendingUp }[] = [
  { id: "news", labelKey: "tradingNews", icon: Newspaper },
  { id: "orders", labelKey: "tradingOrderPanel", icon: ListOrdered },
  { id: "fundamentals", labelKey: "tradingFundamentals", icon: BarChart3 },
  { id: "broker", labelKey: "tradingBroker", icon: Building2 },
  { id: "notify", labelKey: "tradingNotify", icon: Bell },
];

export function Trading() {
  const { t } = useI18n();
  const store = useTradingStore();
  const [tab, setTab] = useState<Tab>("orders");
  const [news, setNews] = useState<NewsItem[]>([]);
  const [newsLoading, setNewsLoading] = useState(false);
  const [newsError, setNewsError] = useState(false);
  const [stockSentiment, setStockSentiment] = useState<StockSentiment | null>(null);
  const sse = useSSE();
  const sseConnectedRef = useRef(false);

  // Extract stable action references from zustand store
  const { fetchIndices, fetchOrders, selectSymbol, selectedSymbol, chartMode, minuteDate, minutePreClose,
    klineData, klineLoading, minuteData, minuteLoading, orders, ordersLoading, indices,
    setChartMode, setMinuteDate } = store;

  // Current price from kline data (last close)
  const currentPrice = klineData.length > 0 ? klineData[klineData.length - 1].close : 0;

  // Load indices on mount
  useEffect(() => {
    fetchIndices();
    fetchOrders();
  }, [fetchIndices, fetchOrders]);

  const handleSelectSymbol = useCallback((symbol: string) => {
    selectSymbol(symbol);
  }, [selectSymbol]);

  const loadNews = useCallback(async () => {
    if (!selectedSymbol) return;
    setNewsLoading(true);
    setNewsError(false);
    try {
      const data = await api.getNews(selectedSymbol);
      setNews(data.articles || []);
      setStockSentiment(data.stock_sentiment || null);
      if (!data.articles?.length) setNewsError(true);
    } catch {
      setNewsError(true);
      setStockSentiment(null);
    }
    setNewsLoading(false);
  }, [selectedSymbol]);

  useEffect(() => {
    if (tab === "news" && selectedSymbol) {
      loadNews();
    }
  }, [tab, selectedSymbol, loadNews]);

  // SSE connection for per-symbol real-time news
  useEffect(() => {
    if (tab === "news" && selectedSymbol) {
      let cancelled = false;
      const connectSSE = async () => {
        try {
          const url = await api.newsStreamUrl(selectedSymbol);
          if (cancelled) return;
          sse.connect(url, {
            news: (data) => {
              const item = data as unknown as NewsItem;
              setNews((prev) => {
                if (item.url && prev.some((n) => n.url === item.url)) return prev;
                return [item, ...prev].slice(0, 50);
              });
            },
          });
          sseConnectedRef.current = true;
        } catch {
          sseConnectedRef.current = false;
        }
      };
      connectSSE();
      return () => {
        cancelled = true;
        sse.disconnect();
        sseConnectedRef.current = false;
      };
    } else {
      sse.disconnect();
      sseConnectedRef.current = false;
    }
  }, [tab, selectedSymbol]);

  return (
    <div className="flex flex-col h-full">
      {/* Index ticker bar */}
      <IndexTickerBar
        indices={indices}
        onRefresh={fetchIndices}
      />

      {/* Main content grid — responsive: stack on mobile, side-by-side on desktop */}
      <div className="flex-1 flex flex-col md:flex-row min-h-0 gap-2 p-2">
        {/* Left sidebar — search + watchlist (hidden on mobile unless toggled) */}
        <div className="hidden md:flex w-full md:w-56 shrink-0 flex-col rounded-xl border bg-card overflow-hidden">
          <TradingWatchlist
            selectedSymbol={selectedSymbol}
            onSelect={handleSelectSymbol}
          />
        </div>

        {/* Right area — chart + tabs */}
        <div className="flex-1 flex flex-col min-w-0 gap-2">
          {/* Chart area */}
          <div className="flex-1 flex flex-col min-h-0">
            {/* Chart mode toggle */}
            <div className="flex items-center gap-1 mb-2 shrink-0">
              <button
                onClick={() => setChartMode("kline")}
                className={cn(
                  "px-3 py-1 text-xs rounded transition",
                  chartMode === "kline" ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:bg-muted/70"
                )}
              >
                {t.tradingKline || "K线"}
              </button>
              <button
                onClick={() => setChartMode("minute")}
                className={cn(
                  "px-3 py-1 text-xs rounded transition",
                  chartMode === "minute" ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:bg-muted/70"
                )}
              >
                {t.tradingMinuteLine || "分时"}
              </button>

              {/* Date picker for minute mode */}
              {chartMode === "minute" && (
                <input
                  type="date"
                  value={minuteDate}
                  onChange={(e) => setMinuteDate(e.target.value)}
                  className="ml-2 text-xs rounded border px-2 py-1 bg-background"
                  title={t.tradingSelectDate || "选择日期"}
                />
              )}

              {selectedSymbol && (
                <span className="ml-auto text-xs font-mono text-muted-foreground">{selectedSymbol}</span>
              )}
            </div>

            {/* Chart — fills remaining vertical space */}
            <div className="flex-1 min-h-0">
            {!selectedSymbol ? (
              <div className="flex items-center justify-center h-full border rounded-xl bg-muted/10 text-muted-foreground text-sm">
                {t.tradingNoSymbol || "请从左侧自选股选择一个标的"}
              </div>
            ) : chartMode === "kline" ? (
              klineLoading ? (
                <Skeleton className="h-full w-full rounded-xl" />
              ) : (
                <CandlestickChart
                  data={klineData}
                />
              )
            ) : (
              minuteLoading ? (
                <Skeleton className="h-full w-full rounded-xl" />
              ) : (
                <MinuteLineChart
                  data={minuteData}
                  preClose={minutePreClose}
                  symbol={selectedSymbol}
                />
              )
            )}
            </div>
          </div>

          {/* Tab bar + panels — rounded card */}
          <div className="shrink-0 rounded-xl border bg-card overflow-hidden" style={{ height: "40%" }}>
            <div className="flex border-b bg-muted/30">
              {TABS.map(({ id, labelKey, icon: Icon }) => (
                <button
                  key={id}
                  onClick={() => setTab(id)}
                  className={cn(
                    "flex items-center gap-1.5 px-3 py-2 text-xs font-medium transition border-b-2",
                    tab === id ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"
                  )}
                >
                  <Icon className="h-3.5 w-3.5" />
                  {t[labelKey as keyof typeof t] || id}
                </button>
              ))}
            </div>
            <div className="overflow-auto" style={{ height: "calc(100% - 35px)" }}>
              {tab === "news" && (
                <div className="flex flex-col h-full">
                  {/* news header with refresh + live indicator + stock sentiment */}
                  {selectedSymbol && (
                    <div className="flex items-center justify-between px-3 py-1.5 border-b shrink-0">
                      <div className="flex items-center gap-2">
                        <span className="text-[11px] text-muted-foreground">
                          {news.length > 0 ? `${news.length} 条资讯` : "资讯"}
                        </span>
                        {sseConnectedRef.current && (
                          <span className="flex items-center gap-1 text-[10px] text-emerald-600 dark:text-emerald-400">
                            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                            {t.tradingNewsSentimentLive || "Live"}
                          </span>
                        )}
                      </div>
                      <button
                        onClick={loadNews}
                        disabled={newsLoading}
                        className="p-1 rounded text-muted-foreground hover:text-primary hover:bg-primary/10 transition"
                        title="刷新资讯"
                      >
                        <RefreshCw className={cn("h-3 w-3", newsLoading && "animate-spin")} />
                      </button>
                    </div>
                  )}
                  {/* Stock sentiment summary bar */}
                  {stockSentiment && (
                    <div className="flex items-center gap-3 px-3 py-2 border-b shrink-0 bg-muted/20">
                      <span className="text-[10px] text-muted-foreground">{t.tradingNewsSentiment || "Sent."}</span>
                      <span className={cn(
                        "text-xs font-semibold",
                        stockSentiment.sentiment_mean >= 0.6 ? "text-emerald-500" : stockSentiment.sentiment_mean <= 0.4 ? "text-red-500" : "text-amber-500"
                      )}>
                        {(stockSentiment.sentiment_mean * 100).toFixed(0)}
                      </span>
                      <span className="text-[10px] text-muted-foreground">
                        {t.sentimentStd || "Std"}: {(stockSentiment.sentiment_std * 100).toFixed(0)}
                      </span>
                      <span className="text-[10px] text-muted-foreground">
                        N={stockSentiment.news_count}
                      </span>
                      <span className="text-[10px] text-muted-foreground ml-auto">
                        {t.sentimentHeat || "Heat"}: {stockSentiment.trending_score.toFixed(2)}
                      </span>
                    </div>
                  )}
                  <div className="flex-1 overflow-auto p-3 space-y-2">
                  {!selectedSymbol ? (
                    <div className="text-center text-xs text-muted-foreground py-8">请先选择标的</div>
                  ) : newsLoading ? (
                    <div className="text-center py-4 text-xs text-muted-foreground">加载中...</div>
                  ) : newsError && news.length === 0 ? (
                    <div className="text-center py-8 space-y-2">
                      <div className="text-xs text-muted-foreground">加载失败或暂无资讯</div>
                      <button onClick={loadNews} className="text-xs text-primary hover:underline">点击重试</button>
                    </div>
                  ) : newsError ? (
                    <div className="text-center text-[10px] text-muted-foreground/60 py-2">
                      部分来源获取失败 —
                      <button onClick={loadNews} className="ml-1 text-primary hover:underline">重试</button>
                    </div>
                  ) : null}
                  {news.map((n, i) => (
                    <a
                      key={i}
                      href={n.url}
                      target="_blank"
                      rel="noreferrer"
                      className="block border rounded-lg p-2 hover:bg-muted/30 transition text-xs"
                    >
                      <div className="flex items-start gap-1.5">
                        <span className="font-medium line-clamp-2 flex-1">{n.title}</span>
                        {n.sentiment_score !== undefined && (
                          <span className={cn(
                            "shrink-0 inline-block px-1.5 py-0.5 rounded text-[10px] font-medium",
                            n.sentiment_score >= 0.6 ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400" :
                            n.sentiment_score <= 0.4 ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400" :
                            "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400"
                          )}>
                            {(n.sentiment_score * 100).toFixed(0)}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2 mt-1 text-[10px] text-muted-foreground">
                        <span>{n.source}</span>
                        <span>{n.published_at?.slice(0, 10)}</span>
                      </div>
                    </a>
                  ))}
                  </div>
                </div>
              )}
              {tab === "orders" && (
                <OrderPanel
                  symbol={selectedSymbol}
                  orders={orders}
                  loading={ordersLoading}
                  onRefresh={fetchOrders}
                />
              )}
              {tab === "broker" && <BrokerPanel />}
              {tab === "notify" && <NotifyConfigPanel />}
              {tab === "fundamentals" && (
                <StockFundamentalsPanel symbol={selectedSymbol} price={currentPrice} />
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
