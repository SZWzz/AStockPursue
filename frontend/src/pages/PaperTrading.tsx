import { useEffect, useState, useCallback } from "react";
import { Loader2, TrendingUp, Library, List, Plus } from "lucide-react";
import { usePaperTradingStore } from "@/stores/paperTradingStore";
import { useI18n } from "@/lib/i18n";
import { authHeaders } from "@/lib/apiAuth";
import { api, type PriceBar } from "@/lib/api";
import { CodeEditor } from "@/components/indicator-lab/CodeEditor";
import { CandlestickChart } from "@/components/charts/CandlestickChart";
import EquityChart from "@/components/paper-trading/EquityChart";
import PositionTable from "@/components/paper-trading/PositionTable";
import TradeHistoryTable from "@/components/paper-trading/TradeHistoryTable";
import RiskConfigForm, { defaultConfig } from "@/components/paper-trading/RiskConfigForm";
import PaperTradingCard from "@/components/paper-trading/PaperTradingCard";
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

const TAB_KEYS = ["ptTabPositions", "ptTabTrades", "ptTabRisk"] as const;
const TAB_VALUES = ["positions", "trades", "risk"] as const;

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
  const fetchRuns = usePaperTradingStore((s) => s.fetchRuns);
  const disconnectSSE = usePaperTradingStore((s) => s.disconnectSSE);
  const store = usePaperTradingStore();
  const [leftTab, setLeftTab] = useState<LeftTab>("library");
  const [librarySource, setLibrarySource] = useState<LibrarySource>("strategy-lab");
  const [strategies, setStrategies] = useState<StrategyItem[]>([]);
  const [strategiesLoading, setStrategiesLoading] = useState(false);
  const [detailTab, setDetailTab] = useState<"positions" | "trades" | "risk">("positions");
  const [showDeploy, setShowDeploy] = useState(false);

  // Strategy editor state
  const [code, setCode] = useState(DEFAULT_CODE);

  // Deploy form state
  const [runName, setRunName] = useState("");
  const [market, setMarket] = useState("a_share");
  const [codes, setCodes] = useState("");
  const [interval, setInterval] = useState("1D");
  const [initialCapital, setInitialCapital] = useState(100000);
  const [riskConfig, setRiskConfig] = useState<RiskConfig>({ ...defaultConfig });
  const [creating, setCreating] = useState(false);

  // Chart state
  const [priceData, setPriceData] = useState<PriceBar[]>([]);
  const [chartLoading, setChartLoading] = useState(false);
  const [chartError, setChartError] = useState<string | null>(null);

  const selectedRun = store.activeRunDetail?.run;
  const sseConnected = store.sseStatus === "connected";

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
        const res = await fetch("/strategy-lab/list", { headers: authHeaders() });
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
    if (item.code) { setCode(item.code); return; }
    try {
      const res = await fetch(`/strategy-lab/${item.id}`, { headers: authHeaders() });
      if (!res.ok) return;
      const json = await res.json();
      setCode(json.code || "");
    } catch {
      /* ignore */
    }
  };

  // ── OHLCV fetch for chart ───────────────────────────────────────────────

  const fetchChartData = useCallback(async (symbol: string) => {
    if (!symbol) return;
    setChartLoading(true);
    setChartError(null);
    try {
      const data = await api.getOHLCV({ symbol, start_date: "2026-01-01", end_date: "2026-05-24", source: "auto", interval: "1D" });
      setPriceData(data.bars || []);
    } catch (e) {
      setChartError(String(e));
    } finally {
      setChartLoading(false);
    }
  }, []);

  // Auto-fetch chart when run is selected
  useEffect(() => {
    const positions = store.activeRunDetail?.positions || [];
    if (positions.length > 0 && positions[0].symbol) {
      fetchChartData(positions[0].symbol);
    }
  }, [store.activeRunDetail?.positions, fetchChartData]);

  // ── Deploy ──────────────────────────────────────────────────────────────

  const handleDeploy = async () => {
    if (!runName.trim() || !codes.trim()) return;
    setCreating(true);
    try {
      const req: CreateRunRequest = {
        run_name: runName.trim(),
        market,
        codes: codes.split(",").map((s) => s.trim()).filter(Boolean),
        interval,
        initial_capital: initialCapital,
        strategy_code: code,
        risk_config: riskConfig,
      };
      await store.createRun(req);
      setShowDeploy(false);
      setLeftTab("runs");
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : t.ptCreateFailed);
    } finally {
      setCreating(false);
    }
  };

  const labelClass = "text-[11px] font-medium text-muted-foreground";
  const inputClass = "w-full text-xs rounded-md border border-border bg-background px-2 py-1.5 focus:outline-none focus:border-primary/50";

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-3 shrink-0">
        <h1 className="text-xl font-bold">{t.ptTitle}</h1>
        <div className="flex items-center gap-2">
          <button className="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700" onClick={() => { setRunName(""); setCodes(""); setShowDeploy(true); setLeftTab("library"); }}>
            <Plus className="h-3.5 w-3.5 inline mr-1" />{t.newStrategy}
          </button>
        </div>
      </div>

      {/* Deploy modal */}
      {showDeploy && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="bg-card border rounded-xl shadow-2xl w-[600px] max-h-[80vh] overflow-auto animate-scale-in p-5 space-y-4">
            <h2 className="text-lg font-bold">{t.deployToPaper}</h2>
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
              <div>
                <label className={labelClass}>{t.ptCodes}</label>
                <input className={`${inputClass} font-mono`} value={codes} onChange={(e) => setCodes(e.target.value)} placeholder={t.ptCodesPlaceholder} />
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
                  strategies.map((s) => (
                    <button key={s.id} className="w-full text-left p-2 rounded-md hover:bg-muted/50 text-xs border border-border" onClick={() => loadStrategyCode(s)}>
                      <div className="font-medium truncate">{s.name}</div>
                      <div className="text-muted-foreground text-[10px] font-mono">{s.id.slice(0, 12)}</div>
                    </button>
                  ))
                )}
              </div>
            ) : (
              <div className="space-y-2">
                {store.runsLoading ? (
                  <div className="text-center text-muted-foreground py-8 text-xs">{t.ptLoading}</div>
                ) : store.runs.length === 0 ? (
                  <div className="text-center text-muted-foreground py-8 text-xs">{t.ptNoRuns}<br /><span className="text-[10px]">{t.ptNoRunsHint}</span></div>
                ) : (
                  store.runs.map((run) => (
                    <PaperTradingCard
                      key={run.id}
                      run={run}
                      isActive={store.activeRunId === run.id}
                      onSelect={(id) => { store.selectRun(id); store.fetchEquity(id); store.fetchTrades(id); if (run.status === "running") store.connectSSE(id); }}
                      onStart={(id) => store.startRun(id)}
                      onStop={(id) => store.stopRun(id)}
                      onPause={(id) => store.pauseRun(id)}
                      onResume={(id) => store.resumeRun(id)}
                      onDelete={(id) => store.deleteRun(id)}
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
              {/* Chart preview when no run is active */}
              <div className="text-xs font-medium text-muted-foreground">K 线预览</div>
              <div className="flex gap-2 items-end">
                <div className="flex-1">
                  <label className="text-[10px] text-muted-foreground">标的代码</label>
                  <input
                    className="w-full text-xs rounded-md border border-border bg-background px-2 py-1.5 font-mono"
                    placeholder="600519.SH"
                    value={codes}
                    onChange={(e) => { setCodes(e.target.value); }}
                    onKeyDown={(e) => { if (e.key === "Enter") fetchChartData(codes || "600519.SH"); }}
                  />
                </div>
                <button
                  className="px-3 py-1.5 text-xs rounded-md bg-primary text-primary-foreground hover:opacity-90"
                  onClick={() => fetchChartData(codes || "600519.SH")}
                >
                  {chartLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : "加载"}
                </button>
              </div>
              {chartLoading ? (
                <div className="flex items-center justify-center flex-1 text-xs text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin mr-1" />Loading...</div>
              ) : priceData.length > 0 ? (
                <CandlestickChart data={priceData} height={320} />
              ) : (
                <div className="flex flex-col items-center justify-center flex-1 text-sm text-muted-foreground gap-2">
                  <TrendingUp className="h-8 w-8 opacity-30" />
                  <span>输入标的代码后点击「加载」查看 K 线</span>
                </div>
              )}
              {chartError && <div className="text-xs text-danger">{chartError}</div>}
            </div>
          ) : (
            <div className="space-y-3 p-3">
              {/* Run info bar */}
              <div className="flex items-center justify-between shrink-0">
                <div>
                  <h2 className="text-sm font-bold">{selectedRun.run_name}</h2>
                  <p className="text-[10px] text-muted-foreground">
                    {selectedRun.market} &middot; {sseConnected ? t.ptSseConnected : selectedRun.status}
                    {selectedRun.tick_mode && <span className="ml-2 text-blue-500">TickHandler</span>}
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-xs text-muted-foreground">
                    {t.ptEquity} <span className="font-mono font-bold text-sm">{selectedRun.current_equity.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
                  </p>
                  <p className={`text-xs font-mono ${selectedRun.total_return_pct >= 0 ? "text-up" : "text-down"}`}>
                    {selectedRun.total_return_pct >= 0 ? "+" : ""}{selectedRun.total_return_pct.toFixed(2)}%
                  </p>
                </div>
              </div>

              {/* K-line chart */}
              {chartLoading ? (
                <div className="flex items-center justify-center h-48 text-xs text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin mr-1" />Loading...</div>
              ) : priceData.length > 0 ? (
                <CandlestickChart data={priceData} height={280} />
              ) : chartError ? (
                <div className="text-xs text-danger">{chartError}</div>
              ) : null}

              {/* Equity chart */}
              <EquityChart data={store.equity} height={160} />

              {/* Tabs */}
              <div className="flex gap-2 border-b pb-1">
                {TAB_VALUES.map((val, i) => (
                  <button key={val} className={`px-2 py-1 text-[11px] border-b-2 transition-colors ${detailTab === val ? "border-blue-500 text-blue-600 font-medium" : "border-transparent text-muted-foreground hover:text-foreground"}`} onClick={() => setDetailTab(val)}>
                    {t[TAB_KEYS[i] as keyof typeof t]}
                  </button>
                ))}
              </div>

              {/* Tab content */}
              {detailTab === "positions" && <PositionTable positions={store.activeRunDetail?.positions || []} />}
              {detailTab === "trades" && <TradeHistoryTable trades={store.recentTrades.length > 0 ? store.recentTrades : (store.activeRunDetail?.recent_trades || [])} />}
              {detailTab === "risk" && <RiskConfigForm config={riskConfig} onChange={setRiskConfig} disabled={selectedRun.status === "running"} />}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
