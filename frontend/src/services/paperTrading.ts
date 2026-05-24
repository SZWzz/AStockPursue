import { authHeaders } from "@/lib/apiAuth";

const BASE = "";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const mergedHeaders: Record<string, string> = {
    "Content-Type": "application/json",
    ...authHeaders(),
  };
  if (options?.headers) {
    new Headers(options.headers).forEach((value, key) => {
      mergedHeaders[key] = value;
    });
  }
  const { headers: _, ...rest } = options ?? {};
  const res = await fetch(`${BASE}${path}`, { ...rest, headers: mergedHeaders });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail || body.message || detail;
    } catch { /* ignore */ }
    throw new Error(detail);
  }
  const text = await res.text();
  return text ? JSON.parse(text) : ({} as T);
}

// ── Types ────────────────────────────────────────────────────────────

export interface RiskConfig {
  stop_loss_pct: number;
  take_profit_pct: number;
  trailing_stop_pct: number;
  max_daily_loss_pct: number;
  max_position_pct: number;
}

export interface CreateRunRequest {
  run_name: string;
  market: string;
  codes: string[];
  interval: string;
  initial_capital: number;
  strategy_code: string;
  risk_config: RiskConfig;
}

export interface RunSummary {
  id: string;
  run_name: string;
  market: string;
  status: "stopped" | "running" | "paused" | "error";
  tick_mode: boolean;
  state: "flat" | "long" | "short";
  current_equity: number;
  total_return_pct: number;
  trade_count: number;
  open_positions: number;
  created_at: string | null;
  started_at: string | null;
  last_bar_time: string | null;
}

export interface Position {
  symbol: string;
  direction: number;
  entry_price: number;
  entry_time: string;
  size: number;
  leverage: number;
  current_price: number | null;
  unrealized_pnl: number | null;
  pnl_pct: number | null;
}

export interface Trade {
  id: number;
  symbol: string;
  direction: number;
  entry_price: number;
  exit_price: number;
  entry_time: string;
  exit_time: string;
  size: number;
  leverage: number;
  pnl: number;
  pnl_pct: number;
  exit_reason: string;
  holding_bars: number;
  commission: number;
}

export interface EquityPoint {
  point_time: string;
  equity: number;
  capital: number;
  unrealized: number;
  drawdown: number;
}

export interface RunDetail {
  run: RunSummary;
  positions: Position[];
  recent_trades: Trade[];
}

export interface SSEEvent {
  event: string;
  data: unknown;
}

// ── API ──────────────────────────────────────────────────────────────

export const paperTradingApi = {
  createRun: (req: CreateRunRequest) =>
    request<{ id: string; message: string }>("/paper-trading/runs", {
      method: "POST",
      body: JSON.stringify(req),
    }),

  listRuns: () => request<RunSummary[]>("/paper-trading/runs"),

  getRun: (runId: string) => request<RunDetail>(`/paper-trading/runs/${runId}`),

  startRun: (runId: string) =>
    request<{ message: string }>(`/paper-trading/runs/${runId}/start`, {
      method: "POST",
    }),

  stopRun: (runId: string, closePositions = true) =>
    request<{ message: string }>(
      `/paper-trading/runs/${runId}/stop?close_positions=${closePositions}`,
      { method: "POST" }
    ),

  pauseRun: (runId: string) =>
    request<{ message: string }>(`/paper-trading/runs/${runId}/pause`, {
      method: "POST",
    }),

  resumeRun: (runId: string) =>
    request<{ message: string }>(`/paper-trading/runs/${runId}/resume`, {
      method: "POST",
    }),

  deleteRun: (runId: string) =>
    request<{ message: string }>(`/paper-trading/runs/${runId}`, {
      method: "DELETE",
    }),

  getEquity: (runId: string, since?: string) => {
    const params = since ? `?since=${encodeURIComponent(since)}` : "";
    return request<EquityPoint[]>(`/paper-trading/runs/${runId}/equity${params}`);
  },

  getTrades: (runId: string, limit = 100, offset = 0) =>
    request<Trade[]>(
      `/paper-trading/runs/${runId}/trades?limit=${limit}&offset=${offset}`
    ),

  getSSEUrl: (runId: string) => {
    const jwt = window.localStorage.getItem("vt_token");
    const base = `${BASE}/paper-trading/runs/${runId}/stream`;
    return jwt ? `${base}?jwt=${encodeURIComponent(jwt)}` : base;
  },
};
