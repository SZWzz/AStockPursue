import { create } from "zustand";
import {
  paperTradingApi,
  type EquityPoint,
  type Position,
  type RunDetail,
  type RunSummary,
  type Trade,
} from "@/services/paperTrading";

interface PaperTradingState {
  // Run list
  runs: RunSummary[];
  runsLoading: boolean;

  // Selected run detail
  activeRunId: string | null;
  activeRunDetail: RunDetail | null;
  detailLoading: boolean;

  // Real-time data (updated via SSE)
  equity: EquityPoint[];
  positions: Position[];
  recentTrades: Trade[];
  tradeMarkers: Array<{ time: string; price: number; side: "BUY" | "SELL"; text?: string }>;
  signalLog: Array<{ symbol: string; direction: number; price: number; reason: string; timestamp: string }>;

  // SSE status
  sseStatus: "disconnected" | "connected" | "reconnecting";
  eventSource: EventSource | null;

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
  fetchEquity: (runId: string) => Promise<void>;
  fetchTrades: (runId: string) => Promise<void>;
  reset: () => void;
}

const initialState = {
  runs: [],
  runsLoading: false,
  activeRunId: null,
  activeRunDetail: null,
  detailLoading: false,
  equity: [],
  positions: [],
  recentTrades: [],
  tradeMarkers: [],
  signalLog: [],
  sseStatus: "disconnected" as const,
  eventSource: null,
};

export const usePaperTradingStore = create<PaperTradingState>((set, get) => ({
  ...initialState,

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
      set({ activeRunId: null, activeRunDetail: null, equity: [], positions: [], recentTrades: [], tradeMarkers: [], signalLog: [] });
    }
    await get().fetchRuns();
  },

  connectSSE: (runId: string) => {
    const state = get();
    state.disconnectSSE();

    const url = paperTradingApi.getSSEUrl(runId);
    const es = new EventSource(url);
    set({ eventSource: es, sseStatus: "connected" });

    es.addEventListener("bar", (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);
        set((s) => ({
          equity: [
            ...s.equity,
            {
              point_time: data.timestamp,
              equity: data.equity,
              capital: data.capital,
              unrealized: data.unrealized,
              drawdown: data.drawdown,
            },
          ].slice(-500),
          // Update positions from bar event
          positions: data.positions
            ? data.positions.map((p: Record<string, unknown>) => ({
                symbol: p.symbol as string,
                direction: p.direction as number,
                entry_price: p.entry_price as number,
                entry_time: data.timestamp as string,
                size: p.size as number,
                leverage: (p.leverage as number) || 1,
                current_price: null,
                unrealized_pnl: null,
                pnl_pct: null,
              }))
            : s.positions,
        }));
      } catch { /* ignore */ }
    });

    es.addEventListener("trade", (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);
        // Build trade markers for K-line chart
        const markers: Array<{ time: string; price: number; side: "BUY" | "SELL"; text?: string }> = [];
        if (data.entry_time && data.entry_price != null) {
          markers.push({ time: data.entry_time, price: data.entry_price, side: "BUY", text: `Enter ${data.symbol}` });
        }
        if (data.exit_time && data.exit_price != null) {
          markers.push({ time: data.exit_time, price: data.exit_price, side: "SELL", text: `Exit ${data.symbol} (${data.exit_reason || "signal"})` });
        }
        if (markers.length > 0) {
          set((s) => ({ tradeMarkers: [...s.tradeMarkers, ...markers].slice(-200) }));
        }
        // Also refresh detail
        if (get().activeRunId === runId) {
          get().selectRun(runId);
        }
      } catch { /* ignore */ }
    });

    es.addEventListener("signal", (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);
        set((s) => ({
          signalLog: [
            ...s.signalLog,
            {
              symbol: data.symbol as string,
              direction: data.direction as number,
              price: data.price as number,
              reason: (data.reason as string) || "",
              timestamp: data.timestamp as string,
            },
          ].slice(-100),
        }));
      } catch { /* ignore */ }
    });

    es.addEventListener("status", (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);
        if (data.status === "stopped" || data.status === "error") {
          set({ sseStatus: "disconnected" });
          es.close();
        }
      } catch { /* ignore */ }
      get().fetchRuns();
    });

    es.addEventListener("error", () => {
      set({ sseStatus: "reconnecting" });
      get().fetchRuns();
    });

    es.onerror = () => {
      if (es.readyState === EventSource.CLOSED) {
        set({ sseStatus: "disconnected" });
      } else {
        set({ sseStatus: "reconnecting" });
      }
    };
  },

  disconnectSSE: () => {
    const { eventSource } = get();
    if (eventSource) {
      eventSource.close();
      set({ eventSource: null, sseStatus: "disconnected" });
    }
  },

  fetchEquity: async (runId: string) => {
    try {
      const equity = await paperTradingApi.getEquity(runId);
      set({ equity });
    } catch { /* ignore */ }
  },

  fetchTrades: async (runId: string) => {
    try {
      const trades = await paperTradingApi.getTrades(runId);
      set({ recentTrades: trades });
    } catch { /* ignore */ }
  },

  reset: () => {
    get().disconnectSSE();
    set(initialState);
  },
}));
