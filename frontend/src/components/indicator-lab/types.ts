import type { EquityPoint } from "@/types/api";

export interface QualityHint {
  severity: "error" | "warn" | "info";
  code: string;
  params?: Record<string, unknown>;
}

export interface ParamDef {
  name: string;
  type: "int" | "float" | "bool" | "str";
  default: string | number | boolean;
  description: string;
  values?: (string | number)[];
}

export interface StrategyConfig {
  stopLossPct?: number;
  takeProfitPct?: number;
  entryPct?: number;
  trailingEnabled?: boolean;
  trailingStopPct?: number;
  trailingActivationPct?: number;
  tradeDirection?: "long" | "short" | "both";
}

export interface IndicatorInfo {
  id: string;
  name: string;
  description: string;
  param_count: number;
  strategy_config: StrategyConfig;
  created_at: string;
  updated_at: string;
}

export interface IndicatorDetail extends IndicatorInfo {
  code: string;
}

export interface VerifyResult {
  success: boolean;
  error: string | null;
  quality_hints: QualityHint[];
  params: ParamDef[];
  strategy_config: StrategyConfig;
  plots_count: number;
  signals_count: number;
  has_buy_sell: boolean;
}

export interface BacktestMetrics {
  total_return: number;
  sharpe: number;
  max_drawdown: number;
  win_rate: number;
  trade_count: number;
  profit_factor: number;
}

export interface TradeRecord {
  entry_time: string;
  exit_time: string;
  side: string;
  pnl: number;
  return_pct: number;
}

export interface BacktestResult {
  success: boolean;
  error: string | null;
  metrics: BacktestMetrics | null;
  equity_curve: EquityPoint[] | null;
  trades: TradeRecord[] | null;
  run_dir: string | null;
}
