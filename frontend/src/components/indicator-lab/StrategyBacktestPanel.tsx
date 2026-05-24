import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Play, X, BarChart3 } from "lucide-react";
import { useI18n } from "@/lib/i18n";
import { authHeaders } from "@/lib/apiAuth";
import { StockInput } from "@/components/indicator-lab/StockInput";

interface StrategyBacktestPanelProps { code: string; onClose: () => void; }

export function StrategyBacktestPanel({ code, onClose }: StrategyBacktestPanelProps) {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [symbols, setSymbols] = useState("600519.SH, 000001.SZ");
  const [startDate, setStartDate] = useState("2024-01-01");
  const [endDate, setEndDate] = useState("2025-12-31");
  const [interval, setInterval] = useState("1D");
  const [source, setSource] = useState("auto");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runBacktest = async () => {
    setRunning(true); setError(null);
    const codes = symbols.split(",").map(s => s.trim()).filter(Boolean);
    try {
      const res = await fetch("/strategy-lab/backtest", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ code, codes, start_date: startDate, end_date: endDate, interval, source }),
      });
      const data = await res.json();
      if (data.success && data.run_id) { onClose(); navigate(`/runs/${data.run_id}`); }
      else setError(data.error || "Backtest failed");
    } catch (e) { setError(String(e)); }
    finally { setRunning(false); }
  };

  const labelClass = "text-xs font-medium text-muted-foreground";
  const inputClass = "w-full text-sm rounded-lg border border-border bg-background px-3 py-2 focus:outline-none focus:border-primary/50 transition-all duration-150";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-card border rounded-xl shadow-2xl w-[520px] animate-scale-in">
        <div className="flex items-center justify-between px-5 py-3.5 border-b">
          <div className="flex items-center gap-2.5">
            <div className="h-7 w-7 rounded-lg bg-success/10 flex items-center justify-center">
              <BarChart3 className="h-4 w-4 text-success" />
            </div>
            <h2 className="text-base font-semibold">{t.indicatorLabBacktest}</h2>
          </div>
          <button onClick={onClose} className="btn-ghost p-1.5 rounded-lg"><X className="h-4 w-4" /></button>
        </div>
        <div className="p-5 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5 col-span-2">
              <label className={labelClass}>{t.strategyLabSymbols}</label>
              <StockInput value={symbols} onChange={setSymbols} placeholder="600519.SH, 000001.SZ" multi />
            </div>
            <div className="space-y-1.5">
              <label className={labelClass}>{t.indicatorLabStartDate}</label>
              <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className={inputClass} />
            </div>
            <div className="space-y-1.5">
              <label className={labelClass}>{t.indicatorLabEndDate}</label>
              <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} className={inputClass} />
            </div>
            <div className="space-y-1.5">
              <label className={labelClass}>{t.indicatorLabInterval}</label>
              <select value={interval} onChange={(e) => setInterval(e.target.value)} className={inputClass}>
                {["1D", "1H", "4H"].map((v) => (<option key={v} value={v}>{v}</option>))}
              </select>
            </div>
            <div className="space-y-1.5">
              <label className={labelClass}>{t.indicatorLabSource}</label>
              <select value={source} onChange={(e) => setSource(e.target.value)} className={inputClass}>
                {["auto", "tushare", "akshare", "yfinance", "okx", "ccxt", "twelvedata", "finnhub", "futu", "tencent", "coingecko", "global_indices", "commodities"].map((v) => (<option key={v} value={v}>{v}</option>))}
              </select>
            </div>
          </div>
          {error && <div className="px-4 py-2.5 rounded-lg text-sm bg-danger/10 text-danger border border-danger/20">{error}</div>}
          <button onClick={runBacktest} disabled={running} className="btn-md btn-success w-full justify-center">
            <Play className="h-4 w-4" />{running ? t.indicatorLabRunning : t.indicatorLabRunBacktest}
          </button>
        </div>
      </div>
    </div>
  );
}
