import { useEffect, useCallback, useMemo } from "react";
import { TrendingUp, Newspaper, Zap, ShieldAlert, DollarSign, TrendingDown, Activity, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n";
import { useSentimentStore, SOURCE_COLORS, type SSEStatus } from "@/stores/sentimentStore";
import { useSSE } from "@/hooks/useSSE";
import { api, type NewsItem } from "@/lib/api";
import { Skeleton } from "@/components/common/Skeleton";

// ── Sub-components ─────────────────────────────────────────────────────────

function SentimentBadge({ score, size = "sm" }: { score: number; size?: "sm" | "md" }) {
  const colorClass =
    score >= 0.6
      ? "bg-up/10 text-up dark:bg-up/20 dark:text-up"
      : score <= 0.4
        ? "bg-down/10 text-down dark:bg-down/20 dark:text-down"
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

function SourceBadge({ source, sourceLabel, className }: { source: string; sourceLabel?: string; className?: string }) {
  const colors = SOURCE_COLORS[source] || SOURCE_COLORS.web_search;
  const label = sourceLabel || source || "未知";
  return (
    <span className={cn("inline-block rounded px-1.5 py-0 text-[10px] font-medium border whitespace-nowrap", colors, className)}>
      {label}
    </span>
  );
}

function FreshnessDot({ fresh }: { fresh: boolean | null }) {
  if (fresh === true) {
    return <span className="h-2 w-2 rounded-full bg-emerald-500 inline-block" title="Fresh data" />;
  }
  if (fresh === false) {
    return <span className="h-2 w-2 rounded-full bg-amber-400 inline-block" title="Stale data" />;
  }
  return <span className="h-2 w-2 rounded-full bg-gray-300 dark:bg-gray-600 inline-block" title="No data" />;
}

// ── Main page ──────────────────────────────────────────────────────────────

export function Sentiment() {
  const { t } = useI18n();
  const store = useSentimentStore();
  const sse = useSSE();

  // Fetch data on mount
  useEffect(() => {
    store.fetchMarketSentiment();
    store.fetchTrending();
    store.fetchSourceFreshness();
  }, []);

  // Periodically refresh source freshness (every 60s)
  useEffect(() => {
    const interval = setInterval(() => store.fetchSourceFreshness(), 60000);
    return () => clearInterval(interval);
  }, []);

  // SSE connection for market-wide live news
  useEffect(() => {
    let cancelled = false;
    // Track whether connect() was called so cleanup can close it
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
        if (cancelled) {
          // Navigated away during connect — tear down immediately
          sse.disconnect();
          return;
        }
        store.setSseStatus("connected");
      } catch {
        if (!cancelled) store.setSseStatus("disconnected");
      }
    };
    sse.onStatusChange((status: SSEStatus) => {
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
    store.fetchSourceFreshness();
    store.resetLiveNews();
  }, [store]);

  const {
    marketSentiment,
    marketLoading,
    trendingTopics,
    trendingLoading,
    liveNews,
    sseStatus,
    sourceFilter,
    sourceFreshness,
    sourceCounts,
  } = store;

  // Compute filtered live news + unique source list
  const filteredNews = useMemo(() => {
    if (!sourceFilter) return liveNews;
    return liveNews.filter((n) => n.source === sourceFilter);
  }, [liveNews, sourceFilter]);

  const availableSources = useMemo(() => {
    const sourceSet = new Set(liveNews.map((n) => n.source || "web_search"));
    return Array.from(sourceSet)
      .map((id) => ({
        id,
        label: sourceFreshness[id]?.label || id,
        count: sourceCounts[id] || 0,
      }))
      .sort((a, b) => b.count - a.count);
  }, [liveNews, sourceFreshness, sourceCounts]);

  const totalCount = liveNews.length;

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
            <span className="flex items-center gap-1 text-[11px] text-up dark:text-up">
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

      {/* Source Filter Bar */}
      <section className="shrink-0">
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-thin">
          <button
            onClick={() => store.setSourceFilter("")}
            className={cn(
              "shrink-0 px-2.5 py-1 rounded-full text-[11px] font-medium border transition",
              !sourceFilter
                ? "bg-primary text-primary-foreground border-primary"
                : "bg-card text-muted-foreground border-border hover:bg-muted"
            )}
          >
            {t.sentimentAllSources || "全部"} ({totalCount})
          </button>
          {availableSources.map((src) => (
            <button
              key={src.id}
              onClick={() => store.setSourceFilter(src.id)}
              className={cn(
                "shrink-0 px-2.5 py-1 rounded-full text-[11px] font-medium border transition flex items-center gap-1",
                sourceFilter === src.id
                  ? "bg-primary text-primary-foreground border-primary"
                  : "bg-card text-muted-foreground border-border hover:bg-muted"
              )}
            >
              <SourceBadge source={src.id} sourceLabel={src.label} />
              ({src.count})
            </button>
          ))}
        </div>
      </section>

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
                marketSentiment.overall_sentiment >= 0.6 ? "text-up" : marketSentiment.overall_sentiment <= 0.4 ? "text-down" : "text-amber-500"
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
                marketSentiment.yield_spread.signal === "bullish" ? "text-up" : marketSentiment.yield_spread.signal === "bearish" ? "text-down" : "text-muted-foreground"
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

      {/* Source Health Indicators */}
      {Object.keys(sourceFreshness).length > 0 && (
        <section className="shrink-0">
          <div className="flex items-center gap-3 flex-wrap text-[11px] text-muted-foreground">
            <span className="font-medium">{t.sentimentSourceHealth || "数据源健康"}:</span>
            {Object.entries(sourceFreshness).slice(0, 12).map(([id, info]) => (
              <span key={id} className="flex items-center gap-1">
                <FreshnessDot fresh={info.fresh} />
                <SourceBadge source={id} sourceLabel={info.label} />
                {info.count_24h > 0 && (
                  <span className="text-[10px]">{info.count_24h}</span>
                )}
              </span>
            ))}
          </div>
        </section>
      )}

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
                  {trendingTopics.map((topic, i) => (
                    <tr key={topic.topic} className={cn("border-b last:border-0 hover:bg-muted/20 transition", i % 2 === 0 && "bg-muted/5")}>
                      <td className="px-3 py-2 font-medium">{topic.topic}</td>
                      <td className="px-2 py-2 text-center text-muted-foreground">{topic.count}</td>
                      <td className="px-2 py-2">
                        <div className="flex items-center justify-center gap-1">
                          <SentimentBadge score={topic.sentiment_mean} />
                        </div>
                      </td>
                      <td className="px-3 py-2 text-right font-mono">
                        <span className={cn(
                          topic.trending_score >= 3 ? "text-up font-semibold" : topic.trending_score >= 1 ? "text-foreground" : "text-muted-foreground"
                        )}>
                          {topic.trending_score.toFixed(1)}
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
            {filteredNews.length === 0 ? (
              <div className="flex items-center justify-center h-full text-xs text-muted-foreground py-12 text-center">
                {sseStatus === "connected"
                  ? (t.sentimentLoading || "Waiting for live news...")
                  : (t.sentimentNoData || "Connecting to live feed...")}
              </div>
            ) : (
              filteredNews.map((n, i) => (
                <a
                  key={`${n.source}-${i}`}
                  href={n.url || "#"}
                  target={n.url ? "_blank" : undefined}
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
                    <SourceBadge source={n.source} sourceLabel={n.source_label} />
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
