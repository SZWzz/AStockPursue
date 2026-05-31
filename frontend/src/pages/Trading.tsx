import { useEffect, useCallback, useState } from "react";
import { TrendingUp, Newspaper, ListOrdered, Building2, Bell, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n";
import { useTradingStore } from "@/stores/tradingStore";
import { Skeleton } from "@/components/common/Skeleton";
import { CandlestickChart } from "@/components/charts/CandlestickChart";
import { MinuteLineChart } from "@/components/trading/MinuteLineChart";
import { TradingWatchlist } from "@/components/trading/TradingWatchlist";
import { IndexTickerBar } from "@/components/trading/IndexTickerBar";
import { OrderPanel } from "@/components/trading/OrderPanel";
import { BrokerPanel } from "@/components/trading/BrokerPanel";
import { NotifyConfigPanel } from "@/components/trading/NotifyConfigPanel";

type Tab = "news" | "orders" | "broker" | "notify";

const TABS: { id: Tab; labelKey: string; icon: typeof TrendingUp }[] = [
  { id: "news", labelKey: "tradingNews", icon: Newspaper },
  { id: "orders", labelKey: "tradingOrderPanel", icon: ListOrdered },
  { id: "broker", labelKey: "tradingBroker", icon: Building2 },
  { id: "notify", labelKey: "tradingNotify", icon: Bell },
];

export function Trading() {
  const { t } = useI18n();
  const store = useTradingStore();
  const [tab, setTab] = useState<Tab>("orders");
  const [news, setNews] = useState<{ title: string; url: string; source: string; summary: string; published_at: string }[]>([]);
  const [newsLoading, setNewsLoading] = useState(false);
  const [newsError, setNewsError] = useState(false);

  // Extract stable action references from zustand store
  const { fetchIndices, fetchOrders, selectSymbol, selectedSymbol, chartMode, minuteDate, minutePreClose,
    klineData, klineLoading, minuteData, minuteLoading, orders, ordersLoading, indices,
    setChartMode, setMinuteDate } = store;

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
      const { api } = await import("@/lib/api");
      const data = await api.getNews(selectedSymbol);
      setNews(data.articles || []);
      if (!data.articles?.length) setNewsError(true);
    } catch {
      setNewsError(true);
    }
    setNewsLoading(false);
  }, [selectedSymbol]);

  useEffect(() => {
    if (tab === "news" && selectedSymbol) {
      loadNews();
    }
  }, [tab, selectedSymbol, loadNews]);

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
                  {/* news header with refresh */}
                  {selectedSymbol && (
                    <div className="flex items-center justify-between px-3 py-1.5 border-b shrink-0">
                      <span className="text-[11px] text-muted-foreground">
                        {news.length > 0 ? `${news.length} 条资讯` : "资讯"}
                      </span>
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
                      <div className="font-medium line-clamp-2">{n.title}</div>
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
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
