import { useEffect, useState, useCallback, useMemo } from "react";
import { Loader2, TrendingUp, Library, List, Plus, Check, Save, Rocket } from "lucide-react";
import { toast } from "sonner";
import { usePaperTradingRunStore } from "@/stores/paperTradingRunStore";
import { usePaperTradingLiveStore } from "@/stores/paperTradingLiveStore";
import { useI18n } from "@/lib/i18n";
import { authHeaders } from "@/lib/apiAuth";
import { api, type TradeMarker } from "@/lib/api";
import { CodeEditor } from "@/components/indicator-lab/CodeEditor";
import { CandlestickChart } from "@/components/charts/CandlestickChart";
import { StockInput } from "@/components/indicator-lab/StockInput";
import EquityChart from "@/components/paper-trading/EquityChart";
import PositionTable from "@/components/paper-trading/PositionTable";
import TradeHistoryTable from "@/components/paper-trading/TradeHistoryTable";
import RiskConfigForm, { defaultConfig } from "@/components/paper-trading/RiskConfigForm";
import PaperTradingCard from "@/components/paper-trading/PaperTradingCard";
import MonthlyReturnHeatmap from "@/components/paper-trading/MonthlyReturnHeatmap";
import { useBacktest } from "@/hooks/useBacktest";
import type { RiskConfig, CreateRunRequest } from "@/services/paperTrading";

const MARKET_OPTIONS: { value: string; labelKey: string }[] = [
  { value: "a_share", labelKey: "ptMarketAShare" },
  { value: "us_equity", labelKey: "ptMarketUS" },
  { value: "hk_equity", labelKey: "ptMarketHK" },
  { value: "crypto", labelKey: "ptMarketCrypto" },
];

const INTERVAL_OPTIONS: { value: string; labelKey: string }[] = [
  { value: "1D", labelKey: "ptIntervalDaily" },
  { value: "1H", labelKey: "ptInterval1H" },
  { value: "4H", labelKey: "ptInterval4H" },
  { value: "1W", labelKey: "ptIntervalWeekly" },
];

type LeftTab = "library" | "runs";
type LibrarySource = "strategy-lab" | "chat" | "";

interface StrategyItem {
  id: string;
  name: string;
  code: string;
  source: LibrarySource;
}

const DEFAULT_CODE = `import pandas as pd

class SignalEngine:
    def generate(self, data_map: dict[str, pd.DataFrame]) -> dict[str, pd.Series]:
        """Return target weights in [-1, 1] for each code."""
        result = {}
        for code, df in data_map.items():
            weights = pd.Series(0.0, index=df.index)
            # Your strategy logic here
            result[code] = weights
        return result
`;

export default function PaperTrading() {
  const { t } = useI18n();
  const fetchRuns = usePaperTradingRunStore((s) => s.fetchRuns);
  const disconnectSSE = usePaperTradingLiveStore((s) => s.disconnectSSE);
  const [leftTab, setLeftTab] = useState<LeftTab>("library");
  const [librarySource, setLibrarySource] = useState<LibrarySource>("strategy-lab");
  const [strategies, setStrategies] = useState<StrategyItem[]>([]);
  const [strategiesLoading, setStrategiesLoading] = useState(false);
  const [detailTab, setDetailTab] = useState<"positions" | "trades" | "log" | "stats" | "risk">("positions");
  const [showDeploy, setShowDeploy] = useState(false);

  // Strategy editor state
  const [code, setCode] = useState(DEFAULT_CODE);

  // Deploy form state (independent from right-panel preview)
  const [runName, setRunName] = useState("");
  const [market, setMarket] = useState("a_share");
  const [deployCodes, setDeployCodes] = useState("");
  const [interval, setInterval] = useState("1D");
  const [initialCapital, setInitialCapital] = useState(100000);
  const [riskConfig, setRiskConfig] = useState<RiskConfig>({ ...defaultConfig });
  const [selectedStrategy, setSelectedStrategy] = useState<StrategyItem | null>(null);
  const [creating, setCreating] = useState(false);
  const [autoStart, setAutoStart] = useState(true);
  const [riskSaving, setRiskSaving] = useState(false);

  // Right-panel preview state (independent from deploy modal)
  const [previewSymbol, setPreviewSymbol] = useState("");
  const [btMetrics, setBtMetrics] = useState<Record<string, number> | null>(null);
  const [btTradeMarkers, setBtTradeMarkers] = useState<TradeMarker[]>([]);

  const {
    priceData, setPriceData,
    chartLoading, setChartLoading,
    chartError, setChartError,
    fetchOHLCV,
  } = useBacktest();

  const runStore = usePaperTradingRunStore();
  const liveStore = usePaperTradingLiveStore();
  const selectedRun = runStore.activeRunDetail?.run;
  const sseConnected = liveStore.sseStatus === "connected";

  // K-line data from paper-trading engine (real bars, live-updated via SSE)
  const runChartData = useMemo(() => {
    const ohlcv = liveStore.ohlcvData;
    if (!ohlcv || Object.keys(ohlcv).length === 0) return [];
    // Pick the first symbol's bars — they all share the same timeline
    const firstCode = Object.keys(ohlcv)[0];
    return (ohlcv[firstCode] || []).map((b) => ({
      time: b.time,
      open: b.open,
      high: b.high,
      low: b.low,
      close: b.close,
      volume: b.volume,
    }));
  }, [liveStore.ohlcvData]);

  useEffect(() => {
    fetchRuns();
    return () => { disconnectSSE(); };
  }, [fetchRuns, disconnectSSE]);

  // ── Strategy library loading ─────────────────────────────────────────────

  const loadStrategies = useCallback(async (source: LibrarySource) => {
    setStrategiesLoading(true);
    setStrategies([]);
    try {
      if (source === "strategy-lab") {
        const res = await fetch("/v1/strategy-lab/list", { headers: authHeaders() });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        const list = (json.strategies || []).map((s: { id: string; name: string }) => ({
          id: s.id, name: s.name, code: "", source: "strategy-lab" as LibrarySource,
        }));
        setStrategies(list);
      } else if (source === "chat") {
        const sessions = await api.listSessions();
        const items: StrategyItem[] = [];
        for (const s of sessions.slice(0, 20)) {
          try {
            const msgs = await api.getSessionMessages(s.session_id);
            for (const m of (msgs || [])) {
              const rid = m.metadata?.run_id as string | undefined;
              if (rid) {
                const codeMap = await api.getRunCode(rid);
                if (codeMap["signal_engine.py"]) {
                  items.push({ id: rid, name: s.title || rid.slice(0, 8), code: codeMap["signal_engine.py"], source: "chat" });
                  break;
                }
              }
            }
          } catch { /* skip */ }
        }
        setStrategies(items);
      }
    } catch {
      setStrategies([]);
    } finally {
      setStrategiesLoading(false);
    }
  }, []);

  useEffect(() => {
    if (leftTab === "library") loadStrategies(librarySource);
  }, [leftTab, librarySource, loadStrategies]);

  // ── Load strategy code ──────────────────────────────────────────────────

  const loadStrategyCode = async (item: StrategyItem) => {
    setSelectedStrategy(item);
    if (item.code) { setCode(item.code); return; }
    try {
      const res = await fetch(`/v1/strategy-lab/${item.id}`, { headers: authHeaders() });
      if (!res.ok) return;
      const json = await res.json();
      const loaded = { ...item, code: json.code || "" };
      setSelectedStrategy(loaded);
      setCode(json.code || "");
    } catch {
      /* ignore */
    }
  };

  // ── Quick deploy from strategy card ─────────────────────────────────────

  const handleQuickDeploy = (item: StrategyItem) => {
    loadStrategyCode(item);
    setRunName(item.name);
    setShowDeploy(true);
  };

  // ── OHLCV fetch for preview ─────────────────────────────────────────────

  const handlePreviewFetch = useCallback((symbol: string) => {
    const today = new Date().toISOString().slice(0, 10);
    const oneYearAgo = new Date(Date.now() - 365 * 86400000).toISOString().slice(0, 10);
    if (symbol) fetchOHLCV(symbol, oneYearAgo, today, "auto", "1D");
  }, [fetchOHLCV]);

  // ── Shared quick-backtest logic ─────────────────────────────────────────

  const runQuickBacktest = useCallback(async (btCode: string, btSymbols: string) => {
    const syms = btSymbols.split(",").map(s => s.trim()).filter(Boolean);
    if (!btCode || syms.length === 0) return;
    try {
      const res = await fetch("/v1/strategy-lab/backtest", {
        method: "POST", headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ code: btCode, codes: syms, start_date: "2023-01-01", end_date: new Date().toISOString().slice(0, 10), source: "auto", interval: "1D", initial_cash: initialCapital }),
      });
      const d = await res.json();
      if (d.success && d.run_id) {
        const run = await api.getRun(d.run_id);
        if (run.price_series) { const fs = Object.keys(run.price_series)[0]; if (fs) setPriceData(run.price_series[fs]); }
        if (run.metrics) setBtMetrics(run.metrics as Record<string, number>);
        if (run.trade_markers) setBtTradeMarkers(run.trade_markers);
      } else { throw new Error(d.error || "Backtest failed"); }
    } catch (e) { throw e; }
  }, [initialCapital, setPriceData]);

  // ── Clone ──────────────────────────────────────────────────────────────

  const handleClone = async (runId: string) => {
    const meta = runStore.runs.find(r => r.id === runId);
    if (!meta) return;
    setRunName(meta.run_name + " (副本)");
    setMarket(meta.market);
    setInterval("1D");
    setDeployCodes("");

    try {
      const res = await fetch(`/v1/runs/${runId}/code`, { headers: authHeaders() });
      const codeMap = await res.json();
      if (codeMap["signal_engine.py"]) setCode(codeMap["signal_engine.py"]);
    } catch { /* ignore */ }

    try {
      const cfgRes = await fetch(`/v1/runs/${runId}/config`, { headers: authHeaders() });
      const cfg = await cfgRes.json();
      if (cfg.codes && Array.isArray(cfg.codes)) setDeployCodes(cfg.codes.join(", "));
      if (cfg.initial_capital) setInitialCapital(cfg.initial_capital);
    } catch { /* ignore */ }

    setShowDeploy(true);
    setLeftTab("library");
  };

  // ── Deploy ──────────────────────────────────────────────────────────────

  const handleDeploy = async () => {
    if (!runName.trim() || !deployCodes.trim()) return;
    setCreating(true);
    try {
      const vRes = await fetch("/v1/strategy-lab/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ code }),
      });
      const vData = await vRes.json();
      if (!vData.success) {
        toast.error(t.ptStrategyVerifyFail.replace("{error}", vData.error));
        setCreating(false);
        return;
      }

      const req: CreateRunRequest = {
        run_name: runName.trim(),
        market,
        codes: deployCodes.split(",").map((s) => s.trim()).filter(Boolean),
        interval,
        initial_capital: initialCapital,
        strategy_code: code,
        risk_config: riskConfig,
      };
      const runId = await runStore.createRun(req);
      setShowDeploy(false);
      setLeftTab("runs");
      if (autoStart && runId) {
        setTimeout(() => runStore.startRun(runId), 500);
      }
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : t.ptCreateFailed);
    } finally {
      setCreating(false);
    }
  };

  // ── Risk config save ────────────────────────────────────────────────────

  const handleSaveRisk = async () => {
    if (!selectedRun?.id) return;
    setRiskSaving(true);
    try {
      await fetch(`/v1/runs/${selectedRun.id}/risk`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify(riskConfig),
      });
    } catch (e) {
      toast.error(String(e));
    } finally {
      setRiskSaving(false);
    }
  };

  // ── Select run (with SSE management) ────────────────────────────────────

  const handleSelectRun = (id: string) => {
    if (runStore.activeRunId && runStore.activeRunId !== id) {
      disconnectSSE();
    }
    runStore.selectRun(id);
    liveStore.fetchEquity(id);
    liveStore.fetchTrades(id);
    const run = runStore.runs.find(r => r.id === id);
    if (run?.status === "running") liveStore.connectSSE(id);
  };

  const labelClass = "text-[11px] font-medium text-muted-foreground";
  const inputClass = "w-full text-xs rounded-md border border-border bg-background px-2 py-1.5 focus:outline-none focus:border-primary/50";

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-3 shrink-0">
        <h1 className="text-xl font-bold">{t.ptTitle}</h1>
        <div className="flex items-center gap-2">
          <button className="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700" onClick={() => { setRunName(""); setDeployCodes(""); setSelectedStrategy(null); setShowDeploy(true); setLeftTab("library"); }}>
            <Plus className="h-3.5 w-3.5 inline mr-1" />{t.newStrategy}
          </button>
        </div>
      </div>

      {/* Deploy modal */}
      {showDeploy && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="bg-card border rounded-xl shadow-2xl w-[600px] max-h-[80vh] overflow-auto animate-scale-in p-5 space-y-4">
            <h2 className="text-lg font-bold">{t.deployToPaper}</h2>
            {selectedStrategy && (
              <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-primary/5 border border-primary/20 text-sm">
                <Check className="h-4 w-4 text-primary shrink-0" />
                <span className="text-muted-foreground">{t.ptSelectedStrategy}：</span>
                <span className="font-medium truncate">{selectedStrategy.name}</span>
                <span className="text-muted-foreground text-xs font-mono">({selectedStrategy.id.slice(0, 12)})</span>
              </div>
            )}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className={labelClass}>{t.ptStrategyName}</label>
                <input className={inputClass} value={runName} onChange={(e) => setRunName(e.target.value)} placeholder={t.ptStrategyPlaceholder} />
              </div>
              <div>
                <label className={labelClass}>{t.ptMarket}</label>
                <select className={inputClass} value={market} onChange={(e) => setMarket(e.target.value)}>
                  {MARKET_OPTIONS.map((o) => (<option key={o.value} value={o.value}>{t[o.labelKey as keyof typeof t]}</option>))}
                </select>
              </div>
              <div className="col-span-2">
                <label className={labelClass}>{t.ptCodes}</label>
                <StockInput value={deployCodes} onChange={setDeployCodes} placeholder={t.ptCodesPlaceholder} multi />
              </div>
              <div>
                <label className={labelClass}>{t.ptInterval}</label>
                <select className={inputClass} value={interval} onChange={(e) => setInterval(e.target.value)}>
                  {INTERVAL_OPTIONS.map((o) => (<option key={o.value} value={o.value}>{t[o.labelKey as keyof typeof t]}</option>))}
                </select>
              </div>
              <div>
                <label className={labelClass}>{t.ptInitialCapital}</label>
                <input type="number" className={`${inputClass} font-mono`} value={initialCapital} onChange={(e) => setInitialCapital(parseInt(e.target.value) || 100000)} />
              </div>
            </div>
            <div>
              <label className={labelClass}>{t.ptRiskConfig}</label>
              <RiskConfigForm config={riskConfig} onChange={setRiskConfig} />
            </div>
            <label className="flex items-center gap-2 text-xs cursor-pointer">
              <input type="checkbox" checked={autoStart} onChange={(e) => setAutoStart(e.target.checked)} className="rounded" />
              {t.ptAutoStart}
            </label>
            <div className="flex gap-2 justify-end">
              <button className="px-4 py-1.5 border rounded-md text-sm" onClick={() => setShowDeploy(false)}>{t.ptCancel}</button>
              <button className="px-4 py-1.5 bg-green-600 text-white rounded-md text-sm hover:bg-green-700 disabled:opacity-50" onClick={handleDeploy} disabled={creating}>
                {creating ? <Loader2 className="h-3.5 w-3.5 animate-spin inline mr-1" /> : null}{t.ptDeploy}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Main 3-column layout */}
      <div className="flex-1 flex gap-2 overflow-hidden min-h-0">
        {/* Left: Strategy Library + Run List */}
        <div className="w-72 shrink-0 border rounded-lg bg-card flex flex-col min-h-0">
          <div className="flex border-b">
            <button className={`flex-1 py-2 text-xs font-medium flex items-center justify-center gap-1 ${leftTab === "library" ? "border-b-2 border-primary text-primary" : "text-muted-foreground"}`} onClick={() => setLeftTab("library")}>
              <Library className="h-3.5 w-3.5" />{t.strategyLibrary}
            </button>
            <button className={`flex-1 py-2 text-xs font-medium flex items-center justify-center gap-1 ${leftTab === "runs" ? "border-b-2 border-primary text-primary" : "text-muted-foreground"}`} onClick={() => setLeftTab("runs")}>
              <List className="h-3.5 w-3.5" />{t.runList}
            </button>
          </div>
          <div className="flex-1 overflow-auto p-2">
            {leftTab === "library" ? (
              <div className="space-y-3">
                <div className="flex gap-1">
                  {([
                    ["strategy-lab", t.fromStrategyLab],
                    ["chat", t.fromChat],
                  ] as const).map(([key, label]) => (
                    <button key={key} className={`flex-1 py-1 text-xs rounded-md ${librarySource === key ? "bg-primary/10 text-primary font-medium" : "text-muted-foreground hover:bg-muted"}`} onClick={() => setLibrarySource(key)}>
                      {label}
                    </button>
                  ))}
                </div>
                {strategiesLoading ? (
                  <div className="text-center text-muted-foreground py-8 text-xs"><Loader2 className="h-4 w-4 animate-spin mx-auto mb-1" />{t.ptLoading}</div>
                ) : strategies.length === 0 ? (
                  <div className="text-center text-muted-foreground py-8 text-xs">{t.ptNoRuns}</div>
                ) : (
                  strategies.map((s) => {
                    const isSelected = selectedStrategy?.id === s.id;
                    return (
                      <div
                        key={s.id}
                        className={`text-left p-2 rounded-md text-xs border transition-colors ${isSelected ? "border-primary bg-primary/10 ring-1 ring-primary/30" : "border-border hover:bg-muted/50"}`}
                      >
                        <button
                          className="w-full text-left"
                          onClick={() => loadStrategyCode(s)}
                        >
                          <div className="flex items-center gap-1.5">
                            {isSelected && <Check className="h-3 w-3 text-primary shrink-0" />}
                            <span className="font-medium truncate">{s.name}</span>
                          </div>
                          <div className="text-muted-foreground text-[10px] font-mono mt-0.5">{s.id.slice(0, 12)}</div>
                        </button>
                        <button
                          className="mt-1.5 w-full flex items-center justify-center gap-1 py-1 text-[10px] rounded bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
                          onClick={(e) => { e.stopPropagation(); handleQuickDeploy(s); }}
                        >
                          <Rocket className="h-3 w-3" />{t.ptQuickDeploy}
                        </button>
                      </div>
                    );
                  })
                )}
              </div>
            ) : (
              <div className="space-y-2">
                {runStore.runsLoading ? (
                  <div className="text-center text-muted-foreground py-8 text-xs">{t.ptLoading}</div>
                ) : runStore.runs.length === 0 ? (
                  <div className="text-center text-muted-foreground py-8 text-xs">{t.ptNoRuns}<br /><span className="text-[10px]">{t.ptNoRunsHint}</span></div>
                ) : (
                  runStore.runs.map((run) => (
                    <PaperTradingCard
                      key={run.id}
                      run={run}
                      isActive={runStore.activeRunId === run.id}
                      onSelect={handleSelectRun}
                      onStart={async (id) => { try { await runStore.startRun(id); } catch (e) { toast.error(e instanceof Error ? e.message : String(e)); } }}
                      onStop={(id) => runStore.stopRun(id)}
                      onPause={(id) => runStore.pauseRun(id)}
                      onResume={(id) => runStore.resumeRun(id)}
                      onDelete={(id) => runStore.deleteRun(id)}
                      onClone={handleClone}
                    />
                  ))
                )}
              </div>
            )}
          </div>
        </div>

        {/* Middle: Code Editor */}
        <div className="flex-1 flex flex-col min-w-0 min-w-[320px] border rounded-lg bg-card">
          <div className="px-3 py-1.5 border-b text-xs font-medium text-muted-foreground shrink-0">{t.ptStrategyCodeLabel}</div>
          <div className="flex-1 min-h-0">
            <CodeEditor value={code} onChange={setCode} filename="strategy.py" mode="strategy" />
          </div>
        </div>

        {/* Right: K-line chart + status */}
        <div className="flex-1 flex flex-col min-w-0 min-w-[380px] border rounded-lg bg-card overflow-auto">
          {!selectedRun ? (
            <div className="flex flex-col h-full p-3 space-y-3">
              <div className="text-xs font-medium text-muted-foreground">{t.ptKlinePreview}</div>
              <div className="flex gap-2 items-end flex-wrap">
                <div className="flex-1 min-w-[100px]">
                  <label className="text-[10px] text-muted-foreground">{t.ptSymbolCode}</label>
                  <StockInput
                    value={previewSymbol}
                    onChange={(v) => { setPreviewSymbol(v); if (v) handlePreviewFetch(v); }}
                    placeholder="600519.SH"
                  />
                </div>
                <button className="px-3 py-1.5 text-xs rounded-md bg-primary text-primary-foreground hover:opacity-90" onClick={() => handlePreviewFetch(previewSymbol || "600519.SH")}>
                  {chartLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : t.ptLoad}
                </button>
                <button className="px-3 py-1.5 text-xs rounded-md border hover:bg-muted" onClick={async () => {
                  try {
                    setChartLoading(true);
                    await runQuickBacktest(code, previewSymbol);
                  } catch (e) { setChartError(String(e)); }
                  finally { setChartLoading(false); }
                }}>{t.ptQuickBacktest}</button>
              </div>
              {btMetrics && Object.keys(btMetrics).length > 0 && (
                <div className="flex flex-wrap gap-x-3 gap-y-1 text-[10px] shrink-0">
                  {btMetrics.total_return != null && <span>{t.ptReturnShort} <span className={`font-mono font-medium ${btMetrics.total_return >= 0 ? "text-up" : "text-down"}`}>{(btMetrics.total_return * 100).toFixed(2)}%</span></span>}
                  {btMetrics.annual_return != null && <span>{t.ptAnnualLabel} <span className="font-mono font-medium">{(btMetrics.annual_return * 100).toFixed(2)}%</span></span>}
                  {btMetrics.sharpe != null && <span>{t.ptSharpeLabel} <span className="font-mono font-medium">{btMetrics.sharpe.toFixed(2)}</span></span>}
                  {btMetrics.max_drawdown != null && <span>{t.ptDrawdownLabel} <span className="font-mono font-medium text-down">{(btMetrics.max_drawdown * 100).toFixed(2)}%</span></span>}
                  {btMetrics.win_rate != null && <span>{t.ptWinRateLabel} <span className="font-mono font-medium">{(btMetrics.win_rate * 100).toFixed(2)}%</span></span>}
                  {btMetrics.trade_count != null && <span>{t.ptTradeCountLabel} <span className="font-mono font-medium">{btMetrics.trade_count}</span></span>}
                </div>
              )}
              {priceData.length > 0 ? (
                <div className="relative">
                  {chartLoading && (
                    <div className="absolute top-1 right-2 z-10 flex items-center gap-1 text-[10px] text-muted-foreground bg-card/80 px-1.5 py-0.5 rounded">
                      <Loader2 className="h-3 w-3 animate-spin" />{t.ptUpdating}
                    </div>
                  )}
                  <CandlestickChart data={priceData} markers={btTradeMarkers} height={320} />
                </div>
              ) : chartLoading ? (
                <div className="flex items-center justify-center flex-1 text-xs text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin mr-1" />Loading...</div>
              ) : (
                <div className="flex flex-col items-center justify-center flex-1 text-sm text-muted-foreground gap-2">
                  <TrendingUp className="h-8 w-8 opacity-30" />
                  <span>输入{t.ptSymbolCode}后点击「加载」查看 K 线</span>
                </div>
              )}
              {chartError && <div className="text-xs text-danger">{chartError}</div>}
            </div>
          ) : (
            <div className="space-y-2 p-3">
              {/* Run info bar + stats */}
              <div className="flex items-center justify-between shrink-0">
                <div>
                  <h2 className="text-sm font-bold">{selectedRun.run_name}</h2>
                  <p className="text-[10px] text-muted-foreground">
                    {selectedRun.market} &middot; {sseConnected ? t.ptSseConnected : liveStore.sseStatus === "reconnecting" ? t.ptReconnecting.replace("{n}", String(liveStore.reconnectCount)).replace("{s}", String(Math.ceil(liveStore.reconnectDelayMs / 1000))) : selectedRun.status}
                    {runStore.activeRunDetail?.data_source && <> &middot; {runStore.activeRunDetail.data_source}</>}
                  </p>
                </div>
                <button className="px-2 py-1 text-[10px] rounded border hover:bg-muted" onClick={() => {
                  if (selectedRun?.id) liveStore.fetchBars(selectedRun.id);
                }}>{t.ptRefreshKline}</button>
              </div>

              {/* Return stats cards */}
              <div className="grid grid-cols-4 gap-1.5 shrink-0">
                {(() => {
                  const eq = liveStore.equity;
                  const dailyReturn = eq.length >= 2 ? ((eq[eq.length - 1].equity - eq[eq.length - 2].equity) / eq[eq.length - 2].equity * 100) : null;
                  let maxDD = 0, peak = eq.length > 0 ? eq[0].equity : 0;
                  for (const p of eq) { if (p.equity > peak) peak = p.equity; const dd = (peak - p.equity) / peak * 100; if (dd > maxDD) maxDD = dd; }
                  const days = eq.length >= 2 ? (new Date(eq[eq.length - 1].point_time).getTime() - new Date(eq[0].point_time).getTime()) / 86400000 || 1 : 0;
                  const annReturn = days > 0 ? (Math.pow(1 + selectedRun.total_return_pct / 100, 365 / days) - 1) * 100 : null;
                  const items: [string, number | null, (v: number) => string][] = [
                    [t.ptDailyReturn, dailyReturn, (v) => `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`],
                    [t.ptCumulativeReturn, selectedRun.total_return_pct, (v) => `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`],
                    [t.ptAnnualReturn, annReturn, (v) => `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`],
                    [t.ptMaxDrawdown, maxDD, (v) => `${v.toFixed(2)}%`],
                  ];
                  return items.map(([label, value, fmt]) => value != null ? (
                    <div key={label} className="rounded-md bg-muted/30 p-2 text-center">
                      <div className="text-[10px] text-muted-foreground">{label}</div>
                      <div className={`text-xs font-mono font-bold ${value > 0 ? "text-up" : value < 0 ? "text-down" : ""}`}>{fmt(value)}</div>
                    </div>
                  ) : null);
                })()}
              </div>

              {/* K-line chart with trade markers — live from paper-trading engine */}
              <div className="min-h-[320px] shrink-0">
                {runChartData.length > 0 ? (
                  <CandlestickChart data={runChartData} markers={liveStore.tradeMarkers} height={320} />
                ) : runStore.detailLoading ? (
                  <div className="flex items-center justify-center h-36 text-xs text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin mr-1" />Loading...</div>
                ) : (
                  <div className="flex items-center justify-center h-36 text-xs text-muted-foreground">{t.ptNoKline}</div>
                )}
              </div>

              {/* Equity chart */}
              <div className="min-h-[200px] shrink-0">
                <EquityChart data={liveStore.equity} minHeight={180} />
              </div>

              {/* Tabs: positions / trades / log / stats / risk */}
              <div className="flex gap-1 border-b pb-1 overflow-x-auto">
                {(["positions", "trades", "log", "stats", "risk"] as const).map((val) => (
                  <button key={val} className={`px-2 py-1 text-[10px] whitespace-nowrap border-b-2 transition-colors ${detailTab === val ? "border-blue-500 text-blue-600 font-medium" : "border-transparent text-muted-foreground hover:text-foreground"}`} onClick={() => setDetailTab(val)}>
                    {{ positions: t.ptPositions, trades: t.ptTrades, log: t.ptTabLog, stats: t.ptTabStats, risk: t.ptRiskConfig }[val]}
                  </button>
                ))}
              </div>
              {detailTab === "positions" && <PositionTable positions={runStore.activeRunDetail?.positions || liveStore.positions || []} />}
              {detailTab === "trades" && <TradeHistoryTable trades={liveStore.recentTrades.length > 0 ? liveStore.recentTrades : (runStore.activeRunDetail?.recent_trades || [])} />}
              {detailTab === "log" && (
                <div className="space-y-1 max-h-48 overflow-auto text-[10px]">
                  {liveStore.signalLog.length === 0 && liveStore.recentTrades.length === 0 && <div className="text-muted-foreground text-center py-4">{t.ptNoLog}</div>}
                  {liveStore.signalLog.slice(-20).reverse().map((s, i) => (
                    <div key={i} className="flex gap-2 py-0.5 border-b border-border/30">
                      <span className="text-muted-foreground font-mono w-16 shrink-0">{s.timestamp?.slice(0, 16) || ""}</span>
                      <span className="font-mono">{s.symbol}</span>
                      <span className={s.direction > 0 ? "text-up" : "text-down"}>{s.direction > 0 ? t.ptLong : t.ptShort}</span>
                      <span className="text-muted-foreground">{s.reason}</span>
                    </div>
                  ))}
                  {liveStore.recentTrades.slice(-10).reverse().map((tr, i) => (
                    <div key={`t${i}`} className="flex gap-2 py-0.5 border-b border-border/30 bg-muted/20">
                      <span className="text-muted-foreground font-mono w-16 shrink-0">{tr.exit_time?.slice(0, 16) || ""}</span>
                      <span className="font-mono">{tr.symbol}</span>
                      <span className={tr.direction > 0 ? "text-up" : "text-down"}>{tr.direction > 0 ? t.ptLong : t.ptShort}</span>
                      <span className="font-mono font-medium">{tr.pnl >= 0 ? "+" : ""}{tr.pnl.toFixed(2)}</span>
                      <span className="text-muted-foreground">{tr.exit_reason}</span>
                    </div>
                  ))}
                </div>
              )}
              {detailTab === "stats" && (
                <div className="space-y-3 text-[11px]">
                  <MonthlyReturnHeatmap equity={liveStore.equity} />
                  {(() => {
                    const signals = liveStore.signalLog;
                    const trades = liveStore.recentTrades;
                    const longSig = signals.filter(s => s.direction > 0).length;
                    const shortSig = signals.filter(s => s.direction < 0).length;
                    const winTrades = trades.filter(t => t.pnl > 0).length;
                    const totalTrades = trades.length || 1;
                    return (
                      <div className="grid grid-cols-2 gap-2">
                        {[[t.ptLongSignal, longSig], [t.ptShortSignal, shortSig], [t.ptWinRate, `${(winTrades / totalTrades * 100).toFixed(1)}%`], [t.ptTotalTrades, trades.length], [t.ptOpenPositions, (selectedRun?.open_positions || 0)], [t.ptCurrentEquity, selectedRun?.current_equity.toFixed(0) || "0"]].map(([l, v]) => (
                          <div key={l as string} className="rounded bg-muted/20 p-2"><div className="text-muted-foreground text-[10px]">{l as string}</div><div className="font-mono font-medium">{String(v)}</div></div>
                        ))}
                      </div>
                    );
                  })()}
                </div>
              )}
              {detailTab === "risk" && (
                <div className="space-y-2">
                  <RiskConfigForm config={riskConfig} onChange={setRiskConfig} disabled={selectedRun.status === "running"} />
                  <button
                    className="flex items-center gap-1 px-3 py-1.5 text-xs bg-primary text-primary-foreground rounded-md hover:opacity-90 disabled:opacity-50"
                    onClick={handleSaveRisk}
                    disabled={riskSaving || selectedRun.status === "running"}
                  >
                    {riskSaving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Save className="h-3 w-3" />}
                    {t.ptSaveRiskConfig}
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
