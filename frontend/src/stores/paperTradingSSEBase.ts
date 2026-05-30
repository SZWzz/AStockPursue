import type { EquityPoint, Position, Trade } from "@/services/paperTrading";
import { paperTradingApi } from "@/services/paperTrading";
import { createDedupTracker, scheduleReconnect, calcReconnectDelay } from "@/lib/sseClient";

/* ------------------------------------------------------------------ */
/*  BarData (re-exported for consumers of the old stores)             */
/* ------------------------------------------------------------------ */

export interface BarData {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

/* ------------------------------------------------------------------ */
/*  State-slice interfaces – both stores extend these                 */
/* ------------------------------------------------------------------ */

export interface SSEStateFields {
  sseStatus: "disconnected" | "connected" | "reconnecting";
  eventSource: EventSource | null;
  reconnectCount: number;
  reconnectDelayMs: number;
  reconnectTimer: ReturnType<typeof setTimeout> | null;
}

export interface SSEDataFields {
  equity: EquityPoint[];
  positions: Position[];
  recentTrades: Trade[];
  tradeMarkers: Array<{ time: string; price: number; side: "BUY" | "SELL"; text?: string }>;
  signalLog: Array<{ symbol: string; direction: number; price: number; reason: string; timestamp: string }>;
  ohlcvData: Record<string, BarData[]>;
}

/** One-liner initial values for every SSE + data field. */
export const sseInitialState: SSEStateFields & SSEDataFields = {
  sseStatus: "disconnected",
  eventSource: null,
  reconnectCount: 0,
  reconnectDelayMs: 0,
  reconnectTimer: null,
  equity: [],
  positions: [],
  recentTrades: [],
  tradeMarkers: [],
  signalLog: [],
  ohlcvData: {},
};

/* ------------------------------------------------------------------ */
/*  Callbacks – let each store plug its own side-effects              */
/* ------------------------------------------------------------------ */

export interface SSEActionCallbacks {
  /** Called after a "trade" SSE event is fully processed. */
  onTrade?: (runId: string) => void;
  /** Called after a "status" SSE event is received. */
  onStatus?: () => void;
}

/* ------------------------------------------------------------------ */
/*  createSSEActions – the shared SSE connect / disconnect logic     */
/* ------------------------------------------------------------------ */

/**
 * Minimal shape the SSE action factory reads & writes at runtime.
 * Each concrete store's state must be a superset of this.
 */
export type SSESliceState = SSEStateFields &
  SSEDataFields & {
    disconnectSSE: () => void;
  };

export function createSSEActions(
  set: (partial: Partial<SSESliceState> | ((s: SSESliceState) => Partial<SSESliceState>)) => void,
  get: () => SSESliceState,
  callbacks?: SSEActionCallbacks,
) {
  /* ---- connectSSE ------------------------------------------------- */
  function connectSSE(runId: string) {
    get().disconnectSSE();

    const dedup = createDedupTracker(500);
    let reconnectCount = 0;

    const doConnect = () => {
      const url = paperTradingApi.getSSEUrl(runId);
      const es = new EventSource(url);
      set({ eventSource: es, sseStatus: "connected", reconnectCount });

      /* bar event --------------------------------------------------- */
      es.addEventListener("bar", (e: MessageEvent) => {
        try {
          if (e.lastEventId && dedup.track(e.lastEventId)) return;
          const data = JSON.parse(e.data);
          set((s) => {
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
        } catch {
          /* ignore malformed frames */
        }
      });

      /* trade event ------------------------------------------------- */
      es.addEventListener("trade", (e: MessageEvent) => {
        try {
          if (e.lastEventId && dedup.track(e.lastEventId)) return;
          const data = JSON.parse(e.data);
          const markers: Array<{
            time: string;
            price: number;
            side: "BUY" | "SELL";
            text?: string;
          }> = [];
          if (data.entry_time && data.entry_price != null) {
            markers.push({
              time: data.entry_time,
              price: data.entry_price,
              side: "BUY",
              text: `Enter ${data.symbol}`,
            });
          }
          if (data.exit_time && data.exit_price != null) {
            markers.push({
              time: data.exit_time,
              price: data.exit_price,
              side: "SELL",
              text: `Exit ${data.symbol} (${data.exit_reason || "signal"})`,
            });
          }
          if (markers.length > 0) {
            set((s) => ({
              tradeMarkers: [...s.tradeMarkers, ...markers].slice(-200),
            }));
          }
          callbacks?.onTrade?.(runId);
        } catch {
          /* ignore */
        }
      });

      /* signal event ------------------------------------------------ */
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
        } catch {
          /* ignore */
        }
      });

      /* status event ------------------------------------------------ */
      es.addEventListener("status", (e: MessageEvent) => {
        try {
          const data = JSON.parse(e.data);
          if (data.status === "stopped" || data.status === "error") {
            set({ sseStatus: "disconnected", reconnectCount: 0 });
            es.close();
          }
        } catch {
          /* ignore */
        }
        callbacks?.onStatus?.();
      });

      /* connection error / reconnection ----------------------------- */
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
        set({
          sseStatus: "reconnecting",
          reconnectCount,
          reconnectDelayMs: delayMs,
        });
        const timer = scheduleReconnect(() => doConnect(), reconnectCount);
        set({ reconnectTimer: timer });
      };
    };

    doConnect();
  }

  /* ---- disconnectSSE ---------------------------------------------- */
  function disconnectSSE() {
    const { eventSource, reconnectTimer } = get();
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
    }
    if (eventSource) {
      eventSource.close();
      set({
        eventSource: null,
        sseStatus: "disconnected",
        reconnectCount: 0,
        reconnectDelayMs: 0,
        reconnectTimer: null,
      });
    }
  }

  return { connectSSE, disconnectSSE };
}
