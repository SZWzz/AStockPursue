import { useEffect, useCallback, useState } from "react";
import { TrendingUp, Newspaper, ListOrdered, Building2, Bell, FlaskConical } from "lucide-react";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n";
import { useTradingStore } from "@/stores/tradingStore";
import { CandlestickChart } from "@/components/charts/CandlestickChart";
import { MinuteLineChart } from "@/components/trading/MinuteLineChart";
import { TradingWatchlist } from "@/components/trading/TradingWatchlist";
import { IndexTickerBar } from "@/components/trading/IndexTickerBar";
import { OrderPanel } from "@/components/trading/OrderPanel";
import { BrokerPanel } from "@/components/trading/BrokerPanel";
import { NotifyConfigPanel } from "@/components/trading/NotifyConfigPanel";
import { OptimizationPanel } from "@/components/trading/OptimizationPanel";

type Tab = "news" | "orders" | "broker" | "notify" | "optimize";

const TABS: { id: Tab; labelKey: string; icon: typeof TrendingUp }[] = [
  { id: "news", labelKey: "tradingNews", icon: Newspaper },
  { id: "orders", labelKey: "tradingOrderPanel", icon: ListOrdered },
  { id: "broker", labelKey: "tradingBroker", icon: Building2 },
  { id: "notify", labelKey: "tradingNotify", icon: Bell },
  { id: "optimize", labelKey: "tradingOptimize", icon: FlaskConical },
];

export function Trading() {
  const { t } = useI18n();
  const store = useTradingStore();
  const [tab, setTab] = useState<Tab>("orders");
  const [news, setNews] = useState<{ title: string; url: string; source: string; summary: string; published_at: string }[]>([]);
  const [newsLoading, setNewsLoading] = useState(false);

  // Load indices on mount
  useEffect(() => {
    store.fetchIndices();
    store.fetchOrders();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSelectSymbol = useCallback((symbol: string) => {
    store.selectSymbol(symbol);
  }, [store]);

  const loadNews = useCallback(async () => {
    if (!store.selectedSymbol) return;
    setNewsLoading(true);
    try {
      const { api } = await import("@/lib/api");
      const data = await api.getNews(store.selectedSymbol);
      setNews(data.articles || []);
    } catch { /* ignore */ }
    setNewsLoading(false);
  }, [store.selectedSymbol]);

  useEffect(() => {
    if (tab === "news" && store.selectedSymbol) {
      loadNews();
    }
  }, [tab, store.selectedSymbol, loadNews]);

  return (
    <div className="flex flex-col h-full">
      {/* Index ticker bar */}
      <IndexTickerBar
        indices={store.indices}
        onRefresh={store.fetchIndices}
      />

      {/* Main content grid */}
      <div className="flex-1 flex min-h-0">
        {/* Left sidebar — search + watchlist */}
        <div className="w-56 shrink-0 border-r flex flex-col bg-muted/10">
          <TradingWatchlist
            selectedSymbol={store.selectedSymbol}
            onSelect={handleSelectSymbol}
          />
        </div>

        {/* Right area — chart + tabs */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Chart area */}
          <div className="flex-1 min-h-0 overflow-auto p-2">
            {/* Chart mode toggle */}
            <div className="flex items-center gap-1 mb-2">
              <button
                onClick={() => store.setChartMode("kline")}
                className={cn(
                  "px-3 py-1 text-xs rounded transition",
                  store.chartMode === "kline" ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:bg-muted/70"
                )}
              >
                {t.tradingKline || "K线"}
              </button>
              <button
                onClick={() => store.setChartMode("minute")}
                className={cn(
                  "px-3 py-1 text-xs rounded transition",
                  store.chartMode === "minute" ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:bg-muted/70"
                )}
              >
                {t.tradingMinuteLine || "分时"}
              </button>

              {/* Date picker for minute mode */}
              {store.chartMode === "minute" && (
                <input
                  type="date"
                  value={store.minuteDate}
                  onChange={(e) => store.setMinuteDate(e.target.value)}
                  className="ml-2 text-xs rounded border px-2 py-1 bg-background"
                  title={t.tradingSelectDate || "选择日期"}
                />
              )}

              {store.selectedSymbol && (
                <span className="ml-auto text-xs font-mono text-muted-foreground">{store.selectedSymbol}</span>
              )}
            </div>

            {/* Chart */}
            {!store.selectedSymbol ? (
              <div className="flex items-center justify-center h-[400px] border rounded-xl bg-muted/10 text-muted-foreground text-sm">
                {t.tradingNoSymbol || "请从左侧自选股选择一个标的"}
              </div>
            ) : store.chartMode === "kline" ? (
              store.klineLoading ? (
                <div className="flex items-center justify-center h-[400px] border rounded-xl bg-muted/10 text-muted-foreground text-sm">
                  加载K线数据...
                </div>
              ) : (
                <CandlestickChart
                  data={store.klineData}
                  height={400}
                />
              )
            ) : (
              store.minuteLoading ? (
                <div className="flex items-center justify-center h-[400px] border rounded-xl bg-muted/10 text-muted-foreground text-sm">
                  加载分时数据...
                </div>
              ) : (
                <MinuteLineChart
                  data={store.minuteData}
                  preClose={store.minutePreClose}
                  symbol={store.selectedSymbol}
                  height={400}
                />
              )
            )}
          </div>

          {/* Tab bar + panels */}
          <div className="border-t shrink-0" style={{ height: "40%" }}>
            <div className="flex border-b">
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
                <div className="p-3 space-y-2">
                  {!store.selectedSymbol ? (
                    <div className="text-center text-xs text-muted-foreground py-8">请先选择标的</div>
                  ) : newsLoading ? (
                    <div className="text-center py-4 text-xs text-muted-foreground">加载中...</div>
                  ) : news.length === 0 ? (
                    <div className="text-center text-xs text-muted-foreground py-8">暂无相关资讯</div>
                  ) : (
                    news.map((n, i) => (
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
                    ))
                  )}
                </div>
              )}
              {tab === "orders" && (
                <OrderPanel
                  symbol={store.selectedSymbol}
                  orders={store.orders}
                  loading={store.ordersLoading}
                  onRefresh={() => store.fetchOrders()}
                />
              )}
              {tab === "broker" && <BrokerPanel />}
              {tab === "notify" && <NotifyConfigPanel />}
              {tab === "optimize" && <OptimizationPanel symbol={store.selectedSymbol} />}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
