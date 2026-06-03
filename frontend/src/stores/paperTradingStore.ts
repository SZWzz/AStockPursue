import { create } from "zustand";
import {
  paperTradingApi,
  type RunDetail,
  type RunSummary,
} from "@/services/paperTrading";
import {
  type BarData,
  type SSEStateFields,
  type SSEDataFields,
  sseInitialState,
  createSSEActions,
} from "./paperTradingSSEBase";

// Re-export BarData for backward compatibility — consumers may import it from here.
export type { BarData };

/* ------------------------------------------------------------------ */
/*  Store state type                                                  */
/* ------------------------------------------------------------------ */

interface PaperTradingState extends SSEStateFields, SSEDataFields {
  // Run list
  runs: RunSummary[];
  runsLoading: boolean;

  // Selected run detail
  activeRunId: string | null;
  activeRunDetail: RunDetail | null;
  detailLoading: boolean;

  // Actions
  fetchRuns: () => Promise<void>;
  selectRun: (runId: string) => Promise<void>;
  createRun: (req: Parameters<typeof paperTradingApi.createRun>[0]) => Promise<string>;
  startRun: (runId: string) => Promise<void>;
  stopRun: (runId: string) => Promise<void>;
  pauseRun: (runId: string) => Promise<void>;
  resumeRun: (runId: string) => Promise<void>;
  deleteRun: (runId: string) => Promise<void>;
  connectSSE: (runId: string) => void;
  disconnectSSE: () => void;
  fetchBars: (runId: string, codes?: string) => Promise<void>;
  fetchEquity: (runId: string) => Promise<void>;
  fetchTrades: (runId: string) => Promise<void>;
  reset: () => void;
}

/* ------------------------------------------------------------------ */
/*  Initial state for the run-management fields only                  */
/* ------------------------------------------------------------------ */

const runInitialState = {
  runs: [] as RunSummary[],
  runsLoading: false,
  activeRunId: null as string | null,
  activeRunDetail: null as RunDetail | null,
  detailLoading: false,
};

/* ------------------------------------------------------------------ */
/*  Store                                                             */
/* ------------------------------------------------------------------ */

export const usePaperTradingStore = create<PaperTradingState>((set, get) => ({
  ...runInitialState,
  ...sseInitialState,

  /* SSE actions — composed from the shared base with store-specific
     callbacks for trade and status events.                             */
  ...createSSEActions(
    set,
    get,
    {
      /* After a trade event, refresh the run detail so tables update.
         Debounce to avoid request cascade during rapid trading activity. */
      onTrade: (() => {
        let timer: ReturnType<typeof setTimeout> | null = null;
        let latestRunId: string | null = null;
        return (runId: string) => {
          latestRunId = runId;
          if (timer) return;  // already scheduled
          timer = setTimeout(() => {
            timer = null;
            const rid = latestRunId;
            latestRunId = null;
            if (rid && get().activeRunId === rid) {
              get().selectRun(rid);
            }
          }, 500);
        };
      })(),
      /* After a status event, refresh the run list. */
      onStatus: () => {
        get().fetchRuns();
      },
    },
  ),

  /* ---- run-management actions ------------------------------------ */

  fetchRuns: async () => {
    set({ runsLoading: true });
    try {
      const runs = await paperTradingApi.listRuns();
      set({ runs, runsLoading: false });
    } catch {
      set({ runsLoading: false });
    }
  },

  selectRun: async (runId: string) => {
    set({ activeRunId: runId, detailLoading: true });
    try {
      const detail = await paperTradingApi.getRun(runId);
      set({ activeRunDetail: detail, detailLoading: false });
      const codes =
        detail.positions?.map((p) => p.symbol).join(",") || "";
      get().fetchBars(runId, codes || undefined);
    } catch {
      set({ detailLoading: false });
    }
  },

  createRun: async (req) => {
    const result = await paperTradingApi.createRun(req);
    await get().fetchRuns();
    return result.id;
  },

  startRun: async (runId: string) => {
    await paperTradingApi.startRun(runId);
    await get().fetchRuns();
    get().connectSSE(runId);
  },

  stopRun: async (runId: string) => {
    get().disconnectSSE();
    await paperTradingApi.stopRun(runId);
    await get().fetchRuns();
    if (get().activeRunId === runId) {
      await get().selectRun(runId);
    }
  },

  pauseRun: async (runId: string) => {
    await paperTradingApi.pauseRun(runId);
    await get().fetchRuns();
  },

  resumeRun: async (runId: string) => {
    await paperTradingApi.resumeRun(runId);
    await get().fetchRuns();
    get().connectSSE(runId);
  },

  deleteRun: async (runId: string) => {
    get().disconnectSSE();
    await paperTradingApi.deleteRun(runId);
    if (get().activeRunId === runId) {
      set({
        activeRunId: null,
        activeRunDetail: null,
        ...sseInitialState,
      });
    }
    await get().fetchRuns();
  },

  /* ---- data-fetching actions (identical to the live store) ------- */

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
    set({ ...runInitialState, ...sseInitialState });
  },
}));
