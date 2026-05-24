import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Play, X, BarChart3 } from "lucide-react";
import { useI18n } from "@/lib/i18n";
import { authHeaders } from "@/lib/apiAuth";

interface BacktestPanelProps { code: string; onClose: () => void; }

export function BacktestPanel({ code, onClose }: BacktestPanelProps) {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [symbol, setSymbol] = useState("600519.SH");
  const [startDate, setStartDate] = useState("2024-01-01");
  const [endDate, setEndDate] = useState("2025-12-31");
  const [interval, setInterval] = useState("1D");
  const [source, setSource] = useState("auto");
  const [leverage, setLeverage] = useState(1);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runBacktest = async () => {
    setRunning(true);
    setError(null);
    try {
      const res = await fetch("/indicator-lab/backtest", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ code, symbol, start_date: startDate, end_date: endDate, interval, source, leverage }),
      });
      const data = await res.json();
      if (data.success && data.run_id) {
        onClose();
        navigate(`/runs/${data.run_id}`);
      } else {
        setError(data.error || "Backtest failed");
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-card border rounded-xl shadow-2xl w-[500px]">
        <div className="flex items-center justify-between px-4 py-3 border-b">
          <div className="flex items-center gap-2"><BarChart3 className="h-4 w-4 text-primary" /><h2 className="text-sm font-semibold">{t.indicatorLabBacktest}</h2></div>
          <button onClick={onClose} className="p-1 text-muted-foreground hover:text-foreground rounded"><X className="h-4 w-4" /></button>
        </div>
        <div className="p-4 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1"><label className="text-[10px] text-muted-foreground font-medium">{t.indicatorLabSymbol}</label><input value={symbol} onChange={(e) => setSymbol(e.target.value)} className="w-full text-xs rounded border border-border bg-background px-2 py-1.5 font-mono" /></div>
            <div className="space-y-1"><label className="text-[10px] text-muted-foreground font-medium">{t.indicatorLabInterval}</label><select value={interval} onChange={(e) => setInterval(e.target.value)} className="w-full text-xs rounded border border-border bg-background px-2 py-1.5">{["1D","1H","4H"].map(v=>(<option key={v} value={v}>{v}</option>))}</select></div>
            <div className="space-y-1"><label className="text-[10px] text-muted-foreground font-medium">{t.indicatorLabStartDate}</label><input type="date" value={startDate} onChange={(e)=>setStartDate(e.target.value)} className="w-full text-xs rounded border border-border bg-background px-2 py-1.5" /></div>
            <div className="space-y-1"><label className="text-[10px] text-muted-foreground font-medium">{t.indicatorLabEndDate}</label><input type="date" value={endDate} onChange={(e)=>setEndDate(e.target.value)} className="w-full text-xs rounded border border-border bg-background px-2 py-1.5" /></div>
            <div className="space-y-1"><label className="text-[10px] text-muted-foreground font-medium">{t.indicatorLabSource}</label><select value={source} onChange={(e)=>setSource(e.target.value)} className="w-full text-xs rounded border border-border bg-background px-2 py-1.5">{["auto","akshare","yfinance","tushare"].map(v=>(<option key={v} value={v}>{v}</option>))}</select></div>
            <div className="space-y-1"><label className="text-[10px] text-muted-foreground font-medium">{t.indicatorLabLeverage}</label><input type="number" min={1} max={20} value={leverage} onChange={(e)=>setLeverage(Number(e.target.value))} className="w-full text-xs rounded border border-border bg-background px-2 py-1.5" /></div>
          </div>
          {error && <div className="px-3 py-2 rounded text-xs bg-danger/10 text-danger border border-danger/20">{error}</div>}
          <button onClick={runBacktest} disabled={running} className="flex items-center gap-2 px-4 py-2 text-sm rounded bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 w-full justify-center">
            <Play className="h-4 w-4" />{running ? t.indicatorLabRunning : t.indicatorLabRunBacktest}
          </button>
        </div>
      </div>
    </div>
  );
}
