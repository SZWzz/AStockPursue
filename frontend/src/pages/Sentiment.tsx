import { useEffect, useCallback } from "react";
import { TrendingUp, Newspaper, Zap, ShieldAlert, DollarSign, TrendingDown, Activity, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n";
import { useSentimentStore } from "@/stores/sentimentStore";
import { useSSE } from "@/hooks/useSSE";
import { api, type NewsItem } from "@/lib/api";
import { Skeleton } from "@/components/common/Skeleton";

function SentimentBadge({ score, size = "sm" }: { score: number; size?: "sm" | "md" }) {
  const colorClass =
    score >= 0.6
      ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400"
      : score <= 0.4
        ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
        : "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400";
  return (
    <span className={cn("inline-block rounded font-medium", colorClass, size === "md" ? "px-2 py-0.5 text-xs" : "px-1.5 py-0.5 text-[10px]")}>
      {(score * 100).toFixed(0)}
    </span>
  );
}

function SentimentBar({ value, maxWidth = 80 }: { value: number; maxWidth?: number }) {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  const color = value >= 0.6 ? "bg-emerald-400" : value <= 0.4 ? "bg-red-400" : "bg-amber-400";
  return (
    <div className="flex items-center gap-1.5">
      <div className="h-1.5 rounded-full bg-muted overflow-hidden" style={{ width: maxWidth }}>
        <div className={cn("h-full rounded-full transition-all", color)} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[10px] text-muted-foreground w-8 text-right">{pct.toFixed(0)}</span>
    </div>
  );
}

export function Sentiment() {
  const { t } = useI18n();
  const store = useSentimentStore();
  const sse = useSSE();

  // Fetch data on mount
  useEffect(() => {
    store.fetchMarketSentiment();
    store.fetchTrending();
  }, []);

  // SSE connection for market-wide live news
  useEffect(() => {
    let cancelled = false;
    const connectSSE = async () => {
      try {
        const url = await api.newsStreamUrl();
        if (cancelled) return;
        sse.connect(url, {
          news: (data) => {
            const item = data as unknown as NewsItem;
            store.addLiveNews(item);
          },
        });
        store.setSseStatus("connected");
      } catch {
        store.setSseStatus("disconnected");
      }
    };
    sse.onStatusChange((status) => {
      store.setSseStatus(status);
    });
    connectSSE();
    return () => {
      cancelled = true;
      sse.disconnect();
    };
  }, []);

  const refreshAll = useCallback(() => {
    store.fetchMarketSentiment();
    store.fetchTrending();
    store.resetLiveNews();
  }, [store]);

  const { marketSentiment, marketLoading, trendingTopics, trendingLoading, liveNews, sseStatus } = store;

  return (
    <div className="flex flex-col h-full p-4 gap-4 overflow-auto">
      {/* Header */}
      <div className="flex items-center justify-between shrink-0">
        <h1 className="text-lg font-bold flex items-center gap-2">
          <Newspaper className="h-5 w-5" />
          {t.sentiment || "Sentiment"}
        </h1>
        <div className="flex items-center gap-2">
          {sseStatus === "connected" && (
            <span className="flex items-center gap-1 text-[11px] text-emerald-600 dark:text-emerald-400">
              <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              {t.sentimentSseConnected || "Live"}
            </span>
          )}
          <button
            onClick={refreshAll}
            className="p-1.5 rounded-lg text-muted-foreground hover:text-primary hover:bg-primary/10 transition"
            title={t.sentimentRefresh || "Refresh"}
          >
            <RefreshCw className={cn("h-4 w-4", (marketLoading || trendingLoading) && "animate-spin")} />
          </button>
        </div>
      </div>

      {/* Market Sentiment Overview */}
      <section className="shrink-0">
        <h2 className="text-sm font-semibold mb-2 flex items-center gap-1.5">
          <Activity className="h-4 w-4" />
          {t.sentimentMarket || "Market Sentiment"}
        </h2>
        {marketLoading ? (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            {[1, 2, 3, 4, 5].map((i) => (
              <Skeleton key={i} className="h-24 rounded-xl" />
            ))}
          </div>
        ) : marketSentiment ? (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            {/* Overall */}
            <div className="rounded-xl border bg-card p-3 flex flex-col items-center justify-center gap-1">
              <span className="text-[10px] text-muted-foreground uppercase tracking-wide">
                {t.sentimentOverallNews || "Overall"}
              </span>
              <span className={cn(
                "text-2xl font-bold",
                marketSentiment.overall_sentiment >= 0.6 ? "text-emerald-500" : marketSentiment.overall_sentiment <= 0.4 ? "text-red-500" : "text-amber-500"
              )}>
                {(marketSentiment.overall_sentiment * 100).toFixed(0)}
              </span>
              <SentimentBar value={marketSentiment.overall_sentiment} maxWidth={60} />
            </div>

            {/* VIX */}
            <div className="rounded-xl border bg-card p-3 flex flex-col items-center justify-center gap-1">
              <span className="text-[10px] text-muted-foreground uppercase tracking-wide flex items-center gap-1">
                <ShieldAlert className="h-3 w-3" />
                {t.sentimentVix || "VIX"}
              </span>
              <span className="text-2xl font-bold">{marketSentiment.vix.current?.toFixed(1) || "-"}</span>
              <span className="text-[10px] text-muted-foreground">{marketSentiment.vix.level || ""}</span>
            </div>

            {/* DXY */}
            <div className="rounded-xl border bg-card p-3 flex flex-col items-center justify-center gap-1">
              <span className="text-[10px] text-muted-foreground uppercase tracking-wide flex items-center gap-1">
                <DollarSign className="h-3 w-3" />
                {t.sentimentDxy || "DXY"}
              </span>
              <span className="text-2xl font-bold">{marketSentiment.dxy.current?.toFixed(1) || "-"}</span>
              <span className="text-[10px] text-muted-foreground">{marketSentiment.dxy.level || ""}</span>
            </div>

            {/* Yield Spread */}
            <div className="rounded-xl border bg-card p-3 flex flex-col items-center justify-center gap-1">
              <span className="text-[10px] text-muted-foreground uppercase tracking-wide flex items-center gap-1">
                <TrendingDown className="h-3 w-3" />
                {t.sentimentYieldSpread || "Yield Spread"}
              </span>
              <span className="text-2xl font-bold">{marketSentiment.yield_spread.spread?.toFixed(2) || "-"}%</span>
              <span className={cn(
                "text-[10px]",
                marketSentiment.yield_spread.signal === "bullish" ? "text-emerald-500" : marketSentiment.yield_spread.signal === "bearish" ? "text-red-500" : "text-muted-foreground"
              )}>
                {marketSentiment.yield_spread.level || ""}
              </span>
            </div>

            {/* Fear & Greed */}
            <div className="rounded-xl border bg-card p-3 flex flex-col items-center justify-center gap-1">
              <span className="text-[10px] text-muted-foreground uppercase tracking-wide flex items-center gap-1">
                <Zap className="h-3 w-3" />
                {t.sentimentFearGreed || "F&G"}
              </span>
              <span className="text-2xl font-bold">{marketSentiment.fear_greed.value || "-"}</span>
              <span className="text-[10px] text-muted-foreground">{marketSentiment.fear_greed.classification || ""}</span>
            </div>
          </div>
        ) : (
          <div className="text-center text-xs text-muted-foreground py-8 border rounded-xl bg-muted/10">
            {t.sentimentNoData || "No data"}
          </div>
        )}
      </section>

      {/* Trending Topics + Live News */}
      <div className="flex-1 grid grid-cols-1 md:grid-cols-3 gap-4 min-h-0">
        {/* Trending Topics */}
        <section className="md:col-span-2 flex flex-col min-h-0">
          <h2 className="text-sm font-semibold mb-2 flex items-center gap-1.5 shrink-0">
            <TrendingUp className="h-4 w-4" />
            {t.sentimentTrending || "Trending Topics"}
          </h2>
          <div className="flex-1 overflow-auto rounded-xl border bg-card">
            {trendingLoading ? (
              <div className="p-4 space-y-2">
                {[1, 2, 3, 4, 5].map((i) => (
                  <Skeleton key={i} className="h-8 w-full" />
                ))}
              </div>
            ) : trendingTopics.length === 0 ? (
              <div className="flex items-center justify-center h-full text-xs text-muted-foreground py-12">
                {t.sentimentNoData || "No trending topics yet"}
              </div>
            ) : (
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b bg-muted/30 text-muted-foreground">
                    <th className="text-left px-3 py-2 font-medium">{t.sentimentTrending || "Topic"}</th>
                    <th className="text-center px-2 py-2 font-medium w-16">{t.sentimentCount || "Count"}</th>
                    <th className="text-center px-2 py-2 font-medium w-20">{t.sentimentMean || "Sentiment"}</th>
                    <th className="text-right px-3 py-2 font-medium w-20">{t.sentimentHeat || "Heat"}</th>
                  </tr>
                </thead>
                <tbody>
                  {trendingTopics.map((t_, i) => (
                    <tr key={t_.topic} className={cn("border-b last:border-0 hover:bg-muted/20 transition", i % 2 === 0 && "bg-muted/5")}>
                      <td className="px-3 py-2 font-medium">{t_.topic}</td>
                      <td className="px-2 py-2 text-center text-muted-foreground">{t_.count}</td>
                      <td className="px-2 py-2">
                        <div className="flex items-center justify-center gap-1">
                          <SentimentBadge score={t_.sentiment_mean} />
                        </div>
                      </td>
                      <td className="px-3 py-2 text-right font-mono">
                        <span className={cn(
                          t_.trending_score >= 3 ? "text-emerald-500 font-semibold" : t_.trending_score >= 1 ? "text-foreground" : "text-muted-foreground"
                        )}>
                          {t_.trending_score.toFixed(1)}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </section>

        {/* Live News Feed */}
        <section className="flex flex-col min-h-0">
          <h2 className="text-sm font-semibold mb-2 flex items-center gap-1.5 shrink-0">
            <Newspaper className="h-4 w-4" />
            {t.sentimentSseConnected || "Live Feed"}
            {sseStatus === "connected" && (
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 ml-1" />
            )}
          </h2>
          <div className="flex-1 overflow-auto rounded-xl border bg-card p-2 space-y-1.5">
            {liveNews.length === 0 ? (
              <div className="flex items-center justify-center h-full text-xs text-muted-foreground py-12 text-center">
                {sseStatus === "connected"
                  ? (t.sentimentLoading || "Waiting for live news...")
                  : (t.sentimentNoData || "Connecting to live feed...")}
              </div>
            ) : (
              liveNews.map((n, i) => (
                <a
                  key={i}
                  href={n.url}
                  target="_blank"
                  rel="noreferrer"
                  className="block border rounded-lg p-2 hover:bg-muted/30 transition text-xs"
                >
                  <div className="flex items-start justify-between gap-1">
                    <span className="font-medium line-clamp-2 flex-1">{n.title}</span>
                    {n.sentiment_score !== undefined && (
                      <SentimentBadge score={n.sentiment_score} />
                    )}
                  </div>
                  <div className="flex items-center gap-2 mt-1 text-[10px] text-muted-foreground">
                    <span>{n.source}</span>
                    {n.published_at && <span>{n.published_at.slice(0, 10)}</span>}
                  </div>
                </a>
              ))
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
