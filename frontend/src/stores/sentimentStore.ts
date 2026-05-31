import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import { api, type NewsItem, type TrendingTopic, type MarketSentiment, type StockSentiment, type SourceFreshness } from "@/lib/api";

export type SSEStatus = "disconnected" | "connected" | "reconnecting";

// Source color mapping for UI badges
export const SOURCE_COLORS: Record<string, string> = {
  eastmoney_stock:  "bg-red-100 text-red-700 border-red-200 dark:bg-red-900/30 dark:text-red-400",
  eastmoney_global: "bg-orange-100 text-orange-700 border-orange-200 dark:bg-orange-900/30 dark:text-orange-400",
  cls:              "bg-blue-100 text-blue-700 border-blue-200 dark:bg-blue-900/30 dark:text-blue-400",
  cninfo:           "bg-purple-100 text-purple-700 border-purple-200 dark:bg-purple-900/30 dark:text-purple-400",
  xueqiu:           "bg-green-100 text-green-700 border-green-200 dark:bg-green-900/30 dark:text-green-400",
  sina:             "bg-amber-100 text-amber-700 border-amber-200 dark:bg-amber-900/30 dark:text-amber-400",
  futu:             "bg-cyan-100 text-cyan-700 border-cyan-200 dark:bg-cyan-900/30 dark:text-cyan-400",
  ths:              "bg-indigo-100 text-indigo-700 border-indigo-200 dark:bg-indigo-900/30 dark:text-indigo-400",
  gnews:            "bg-gray-100 text-gray-700 border-gray-200 dark:bg-gray-800 dark:text-gray-400",
  newsapi:          "bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-400",
  web_search:       "bg-zinc-100 text-zinc-700 border-zinc-200 dark:bg-zinc-800 dark:text-zinc-400",
};

interface SentimentState {
  // Trending topics
  trendingTopics: TrendingTopic[];
  trendingLoading: boolean;

  // Market sentiment overview
  marketSentiment: MarketSentiment | null;
  marketLoading: boolean;

  // Per-stock sentiments (cached)
  stockSentiments: Record<string, StockSentiment>;
  stockSentimentLoading: boolean;

  // Live news from SSE
  liveNews: NewsItem[];

  // SSE state
  sseStatus: SSEStatus;

  // Source filter & freshness
  sourceFilter: string;                            // current selected source id, "" = all
  sourceFreshness: Record<string, SourceFreshness>; // per-source health
  sourceCounts: Record<string, number>;             // per-source article count in liveNews

  // Actions
  fetchTrending: (limit?: number) => Promise<void>;
  fetchMarketSentiment: () => Promise<void>;
  fetchStockSentiment: (symbol: string) => Promise<StockSentiment | null>;
  addLiveNews: (item: NewsItem) => void;
  setSseStatus: (status: SSEStatus) => void;
  resetLiveNews: () => void;
  setSourceFilter: (source: string) => void;
  fetchSourceFreshness: () => Promise<void>;
}

export const useSentimentStore = create<SentimentState>()(
  persist(
    (set, get) => ({
      trendingTopics: [],
      trendingLoading: false,
      marketSentiment: null,
      marketLoading: false,
      stockSentiments: {},
      stockSentimentLoading: false,
      liveNews: [],
      sseStatus: "disconnected",
      sourceFilter: "",
      sourceFreshness: {},
      sourceCounts: {},

      fetchTrending: async (limit = 10) => {
        set({ trendingLoading: true });
        try {
          const data = await api.getTrendingTopics(limit);
          set({ trendingTopics: data.topics || [], trendingLoading: false });
        } catch {
          set({ trendingLoading: false });
        }
      },

      fetchMarketSentiment: async () => {
        set({ marketLoading: true });
        try {
          const data = await api.getMarketSentiment();
          set({ marketSentiment: data, marketLoading: false });
        } catch {
          set({ marketLoading: false });
        }
      },

      fetchStockSentiment: async (symbol: string) => {
        set({ stockSentimentLoading: true });
        try {
          const data = await api.getStockSentiment(symbol);
          set((s) => ({
            stockSentiments: { ...s.stockSentiments, [symbol.toUpperCase()]: data },
            stockSentimentLoading: false,
          }));
          return data;
        } catch {
          set({ stockSentimentLoading: false });
          return null;
        }
      },

      addLiveNews: (item: NewsItem) => {
        set((s) => {
          // Dedup by URL
          if (item.url && s.liveNews.some((n) => n.url === item.url)) return s;

          const newLiveNews = [item, ...s.liveNews].slice(0, 100);

          // Update source counts
          const newCounts = { ...s.sourceCounts };
          const src = item.source || "web_search";
          newCounts[src] = (newCounts[src] || 0) + 1;

          return { liveNews: newLiveNews, sourceCounts: newCounts };
        });
      },

      setSseStatus: (status: SSEStatus) => {
        set({ sseStatus: status });
      },

      resetLiveNews: () => {
        set({ liveNews: [], sourceCounts: {} });
      },

      setSourceFilter: (source: string) => {
        set({ sourceFilter: source });
      },

      fetchSourceFreshness: async () => {
        try {
          const data = await api.getSourceFreshness();
          set({ sourceFreshness: data.sources || {} });
        } catch {
          // silently fail — freshness indicators will show gray
        }
      },
    }),
    {
      name: "sentiment-storage",
      storage: createJSONStorage(() => sessionStorage),
      partialize: (state) => ({
        trendingTopics: state.trendingTopics,
        marketSentiment: state.marketSentiment,
        stockSentiments: state.stockSentiments,
        liveNews: state.liveNews,
        sourceFilter: state.sourceFilter,
      }),
    },
  ),
);
