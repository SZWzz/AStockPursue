import { useRef, useState, useEffect } from "react";
import { Play, Loader2, AlertTriangle, TrendingUp, BarChart3 } from "lucide-react";
import type { PriceBar, TradeMarker, EquityPoint, IndicatorPoint } from "@/lib/api";
import { CandlestickChart } from "@/components/charts/CandlestickChart";
import { EquityChart } from "@/components/charts/EquityChart";
import { StockInput } from "@/components/indicator-lab/StockInput";

export interface ChartPanelProps {
  symbol: string;
  onSymbolChange: (s: string) => void;
  multiSymbol?: boolean;
  startDate: string;
  endDate: string;
  onStartDateChange: (d: string) => void;
  onEndDateChange: (d: string) => void;
  source: string;
  onSourceChange: (s: string) => void;
  interval: string;
  onIntervalChange: (i: string) => void;
  onFetch: () => Promise<void>;
  onRunBacktest: () => Promise<void>;
  priceData: PriceBar[];
  loading: boolean;
  error: string | null;
  tradeMarkers?: TradeMarker[];
  equityCurve?: EquityPoint[];
  indicatorSeries?: Record<string, IndicatorPoint[]>;
  backtestRunning: boolean;
  backtestLabel?: string;
}

const labelClass = "text-[11px] font-medium text-muted-foreground whitespace-nowrap";
const inputClass =
  "w-full text-xs rounded-md border border-border bg-background px-2 py-1.5 focus:outline-none focus:border-primary/50 transition-all duration-150";

export function ChartPanel({
  symbol,
  onSymbolChange,
  multiSymbol = false,
  startDate,
  endDate,
  onStartDateChange,
  onEndDateChange,
  source,
  onSourceChange,
  interval,
  onIntervalChange,
  onFetch,
  onRunBacktest,
  priceData,
  loading,
  error,
  tradeMarkers,
  equityCurve,
  indicatorSeries,
  backtestRunning,
  backtestLabel = "Run Backtest",
}: ChartPanelProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [chartHeight, setChartHeight] = useState(400);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      const h = el.clientHeight;
      setChartHeight(Math.max(280, h - 8));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const busy = loading || backtestRunning;

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Control bar */}
      <div className="shrink-0 px-3 py-2 border-b space-y-2">
        <div className="flex items-center gap-2 flex-wrap">
          <div className="flex-1 min-w-[120px]">
            <label className={labelClass}>Symbol</label>
            <StockInput
              value={symbol}
              onChange={onSymbolChange}
              placeholder="600519.SH"
              multi={multiSymbol}
            />
          </div>
          <div>
            <label className={labelClass}>Start</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => onStartDateChange(e.target.value)}
              className={inputClass}
              disabled={busy}
            />
          </div>
          <div>
            <label className={labelClass}>End</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => onEndDateChange(e.target.value)}
              className={inputClass}
              disabled={busy}
            />
          </div>
          <div>
            <label className={labelClass}>Source</label>
            <select value={source} onChange={(e) => onSourceChange(e.target.value)} className={inputClass} disabled={busy}>
              {["auto", "tushare", "akshare", "yfinance", "okx", "ccxt", "twelvedata", "finnhub", "futu", "tencent", "coingecko", "global_indices", "commodities"].map((v) => (
                <option key={v} value={v}>{v}</option>
              ))}
            </select>
          </div>
          <div>
            <label className={labelClass}>Interval</label>
            <select value={interval} onChange={(e) => onIntervalChange(e.target.value)} className={inputClass} disabled={busy}>
              {["1D", "1H", "4H"].map((v) => (<option key={v} value={v}>{v}</option>))}
            </select>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={onFetch} disabled={busy} className="btn-sm btn-outline flex items-center gap-1.5">
            {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <BarChart3 className="h-3.5 w-3.5" />}
            Load Data
          </button>
          <button onClick={onRunBacktest} disabled={busy} className="btn-sm btn-success flex items-center gap-1.5">
            {backtestRunning ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
            {backtestRunning ? "Running…" : backtestLabel}
          </button>
          {equityCurve && equityCurve.length > 0 && (
            <span className="text-xs text-muted-foreground flex items-center gap-1 ml-auto">
              <TrendingUp className="h-3.5 w-3.5 text-success" />
              Backtest complete
            </span>
          )}
        </div>
      </div>

      {/* Chart area */}
      <div ref={containerRef} className="flex-1 min-h-0 p-2">
        {error && (
          <div className="flex items-center gap-2 px-3 py-2 mb-2 rounded-md text-xs bg-danger/10 text-danger border border-danger/20">
            <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
            {error}
          </div>
        )}
        {loading ? (
          <div className="flex items-center justify-center h-full text-sm text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin mr-2" />
            Loading data…
          </div>
        ) : priceData.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-sm text-muted-foreground gap-2">
            <BarChart3 className="h-8 w-8 opacity-30" />
            <span>Select a symbol and click "Load Data"</span>
          </div>
        ) : (
          <CandlestickChart
            data={priceData}
            markers={tradeMarkers}
            indicators={indicatorSeries}
            height={chartHeight}
          />
        )}
      </div>

      {/* Equity sub-chart after backtest */}
      {equityCurve && equityCurve.length > 0 && (
        <div className="shrink-0 border-t p-2">
          <EquityChart data={equityCurve} height={130} />
        </div>
      )}
    </div>
  );
}
