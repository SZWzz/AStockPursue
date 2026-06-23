// Market types
export interface MarketRow {
  symbol: string;
  name: string;
  price: number;
  change: number;
  change_pct: number;
  volume: number;
  turnover?: number;
  high: number;
  low: number;
  open: number;
  prev_close: number;
}

// Portfolio types
export interface Position {
  symbol: string;
  side: 'long' | 'short';
  // Primary fields (actual backend response)
  size: number;
  entry_price: number;
  current_price: number;
  market_value: number;
  pnl: number;
  pnl_pct: number;
  realized_pnl: number;
  // Canonical spec aliases
  /** @deprecated use size */
  quantity?: number;
  /** @deprecated use entry_price */
  avg_price?: number;
  /** @deprecated use pnl */
  unrealized_pnl?: number;
  /** @deprecated use pnl_pct */
  unrealized_pnl_pct?: number;
}

export interface Portfolio {
  total_value: number;
  cash: number;
  market_value: number;
  unrealized_pnl: number;
  realized_pnl: number;
  positions: Position[];
  equity_curve?: EquityPoint[];
  // API-compat aliases (actual field names returned by backend)
  /** @deprecated use total_value */
  equity?: number;
  /** @deprecated use cash */
  available?: number;
  position_count?: number;
}

export interface EquityPoint {
  timestamp: number;
  equity: number;
  cash: number;
  position_count: number;
  // Component compatibility — used by EquityChart
  time: string | number;
}

// Order types
export type OrderSide = 'buy' | 'sell';
export type OrderType = 'market' | 'limit' | 'stop' | 'stop_limit';
export type OrderStatus = 'pending' | 'filled' | 'partially_filled' | 'cancelled' | 'rejected';

export interface Order {
  id: string;
  symbol: string;
  side: OrderSide;
  type: OrderType;
  price: number;
  quantity: number;
  filled: number;
  status: OrderStatus;
  created_at: string;
  updated_at: string;
}

// KPI
export interface KpiData {
  label: string;
  value: number;
  change: number;
  change_pct?: number;
  format?: 'currency' | 'percent' | 'number' | 'volume';
}

// Factor
export interface FactorSummary {
  id: string;
  name: string;
  formula: string;
  ic: number;
  rank_ic: number;
  sharpe: number;
  turnover: number;
}

// Backtest
export interface BacktestResult {
  id: string;
  symbol: string;
  start_date: string;
  end_date: string;
  initial_capital: number;
  final_equity: number;
  total_return: number;
  annual_return: number;
  sharpe_ratio: number;
  max_drawdown: number;
  win_rate: number;
  total_trades: number;
  equity_curve: EquityPoint[];
}

// API wrapper
export interface ApiResponse<T> {
  data: T;
  error?: string;
}

// WebSocket
export interface WSMessage {
  channel: string;
  data: unknown;
}

export interface TickerData {
  symbol: string;
  price: number;
  change: number;
  change_pct: number;
}

// Dashboard auxiliary types
export interface GeopoliticsTopic {
  name?: string;
  topic?: string;
  risk_level?: string;
}

export interface NewsArticle {
  title: string;
  url?: string;
  published_at?: string;
  sentiment?: number;
}
