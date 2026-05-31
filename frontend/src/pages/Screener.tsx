import { useEffect, useState } from "react";
import { useI18n } from "@/lib/i18n";
import { useScreenerStore } from "@/stores/screenerStore";
import { Search, Plus, Trash2, Save, Sparkles, Download, Star, BarChart3 } from "lucide-react";

const FIELDS = [
  { name: "close", label: "Close Price", cat: "technical" },
  { name: "volume", label: "Volume", cat: "technical" },
  { name: "returns_1d", label: "1-Day Return", cat: "momentum" },
  { name: "returns_5d", label: "5-Day Return", cat: "momentum" },
  { name: "returns_20d", label: "20-Day Return", cat: "momentum" },
  { name: "volume_ratio", label: "Volume Ratio", cat: "technical" },
  { name: "high_low_ratio", label: "High/Low Ratio", cat: "volatility" },
  { name: "sma_20", label: "SMA(20)", cat: "technical" },
  { name: "sma_60", label: "SMA(60)", cat: "technical" },
  { name: "volatility_20d", label: "20-Day Vol", cat: "volatility" },
  { name: "rsi_14", label: "RSI(14)", cat: "momentum" },
];
const OPERATORS = [
  { value: ">", label: ">" },
  { value: "<", label: "<" },
  { value: ">=", label: ">=" },
  { value: "<=", label: "<=" },
  { value: "==", label: "=" },
  { value: "between", label: "Between" },
  { value: "rank_top", label: "Rank Top %" },
  { value: "rank_bottom", label: "Rank Bottom %" },
];

export function Screener() {
  const { t } = useI18n();
  const store = useScreenerStore();
  const [presetName, setPresetName] = useState("");
  const [showSave, setShowSave] = useState(false);
  const [selectedSymbols, setSelectedSymbols] = useState<Set<string>>(new Set());

  useEffect(() => { store.loadPresets(); }, []);

  const toggleSymbol = (s: string) => {
    setSelectedSymbols((prev) => {
      const next = new Set(prev);
      if (next.has(s)) next.delete(s); else next.add(s);
      return next;
    });
  };

  return (
    <div className="flex flex-col h-full p-4 gap-3">
      <h1 className="text-lg font-bold flex items-center gap-2"><Search className="h-5 w-5" />{t.screener || "Stock Screener"}</h1>

      <div className="flex gap-3 flex-1 min-h-0">
        {/* Left: conditions builder */}
        <div className="w-80 shrink-0 border rounded-xl p-3 flex flex-col gap-2 overflow-y-auto">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold">{t.screenerConditions || "Conditions"}</h3>
            <button onClick={store.addCondition} className="p-1 rounded hover:bg-muted"><Plus className="h-4 w-4" /></button>
          </div>
          {store.conditions.map((c, i) => (
            <div key={i} className="flex items-center gap-1 text-xs bg-muted/30 rounded-lg p-2">
              <select value={c.field} onChange={(e) => store.updateCondition(i, { ...c, field: e.target.value })}
                className="flex-1 border rounded px-1 py-0.5 bg-background min-w-0">
                {FIELDS.map((f) => <option key={f.name} value={f.name}>{f.label}</option>)}
              </select>
              <select value={c.operator} onChange={(e) => store.updateCondition(i, { ...c, operator: e.target.value })}
                className="w-16 border rounded px-1 py-0.5 bg-background">
                {OPERATORS.map((op) => <option key={op.value} value={op.value}>{op.label}</option>)}
              </select>
              <input
                type="number"
                value={typeof c.value === "number" ? c.value : ""}
                onChange={(e) => store.updateCondition(i, { ...c, field: c.field, operator: c.operator, value: +e.target.value })}
                className="w-16 border rounded px-1 py-0.5 bg-background"
              />
              <button onClick={() => store.removeCondition(i)} className="p-0.5 text-destructive hover:bg-destructive/10 rounded"><Trash2 className="h-3 w-3" /></button>
            </div>
          ))}

          <div className="flex gap-2 mt-2">
            <button onClick={store.runScreen} disabled={store.loading}
              className="flex-1 px-3 py-1.5 bg-primary text-primary-foreground rounded text-sm font-medium disabled:opacity-50">
              {store.loading ? "Running..." : (t.screenerRun || "Run Screen")}
            </button>
            <button onClick={() => setShowSave(true)} className="px-3 py-1.5 border rounded text-sm hover:bg-muted"><Save className="h-4 w-4" /></button>
          </div>
          {showSave && (
            <div className="flex gap-1 text-xs">
              <input value={presetName} onChange={(e) => setPresetName(e.target.value)} placeholder="Preset name..." className="flex-1 border rounded px-2 py-1 bg-background" />
              <button onClick={() => { store.savePreset(presetName); setShowSave(false); setPresetName(""); }}
                className="px-2 py-1 bg-primary text-primary-foreground rounded">Save</button>
            </div>
          )}

          {/* AI Recommend */}
          <button onClick={async () => { const r = await store.aiRecommend(); if (Array.isArray(r)) {/* load into UI */} }}
            className="flex items-center justify-center gap-1 px-3 py-1.5 rounded text-xs border border-dashed hover:bg-muted/50 transition">
            <Sparkles className="h-3 w-3" />{t.screenerAiRec || "AI Recommend"}
          </button>

          {/* Presets */}
          {store.presets.length > 0 && <h4 className="text-xs font-semibold mt-2">{t.screenerPresets || "Presets"}</h4>}
          {store.presets.map((p) => (
            <div key={p.id} className="flex items-center justify-between text-xs py-1 px-2 rounded hover:bg-muted/50 cursor-pointer">
              <span>{p.name} {p.is_system && <Star className="h-2.5 w-2.5 inline text-amber-500" />}</span>
              {!p.is_system && <button onClick={() => store.deletePreset(p.id)} className="text-destructive"><Trash2 className="h-3 w-3" /></button>}
            </div>
          ))}
        </div>

        {/* Right: results table */}
        <div className="flex-1 border rounded-xl overflow-auto">
          {store.results.length === 0 ? (
            <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
              {t.screenerNoResults || "Run a screen to see results"}
            </div>
          ) : (
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-card border-b">
                <tr>
                  <th className="text-left py-2 px-3 w-8"></th>
                  <th className="text-left py-2 px-3">Symbol</th>
                  <th className="text-left py-2 px-3">Name</th>
                  {Object.keys(store.results[0] || {}).filter((k) => k !== "symbol" && k !== "name").slice(0, 8).map((k) => (
                    <th key={k} className="text-right py-2 px-3">{k}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {store.results.map((r, i) => (
                  <tr key={i} className="border-b hover:bg-muted/30">
                    <td className="py-1 px-3">
                      <input type="checkbox" checked={selectedSymbols.has(r.symbol)} onChange={() => toggleSymbol(r.symbol)} />
                    </td>
                    <td className="py-1 px-3 font-mono font-medium">{r.symbol}</td>
                    <td className="py-1 px-3">{r.name}</td>
                    {Object.keys(r).filter((k) => k !== "symbol" && k !== "name").slice(0, 8).map((k) => (
                      <td key={k} className="py-1 px-3 text-right font-mono">{(r[k] as number)?.toFixed?.(4) ?? String(r[k])}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Batch actions */}
      {selectedSymbols.size > 0 && (
        <div className="flex items-center gap-2 p-2 border rounded-lg bg-muted/20 text-xs">
          <span>{selectedSymbols.size} selected</span>
          <button onClick={() => store.batchAddWatchlist([...selectedSymbols])} className="px-2 py-1 bg-primary/10 text-primary rounded hover:bg-primary/20">
            <Star className="h-3 w-3 inline mr-1" />Add Watchlist
          </button>
          <button onClick={() => store.batchBacktest([...selectedSymbols])} className="px-2 py-1 bg-primary/10 text-primary rounded hover:bg-primary/20">
            <BarChart3 className="h-3 w-3 inline mr-1" />Backtest Basket
          </button>
          <button className="px-2 py-1 border rounded hover:bg-muted">
            <Download className="h-3 w-3 inline mr-1" />Export CSV
          </button>
        </div>
      )}
    </div>
  );
}
