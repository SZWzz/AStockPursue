import { create } from "zustand";
import { api, type NewsItem, type TrendingTopic, type MarketSentiment, type StockSentiment } from "@/lib/api";

export type SSEStatus = "disconnected" | "connected" | "reconnecting";

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

  // Actions
  fetchTrending: (limit?: number) => Promise<void>;
  fetchMarketSentiment: () => Promise<void>;
  fetchStockSentiment: (symbol: string) => Promise<StockSentiment | null>;
  addLiveNews: (item: NewsItem) => void;
  setSseStatus: (status: SSEStatus) => void;
  resetLiveNews: () => void;
}

export const useSentimentStore = create<SentimentState>((set) => ({
  trendingTopics: [],
  trendingLoading: false,
  marketSentiment: null,
  marketLoading: false,
  stockSentiments: {},
  stockSentimentLoading: false,
  liveNews: [],
  sseStatus: "disconnected",

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
      return { liveNews: [item, ...s.liveNews].slice(0, 100) };
    });
  },

  setSseStatus: (status: SSEStatus) => {
    set({ sseStatus: status });
  },

  resetLiveNews: () => {
    set({ liveNews: [] });
  },
}));
