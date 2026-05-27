import { create } from "zustand";
import {
  paperTradingApi,
  type EquityPoint,
  type Position,
  type RunDetail,
  type RunSummary,
  type Trade,
} from "@/services/paperTrading";
import { createDedupTracker, scheduleReconnect, calcReconnectDelay } from "@/lib/sseClient";

export interface BarData {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

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
  ohlcvData: Record<string, BarData[]>;

  // SSE status
  sseStatus: "disconnected" | "connected" | "reconnecting";
  eventSource: EventSource | null;
  reconnectCount: number;
  reconnectDelayMs: number;
  reconnectTimer: ReturnType<typeof setTimeout> | null;

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
  ohlcvData: {},
  sseStatus: "disconnected" as const,
  eventSource: null,
  reconnectCount: 0,
  reconnectDelayMs: 0,
  reconnectTimer: null,
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
      // Fetch historical K-line data for the run's symbols
      const codes = detail.positions?.map(p => p.symbol).join(",") || "";
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
      set({ activeRunId: null, activeRunDetail: null, equity: [], positions: [], recentTrades: [], tradeMarkers: [], signalLog: [], ohlcvData: {} });
    }
    await get().fetchRuns();
  },

  connectSSE: (runId: string) => {
    const state = get();
    state.disconnectSSE();

    const dedup = createDedupTracker(500);
    let reconnectCount = 0;

    const doConnect = (initialConnect: boolean) => {
      const url = paperTradingApi.getSSEUrl(runId);
      const es = new EventSource(url);
      set({ eventSource: es, sseStatus: initialConnect ? "connected" : "connected", reconnectCount });

      es.addEventListener("bar", (e: MessageEvent) => {
        try {
          if (e.lastEventId && dedup.track(e.lastEventId)) return;
          const data = JSON.parse(e.data);
          set((s) => {
            // Append new bar OHLCV to ohlcvData
            const newOhlcv = { ...s.ohlcvData };
            if (data.bars && typeof data.bars === "object") {
              for (const [code, bar] of Object.entries(data.bars)) {
                const b = bar as Record<string, number>;
                const row: BarData = {
                  time: data.timestamp as string,
                  open: b.open ?? 0,
                  high: b.high ?? 0,
                  low: b.low ?? 0,
                  close: b.close ?? 0,
                  volume: b.volume ?? 0,
                };
                const existing = newOhlcv[code] || [];
                newOhlcv[code] = [...existing, row].slice(-500);
              }
            }
            return {
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
              ohlcvData: newOhlcv,
            };
          });
        } catch { /* ignore */ }
      });

      es.addEventListener("trade", (e: MessageEvent) => {
        try {
          if (e.lastEventId && dedup.track(e.lastEventId)) return;
          const data = JSON.parse(e.data);
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
          if (get().activeRunId === runId) {
            get().selectRun(runId);
          }
        } catch { /* ignore */ }
      });

      es.addEventListener("signal", (e: MessageEvent) => {
        try {
          if (e.lastEventId && dedup.track(e.lastEventId)) return;
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
            set({ sseStatus: "disconnected", reconnectCount: 0 });
            es.close();
          }
        } catch { /* ignore */ }
        get().fetchRuns();
      });

      es.onerror = () => {
        const { eventSource } = get();
        if (!eventSource || eventSource !== es) return;
        es.close();
        if (es.readyState === EventSource.CLOSED) {
          set({ sseStatus: "disconnected", reconnectCount: 0 });
          return;
        }
        reconnectCount += 1;
        const delayMs = calcReconnectDelay(reconnectCount);
        set({ sseStatus: "reconnecting", reconnectCount, reconnectDelayMs: delayMs });
        const timer = scheduleReconnect(
          () => doConnect(false),
          reconnectCount,
        );
        set({ reconnectTimer: timer });
      };
    };

    doConnect(true);
  },

  disconnectSSE: () => {
    const { eventSource, reconnectTimer } = get();
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
    }
    if (eventSource) {
      eventSource.close();
      set({ eventSource: null, sseStatus: "disconnected", reconnectCount: 0, reconnectDelayMs: 0, reconnectTimer: null });
    }
  },

  fetchBars: async (runId: string, codes?: string) => {
    try {
      const bars = await paperTradingApi.getBars(runId, codes);
      if (bars && Object.keys(bars).length > 0) {
        set({ ohlcvData: bars });
      }
    } catch { /* ignore */ }
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
