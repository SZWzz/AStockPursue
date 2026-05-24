import { useEffect, useState } from "react";
import { usePaperTradingStore } from "@/stores/paperTradingStore";
import { useI18n } from "@/lib/i18n";
import PaperTradingCard from "@/components/paper-trading/PaperTradingCard";
import EquityChart from "@/components/paper-trading/EquityChart";
import PositionTable from "@/components/paper-trading/PositionTable";
import TradeHistoryTable from "@/components/paper-trading/TradeHistoryTable";
import RiskConfigForm, { defaultConfig } from "@/components/paper-trading/RiskConfigForm";
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

export default function PaperTrading() {
  const { t } = useI18n();
  const fetchRuns = usePaperTradingStore((s) => s.fetchRuns);
  const disconnectSSE = usePaperTradingStore((s) => s.disconnectSSE);
  const store = usePaperTradingStore();
  const [showCreate, setShowCreate] = useState(false);
  const [tab, setTab] = useState<"positions" | "trades" | "risk">("positions");

  const [form, setForm] = useState({
    run_name: "",
    market: "a_share",
    codes: "",
    interval: "1D",
    initial_capital: 100000,
    strategy_code: `# Write your SignalEngine class here
import pandas as pd

class SignalEngine:
    def generate(self, data_map: dict[str, pd.DataFrame]) -> dict[str, pd.Series]:
        """Return target weights in [-1, 1] for each code."""
        result = {}
        for code, df in data_map.items():
            weights = pd.Series(0.0, index=df.index)
            # Your strategy logic here
            result[code] = weights
        return result
`,
  });
  const [riskConfig, setRiskConfig] = useState<RiskConfig>({ ...defaultConfig });
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    fetchRuns();
    return () => {
      disconnectSSE();
    };
  }, [fetchRuns, disconnectSSE]);

  const handleCreate = async () => {
    if (!form.run_name.trim()) return;
    if (!form.codes.trim()) return;
    setCreating(true);
    try {
      const req: CreateRunRequest = {
        run_name: form.run_name.trim(),
        market: form.market,
        codes: form.codes.split(",").map((s) => s.trim()).filter(Boolean),
        interval: form.interval,
        initial_capital: form.initial_capital,
        strategy_code: form.strategy_code,
        risk_config: riskConfig,
      };
      await store.createRun(req);
      setShowCreate(false);
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : t.ptCreateFailed);
    } finally {
      setCreating(false);
    }
  };

  const selectedRun = store.activeRunDetail?.run;
  const sseConnected = store.sseStatus === "connected";

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-bold">{t.ptTitle}</h1>
        <button
          className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700"
          onClick={() => setShowCreate(!showCreate)}
        >
          {showCreate ? t.ptCancel : t.ptNewStrategy}
        </button>
      </div>

      {/* Create Form */}
      {showCreate && (
        <div className="bg-white border rounded-lg p-4 mb-4 space-y-3">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">{t.ptStrategyName}</label>
              <input
                className="w-full border rounded px-2 py-1 text-sm"
                value={form.run_name}
                onChange={(e) => setForm({ ...form, run_name: e.target.value })}
                placeholder="My Strategy"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">{t.ptMarket}</label>
              <select
                className="w-full border rounded px-2 py-1 text-sm"
                value={form.market}
                onChange={(e) => setForm({ ...form, market: e.target.value })}
              >
                {MARKET_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>{t[o.labelKey as keyof typeof t]}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">{t.ptCodes}</label>
              <input
                className="w-full border rounded px-2 py-1 text-sm font-mono"
                value={form.codes}
                onChange={(e) => setForm({ ...form, codes: e.target.value })}
                placeholder={t.ptCodesPlaceholder}
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">{t.ptInterval}</label>
              <select
                className="w-full border rounded px-2 py-1 text-sm"
                value={form.interval}
                onChange={(e) => setForm({ ...form, interval: e.target.value })}
              >
                {INTERVAL_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>{t[o.labelKey as keyof typeof t]}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">{t.ptInitialCapital}</label>
              <input
                type="number"
                className="w-full border rounded px-2 py-1 text-sm font-mono"
                value={form.initial_capital}
                onChange={(e) => setForm({ ...form, initial_capital: parseInt(e.target.value) || 100000 })}
              />
            </div>
          </div>

          <div>
            <label className="block text-xs text-gray-500 mb-1">{t.ptStrategyCodeLabel}</label>
            <textarea
              className="w-full border rounded px-2 py-1 text-sm font-mono h-32"
              value={form.strategy_code}
              onChange={(e) => setForm({ ...form, strategy_code: e.target.value })}
            />
          </div>

          <div>
            <label className="block text-xs text-gray-500 mb-1">{t.ptRiskConfig}</label>
            <RiskConfigForm config={riskConfig} onChange={setRiskConfig} />
          </div>

          <button
            className="px-6 py-2 bg-green-600 text-white rounded-lg text-sm hover:bg-green-700 disabled:opacity-50"
            onClick={handleCreate}
            disabled={creating}
          >
            {creating ? t.ptCreating : t.ptCreateSave}
          </button>
        </div>
      )}

      <div className="flex-1 flex gap-4 overflow-hidden">
        {/* Left: Run list */}
        <div className="w-80 shrink-0 overflow-y-auto space-y-3 pr-2">
          {store.runsLoading ? (
            <div className="text-center text-gray-400 py-8">{t.ptLoading}</div>
          ) : store.runs.length === 0 ? (
            <div className="text-center text-gray-400 py-8">
              {t.ptNoRuns}
              <br />
              <span className="text-sm">{t.ptNoRunsHint}</span>
            </div>
          ) : (
            store.runs.map((run) => (
              <PaperTradingCard
                key={run.id}
                run={run}
                isActive={store.activeRunId === run.id}
                onSelect={(id) => {
                  store.selectRun(id);
                  store.fetchEquity(id);
                  store.fetchTrades(id);
                  if (run.status === "running") {
                    store.connectSSE(id);
                  }
                }}
                onStart={(id) => store.startRun(id)}
                onStop={(id) => store.stopRun(id)}
                onPause={(id) => store.pauseRun(id)}
                onResume={(id) => store.resumeRun(id)}
                onDelete={(id) => store.deleteRun(id)}
              />
            ))
          )}
        </div>

        {/* Right: Detail */}
        <div className="flex-1 overflow-y-auto border rounded-lg bg-white p-4">
          {!selectedRun ? (
            <div className="text-center text-gray-400 py-16">
              {t.ptSelectRunHint}
            </div>
          ) : (
            <div className="space-y-4">
              {/* Run info bar */}
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-bold">{selectedRun.run_name}</h2>
                  <p className="text-xs text-gray-500">
                    {selectedRun.market} &middot; {sseConnected ? t.ptSseConnected : selectedRun.status}
                    {selectedRun.tick_mode && <span className="ml-2 text-blue-500">TickHandler</span>}
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-sm text-gray-500">
                    {t.ptEquityLabel} <span className="font-mono font-bold text-base">{selectedRun.current_equity.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
                  </p>
                  <p className={`text-sm font-mono ${selectedRun.total_return_pct >= 0 ? "text-green-600" : "text-red-600"}`}>
                    {selectedRun.total_return_pct >= 0 ? "+" : ""}{selectedRun.total_return_pct.toFixed(2)}%
                  </p>
                </div>
              </div>

              {/* Equity chart */}
              <EquityChart data={store.equity} />

              {/* Tabs */}
              <div className="flex gap-2 border-b">
                {TAB_VALUES.map((val, i) => (
                  <button
                    key={val}
                    className={`px-3 py-1.5 text-sm border-b-2 transition-colors ${
                      tab === val
                        ? "border-blue-500 text-blue-600 font-medium"
                        : "border-transparent text-gray-500 hover:text-gray-700"
                    }`}
                    onClick={() => setTab(val)}
                  >
                    {t[TAB_KEYS[i] as keyof typeof t]}
                  </button>
                ))}
              </div>

              {/* Tab content */}
              {tab === "positions" && (
                <PositionTable
                  positions={store.activeRunDetail?.positions || []}
                />
              )}
              {tab === "trades" && (
                <TradeHistoryTable
                  trades={store.recentTrades.length > 0 ? store.recentTrades : (store.activeRunDetail?.recent_trades || [])}
                />
              )}
              {tab === "risk" && (
                <RiskConfigForm
                  config={riskConfig}
                  onChange={setRiskConfig}
                  disabled={selectedRun.status === "running"}
                />
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
