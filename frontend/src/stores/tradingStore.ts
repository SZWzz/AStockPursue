import { create } from "zustand";
import { api, type PriceBar, type MinuteBar, type TradingOrder, type IndexItem } from "@/lib/api";

export type ChartMode = "kline" | "minute";

interface TradingState {
  // Chart / symbol
  selectedSymbol: string;
  chartMode: ChartMode;
  klineData: PriceBar[];
  klineLoading: boolean;
  minuteData: MinuteBar[];
  minuteLoading: boolean;
  minuteDate: string;
  minutePreClose: number | null;

  // Orders
  orders: TradingOrder[];
  ordersLoading: boolean;

  // Indices
  indices: IndexItem[];
  indicesLoading: boolean;

  // Actions
  selectSymbol: (symbol: string) => void;
  setChartMode: (mode: ChartMode) => void;
  setMinuteDate: (date: string) => void;

  fetchKline: (symbol: string) => Promise<void>;
  fetchMinuteLine: (symbol: string, date?: string) => Promise<void>;
  fetchOrders: (status?: string) => Promise<void>;
  fetchIndices: () => Promise<void>;
}

const todayStr = () => new Date().toISOString().slice(0, 10);

export const useTradingStore = create<TradingState>((set, get) => ({
  selectedSymbol: "",
  chartMode: "kline",
  klineData: [],
  klineLoading: false,
  minuteData: [],
  minuteLoading: false,
  minuteDate: todayStr(),
  minutePreClose: null,
  orders: [],
  ordersLoading: false,
  indices: [],
  indicesLoading: false,

  selectSymbol: (symbol: string) => {
    set({ selectedSymbol: symbol });
    if (symbol) {
      const { chartMode, minuteDate } = get();
      if (chartMode === "kline") {
        get().fetchKline(symbol);
      } else {
        get().fetchMinuteLine(symbol, minuteDate);
      }
    }
  },

  setChartMode: (mode: ChartMode) => {
    set({ chartMode: mode });
    const { selectedSymbol, minuteDate } = get();
    if (selectedSymbol) {
      if (mode === "kline") {
        get().fetchKline(selectedSymbol);
      } else {
        get().fetchMinuteLine(selectedSymbol, minuteDate);
      }
    }
  },

  setMinuteDate: (date: string) => {
    set({ minuteDate: date });
    const { selectedSymbol } = get();
    if (selectedSymbol) {
      get().fetchMinuteLine(selectedSymbol, date);
    }
  },

  fetchKline: async (symbol: string) => {
    set({ klineLoading: true });
    try {
      const end = todayStr();
      const start = new Date(Date.now() - 365 * 86400000).toISOString().slice(0, 10);
      const result = await api.getOHLCV({ symbol, start_date: start, end_date: end, source: "auto", interval: "1D" });
      set({ klineData: result.bars || [], klineLoading: false });
    } catch {
      set({ klineLoading: false });
    }
  },

  fetchMinuteLine: async (symbol: string, date?: string) => {
    set({ minuteLoading: true });
    try {
      const data = await api.getMinuteLine(symbol, date);
      set({
        minuteData: data.available ? data.minutes : [],
        minutePreClose: data.preClose ?? null,
        minuteLoading: false,
      });
    } catch {
      set({ minuteLoading: false, minuteData: [], minutePreClose: null });
    }
  },

  fetchOrders: async (status?: string) => {
    set({ ordersLoading: true });
    try {
      const data = await api.listOrders(status);
      set({ orders: data.orders || [], ordersLoading: false });
    } catch {
      set({ ordersLoading: false });
    }
  },

  fetchIndices: async () => {
    set({ indicesLoading: true });
    try {
      const data = await api.getIndices();
      set({ indices: data.indices || [], indicesLoading: false });
    } catch {
      set({ indicesLoading: false });
    }
  },
}));
