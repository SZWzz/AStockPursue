/** Maps metric keys to i18n translation keys */
export const METRIC_I18N_KEYS: Record<string, string> = {
  total_return: "metricTotalReturn",
  annual_return: "metricAnnualReturn",
  sharpe: "metricSharpe",
  max_drawdown: "metricMaxDrawdown",
  win_rate: "metricWinRate",
  trade_count: "metricTradeCount",
  final_value: "metricFinalValue",
  calmar: "metricCalmar",
  sortino: "metricSortino",
  profit_loss_ratio: "metricProfitLossRatio",
  max_consecutive_loss: "metricMaxConsecutiveLoss",
  avg_holding_days: "metricAvgHoldingDays",
  benchmark_return: "metricBenchmarkReturn",
  excess_return: "metricExcessReturn",
  information_ratio: "metricIR",
};

/** Resolve metric label using i18n translations object */
export function getMetricLabel(k: string, t: Record<string, string>): string {
  const i18nKey = METRIC_I18N_KEYS[k];
  return i18nKey ? (t[i18nKey] || k) : k;
}

const PCT_KEYS = ["total_return", "annual_return", "win_rate", "max_drawdown", "benchmark_return", "excess_return"];
const RATIO_KEYS = ["sharpe", "calmar", "sortino", "profit_loss_ratio", "information_ratio"];
const INT_KEYS = ["trade_count", "max_consecutive_loss"];
const NEUTRAL_KEYS = new Set(["trade_count", "avg_holding_days", "final_value"]);

export function formatMetricVal(k: string, v: number): string {
  if (PCT_KEYS.includes(k)) {
    const sign = v > 0 ? "+" : "";
    return `${sign}${(v * 100).toFixed(2)}%`;
  }
  if (RATIO_KEYS.includes(k)) {
    const sign = v > 0 ? "+" : "";
    return `${sign}${v.toFixed(2)}`;
  }
  if (INT_KEYS.includes(k)) return String(Math.round(v));
  if (k === "final_value") return v.toLocaleString(undefined, { maximumFractionDigits: 0 });
  if (k === "avg_holding_days") return v.toFixed(1);
  return v.toFixed(4);
}

export function metricSentiment(k: string, v: number): "positive" | "neutral" | "negative" {
  if (NEUTRAL_KEYS.has(k)) return "neutral";
  if (k === "max_drawdown") return v > -0.05 ? "positive" : v > -0.2 ? "neutral" : "negative";
  if (k === "max_consecutive_loss") return v <= 3 ? "positive" : v <= 6 ? "neutral" : "negative";
  if (k === "win_rate") return v >= 0.5 ? "positive" : v >= 0.35 ? "neutral" : "negative";
  if (k === "sharpe" || k === "calmar" || k === "sortino") return v >= 1.0 ? "positive" : v >= 0.3 ? "neutral" : "negative";
  if (k === "information_ratio") return v >= 0.5 ? "positive" : v >= 0 ? "neutral" : "negative";
  return v > 0 ? "positive" : v === 0 ? "neutral" : "negative";
}

export const DISPLAY_ORDER = [
  "total_return", "annual_return", "sharpe", "max_drawdown", "win_rate", "trade_count",
  "calmar", "sortino", "profit_loss_ratio", "max_consecutive_loss",
  "benchmark_return", "excess_return", "information_ratio", "final_value", "avg_holding_days",
];

export function formatTimestamp(ts: number): string {
  const d = new Date(ts);
  return `${d.getHours().toString().padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}`;
}

export function abbreviateNum(v: number): string {
  const abs = Math.abs(v);
  if (abs >= 1e9) return (v / 1e9).toFixed(1) + "B";
  if (abs >= 1e6) return (v / 1e6).toFixed(1) + "M";
  if (abs >= 1e4) return (v / 1e3).toFixed(0) + "K";
  return v.toLocaleString();
}

/* ── OLED Terminal formatters ─────────────────────────────────────── */

/**
 * Format a price with currency symbol.
 * Use with font-mono + tabular-nums for aligned columns.
 */
export function formatPrice(v: number, decimals = 2, currency = "¥"): string {
  const abs = Math.abs(v);
  const fixed = abs.toFixed(decimals);
  return `${v < 0 ? "-" : ""}${currency}${fixed}`;
}

/**
 * Format a percentage change with sign.
 * e.g., formatPercent(0.0347) → "+3.47%"
 */
export function formatPercent(v: number, decimals = 2): string {
  const sign = v > 0 ? "+" : "";
  return `${sign}${(v * 100).toFixed(decimals)}%`;
}

/**
 * Format volume with appropriate suffix (K, M, B).
 */
export function formatVolume(v: number): string {
  const abs = Math.abs(v);
  if (abs >= 1e9) return (v / 1e9).toFixed(2) + "B";
  if (abs >= 1e6) return (v / 1e6).toFixed(2) + "M";
  if (abs >= 1e4) return (v / 1e3).toFixed(0) + "K";
  return v.toLocaleString();
}

/**
 * Format a large number with Chinese units (万/亿).
 * Used for A-share volume and turnover displays.
 */
export function formatLargeNum(v: number): string {
  const abs = Math.abs(v);
  if (abs >= 1e8) return (v / 1e8).toFixed(2) + "亿";
  if (abs >= 1e4) return (v / 1e4).toFixed(2) + "万";
  return v.toLocaleString();
}

/**
 * Get the CSS color class for a directional value.
 * Respects Chinese market convention via html[lang="zh"] CSS vars.
 */
export function directionColor(v: number): "text-up" | "text-down" | "" {
  if (v > 0) return "text-up";
  if (v < 0) return "text-down";
  return "";
}

/**
 * Get the CSS color class for profit/loss sentiment.
 */
export function pnlColor(v: number): "text-up" | "text-down" | "text-muted-foreground" {
  if (v > 0) return "text-up";
  if (v < 0) return "text-down";
  return "text-muted-foreground";
}
