import { create } from "zustand";
import { paperTradingApi } from "@/services/paperTrading";
import {
  type BarData,
  type SSEStateFields,
  type SSEDataFields,
  sseInitialState,
  createSSEActions,
} from "./paperTradingSSEBase";

// Re-export BarData for backward compatibility — consumers import it from here.
export type { BarData };

/* ------------------------------------------------------------------ */
/*  Store state type (extends the shared SSE slices)                  */
/* ------------------------------------------------------------------ */

interface PaperTradingLiveState extends SSEStateFields, SSEDataFields {
  connectSSE: (runId: string) => void;
  disconnectSSE: () => void;
  fetchBars: (runId: string, codes?: string) => Promise<void>;
  fetchEquity: (runId: string) => Promise<void>;
  fetchTrades: (runId: string) => Promise<void>;
  reset: () => void;
}

/* ------------------------------------------------------------------ */
/*  Store                                                             */
/* ------------------------------------------------------------------ */

export const usePaperTradingLiveStore = create<PaperTradingLiveState>((set, get) => ({
  ...sseInitialState,

  /* SSE actions — composed from the shared base (no extra callbacks) */
  ...createSSEActions(set, get),

  /* ---- data-fetching actions ------------------------------------ */

  fetchBars: async (runId: string, codes?: string) => {
    try {
      const bars = await paperTradingApi.getBars(runId, codes);
      if (bars && Object.keys(bars).length > 0) {
        set({ ohlcvData: bars });
      }
    } catch {
      /* ignore */
    }
  },

  fetchEquity: async (runId: string) => {
    try {
      const equity = await paperTradingApi.getEquity(runId);
      set({ equity });
    } catch {
      /* ignore */
    }
  },

  fetchTrades: async (runId: string) => {
    try {
      const trades = await paperTradingApi.getTrades(runId);
      set({ recentTrades: trades });
    } catch {
      /* ignore */
    }
  },

  reset: () => {
    get().disconnectSSE();
    set(sseInitialState);
  },
}));
