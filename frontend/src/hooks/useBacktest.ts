import { useState, useRef, useCallback } from "react";
import { api } from "@/lib/api";
import type { PriceBar, TradeMarker, EquityPoint, IndicatorPoint } from "@/lib/api";

export function useBacktest() {
  const [priceData, setPriceData] = useState<PriceBar[]>([]);
  const [chartLoading, setChartLoading] = useState(false);
  const [chartError, setChartError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [backtestRunning, setBacktestRunning] = useState(false);
  const [btTradeMarkers, setBtTradeMarkers] = useState<TradeMarker[]>([]);
  const [btEquityCurve, setBtEquityCurve] = useState<EquityPoint[]>([]);
  const [btIndicatorSeries, setBtIndicatorSeries] = useState<Record<string, IndicatorPoint[]>>({});
  const [btMetrics, setBtMetrics] = useState<Record<string, number> | null>(null);

  const clearPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const fetchOHLCV = useCallback(async (
    symbol: string,
    startDate: string,
    endDate: string,
    source: string,
    interval: string,
  ) => {
    setChartLoading(true);
    setChartError(null);
    try {
      const data = await api.getOHLCV({ symbol, start_date: startDate, end_date: endDate, source, interval });
      setPriceData(data.bars || []);
      setBtTradeMarkers([]);
      setBtEquityCurve([]);
      setBtMetrics(null);
      setBtIndicatorSeries({});
    } catch (e) {
      setChartError(String(e));
    } finally {
      setChartLoading(false);
    }
  }, []);

  const handleRunBacktest = useCallback(async (runBacktestFn: () => Promise<string>) => {
    setBacktestRunning(true);
    setChartError(null);
    clearPolling();
    try {
      const runId = await runBacktestFn();

      pollRef.current = setInterval(async () => {
        try {
          const run = await api.getRun(runId);
          if (run.status === "success" || run.status === "failed") {
            clearPolling();
            setBacktestRunning(false);
          }
          const sym = run.price_series ? Object.keys(run.price_series)[0] : null;
          if (run.price_series && sym) setPriceData(run.price_series[sym]);
          if (run.trade_markers) setBtTradeMarkers(run.trade_markers);
          if (run.equity_curve) setBtEquityCurve(run.equity_curve as EquityPoint[]);
          if (run.indicator_series && sym) {
            setBtIndicatorSeries(run.indicator_series[sym] as unknown as Record<string, IndicatorPoint[]>);
          }
          if (run.metrics) setBtMetrics(run.metrics as Record<string, number>);
        } catch {
          /* ignore poll errors */
        }
      }, 1000);
      return runId;
    } catch (e) {
      setChartError(String(e));
      setBacktestRunning(false);
      return null;
    }
  }, [clearPolling]);

  return {
    priceData, setPriceData,
    chartLoading, setChartLoading,
    chartError, setChartError,
    backtestRunning,
    btTradeMarkers, setBtTradeMarkers,
    btEquityCurve, setBtEquityCurve,
    btIndicatorSeries, setBtIndicatorSeries,
    btMetrics, setBtMetrics,
    handleRunBacktest,
    fetchOHLCV,
    clearPolling,
  };
}
