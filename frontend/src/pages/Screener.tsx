import { useEffect, useState } from "react";
import { useI18n } from "@/lib/i18n";
import { useScreenerStore } from "@/stores/screenerStore";
import { Search, Plus, Trash2, Save, Sparkles, Download, Star, BarChart3, Filter, ListOrdered, Database, Globe } from "lucide-react";
import { cn } from "@/lib/utils";
import { ExportToWorkflowButton } from "@/components/shared/ExportToWorkflowButton";

const OPERATORS = [
  { value: ">", label: ">" },
  { value: "<", label: "<" },
  { value: ">=", label: ">=" },
  { value: "<=", label: "<=" },
  { value: "==", label: "=" },
  { value: "between", label: "区间" },
  { value: "rank_top", label: "排名前%" },
  { value: "rank_bottom", label: "排名后%" },
];

const MODES = [
  { key: "filter" as const, label: "筛选", icon: Filter, desc: "多条件交集过滤" },
  { key: "rank" as const, label: "排名", icon: ListOrdered, desc: "Z-score 综合排名" },
  { key: "score" as const, label: "评分", icon: BarChart3, desc: "加权多因子评分" },
];

const FIELD_DEFAULTS = [
  { name: "close", label: "收盘价", category: "technical" },
  { name: "volume", label: "成交量", category: "technical" },
  { name: "returns_1d", label: "1日收益", category: "momentum" },
  { name: "returns_5d", label: "5日收益", category: "momentum" },
  { name: "returns_20d", label: "20日收益", category: "momentum" },
  { name: "volume_ratio", label: "量比", category: "technical" },
  { name: "high_low_ratio", label: "高低比", category: "volatility" },
  { name: "sma_20", label: "SMA(20)", category: "technical" },
  { name: "sma_60", label: "SMA(60)", category: "technical" },
  { name: "volatility_20d", label: "20日波动", category: "volatility" },
  { name: "rsi_14", label: "RSI(14)", category: "momentum" },
];

const UNIVERSE_PRESETS = [
  { value: "csi300", label: "沪深300", codes: ["000001.SZ","000002.SZ","000063.SZ","000066.SZ","000069.SZ","000100.SZ","000157.SZ","000166.SZ","000301.SZ","000333.SZ","000338.SZ","000408.SZ","000425.SZ","000538.SZ","000568.SZ","000596.SZ","000617.SZ","000625.SZ","000630.SZ","000651.SZ","000661.SZ","000708.SZ","000725.SZ","000768.SZ","000776.SZ","000783.SZ","000786.SZ","000792.SZ","000800.SZ","000807.SZ","000858.SZ","000876.SZ","000895.SZ","000938.SZ","000963.SZ","000977.SZ","000983.SZ","001979.SZ","002001.SZ","002007.SZ","002027.SZ","002049.SZ","002050.SZ","002074.SZ","002129.SZ","002142.SZ","002179.SZ","002230.SZ","002236.SZ","002241.SZ","002252.SZ","002271.SZ","002304.SZ","002311.SZ","002352.SZ","002371.SZ","002410.SZ","002415.SZ","002459.SZ","002460.SZ","002466.SZ","002475.SZ","002493.SZ","002594.SZ","002601.SZ","002602.SZ","002648.SZ","002714.SZ","002736.SZ","002812.SZ","002916.SZ","002920.SZ","002938.SZ","300015.SZ","300033.SZ","300059.SZ","300122.SZ","300124.SZ","300142.SZ","300274.SZ","300285.SZ","300308.SZ","300316.SZ","300347.SZ","300408.SZ","300413.SZ","300433.SZ","300450.SZ","300498.SZ","300529.SZ","300628.SZ","300661.SZ","300750.SZ","300760.SZ","300782.SZ","600000.SH","600009.SH","600010.SH","600015.SH","600016.SH","600018.SH","600019.SH","600025.SH","600027.SH","600028.SH","600029.SH","600030.SH","600031.SH","600036.SH","600048.SH","600050.SH","600061.SH","600085.SH","600089.SH","600104.SH","600111.SH","600115.SH","600132.SH","600150.SH","600161.SH","600176.SH","600183.SH","600188.SH","600196.SH","600233.SH","600276.SH","600309.SH","600346.SH","600362.SH","600406.SH","600426.SH","600436.SH","600438.SH","600482.SH","600489.SH","600519.SH","600547.SH","600570.SH","600584.SH","600585.SH","600588.SH","600600.SH","600606.SH","600690.SH","600703.SH","600732.SH","600745.SH","600760.SH","600795.SH","600809.SH","600837.SH","600845.SH","600872.SH","600886.SH","600887.SH","600893.SH","600900.SH","600905.SH","600919.SH","600926.SH","600958.SH","600999.SH","601006.SH","601009.SH","601012.SH","601021.SH","601066.SH","601088.SH","601100.SH","601111.SH","601117.SH","601138.SH","601166.SH","601169.SH","601186.SH","601211.SH","601225.SH","601229.SH","601236.SH","601238.SH","601288.SH","601318.SH","601319.SH","601328.SH","601336.SH","601360.SH","601377.SH","601390.SH","601398.SH","601456.SH","601528.SH","601600.SH","601601.SH","601607.SH","601615.SH","601618.SH","601628.SH","601633.SH","601658.SH","601668.SH","601669.SH","601688.SH","601689.SH","601696.SH","601698.SH","601728.SH","601766.SH","601788.SH","601800.SH","601808.SH","601816.SH","601818.SH","601857.SH","601868.SH","601878.SH","601881.SH","601888.SH","601898.SH","601899.SH","601901.SH","601919.SH","601939.SH","601985.SH","601988.SH","601989.SH","601998.SH","603160.SH","603259.SH","603260.SH","603288.SH","603369.SH","603392.SH","603501.SH","603806.SH","603833.SH","603899.SH","603986.SH","603993.SH","688008.SH","688012.SH","688036.SH","688041.SH","688065.SH","688111.SH","688126.SH","688169.SH","688187.SH","688223.SH","688256.SH","688271.SH","688303.SH","688396.SH","688472.SH","688484.SH","688506.SH","688536.SH","688561.SH","688568.SH","688599.SH","688728.SH","688777.SH","688819.SH","688981.SH"] },
  { value: "active_a", label: "活跃A股(100只)", codes: ["000001.SZ","000002.SZ","000063.SZ","000333.SZ","000651.SZ","000725.SZ","000858.SZ","002049.SZ","002230.SZ","002415.SZ","002594.SZ","002714.SZ","300015.SZ","300059.SZ","300122.SZ","300274.SZ","300308.SZ","300316.SZ","300347.SZ","300408.SZ","300433.SZ","300450.SZ","300498.SZ","300529.SZ","300661.SZ","300750.SZ","300760.SZ","600000.SH","600009.SH","600015.SH","600016.SH","600028.SH","600030.SH","600031.SH","600036.SH","600050.SH","600085.SH","600104.SH","600111.SH","600196.SH","600276.SH","600309.SH","600406.SH","600436.SH","600438.SH","600519.SH","600570.SH","600585.SH","600588.SH","600690.SH","600795.SH","600809.SH","600837.SH","600886.SH","600887.SH","600900.SH","600919.SH","601012.SH","601066.SH","601088.SH","601111.SH","601138.SH","601166.SH","601211.SH","601238.SH","601288.SH","601318.SH","601328.SH","601377.SH","601390.SH","601398.SH","601456.SH","601600.SH","601628.SH","601633.SH","601668.SH","601669.SH","601688.SH","601728.SH","601766.SH","601800.SH","601808.SH","601818.SH","601857.SH","601878.SH","601881.SH","601888.SH","601898.SH","601899.SH","601919.SH","601939.SH","601985.SH","601988.SH","601998.SH","603259.SH","603288.SH","603501.SH","603806.SH","603899.SH","603986.SH","688008.SH","688012.SH","688036.SH","688111.SH","688187.SH","688256.SH","688396.SH","688561.SH","688981.SH"] },
  { value: "custom", label: "自定义输入", codes: [] },
] as const;

export function Screener() {
  const { t } = useI18n();
  const store = useScreenerStore();
  const [presetName, setPresetName] = useState("");
  const [showSave, setShowSave] = useState(false);
  const [selectedSymbols, setSelectedSymbols] = useState<Set<string>>(new Set());
  const [universePreset, setUniversePreset] = useState<string>("active_a");
  const [customUniverse, setCustomUniverse] = useState("");

  useEffect(() => {
    store.loadPresets();
    store.loadFields();
    // Default to 活跃A股 universe
    const activeCodes = UNIVERSE_PRESETS[1].codes as readonly string[];
    store.setUniverse([...activeCodes]);
  }, []);

  // Update universe when preset changes
  const handleUniverseChange = (val: string) => {
    setUniversePreset(val);
    if (val === "custom") {
      store.setUniverse([]);
    } else {
      const preset = UNIVERSE_PRESETS.find((p) => p.value === val);
      if (preset && preset.codes.length > 0) {
        store.setUniverse([...preset.codes]);
      }
    }
  };

  const applyCustomUniverse = () => {
    const codes = customUniverse.split(/[,\s]+/).filter(Boolean);
    store.setUniverse(codes);
  };

  const toggleSymbol = (s: string) => {
    setSelectedSymbols((prev) => {
      const next = new Set(prev);
      if (next.has(s)) next.delete(s); else next.add(s);
      return next;
    });
  };

  return (
    <div className="flex flex-col h-full p-4 gap-3">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold flex items-center gap-2"><Search className="h-5 w-5" />{t.screener || "选股器"}</h1>
        <div className="flex items-center gap-2">
          {/* Mode toggle */}
          <div className="flex items-center bg-muted rounded-lg p-0.5">
            {MODES.map((m) => (
              <button
                key={m.key}
                onClick={() => store.setMode(m.key)}
                className={cn(
                  "flex items-center gap-1 px-2.5 py-1 rounded text-xs transition",
                  store.mode === m.key ? "bg-background shadow-sm font-medium" : "text-muted-foreground hover:text-foreground"
                )}
                title={m.desc}
              >
                <m.icon className="h-3 w-3" />
                {m.label}
              </button>
            ))}
          </div>
          {/* Data source badge */}
          {store.dataSource && (
            <span className={cn(
              "text-[10px] px-2 py-0.5 rounded-full border",
              store.dataSource === "real" ? "bg-emerald-500/10 text-up border-emerald-500/20"
                : store.dataSource === "error" ? "bg-red-500/10 text-down border-red-500/20"
                : "bg-amber-500/10 text-amber-600 border-amber-500/20"
            )}>
              <Database className="h-2.5 w-2.5 inline mr-0.5" />
              {store.dataSource === "real" ? "真实数据"
                : store.dataSource === "error" ? "加载失败"
                : "模拟 ⚠"}
            </span>
          )}
        </div>
      </div>

      <div className="flex gap-3 flex-1 min-h-0">
        {/* Left: conditions builder */}
        <div className="w-80 shrink-0 border rounded-xl p-3 flex flex-col gap-2 overflow-y-auto">
          <h3 className="text-sm font-semibold">{t.screenerConditions || "筛选条件"}</h3>

          {/* ── Universe selector ── */}
          <div className="space-y-1">
            <label className="text-[10px] text-muted-foreground uppercase tracking-wider flex items-center gap-1"><Globe className="h-3 w-3" />股票池</label>
            <select value={universePreset} onChange={(e) => handleUniverseChange(e.target.value)}
              className="w-full text-xs border rounded px-2 py-1.5 bg-background">
              {UNIVERSE_PRESETS.map((p) => (
                <option key={p.value} value={p.value}>{p.label}</option>
              ))}
            </select>
            {universePreset === "custom" && (
              <div className="flex gap-1">
                <input
                  value={customUniverse}
                  onChange={(e) => setCustomUniverse(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") applyCustomUniverse(); }}
                  placeholder="000001.SZ, 600519.SH, ..."
                  className="flex-1 text-xs border rounded px-2 py-1 bg-background font-mono"
                />
                <button onClick={applyCustomUniverse} className="px-2 py-1 text-xs bg-primary text-primary-foreground rounded">应用</button>
              </div>
            )}
            <p className="text-[10px] text-muted-foreground">共 {store.universe.length} 只股票</p>
          </div>

          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-muted-foreground">条件</span>
            <button onClick={store.addCondition} className="p-1 rounded hover:bg-muted"><Plus className="h-4 w-4" /></button>
          </div>
          {store.conditions.map((c, i) => (
            <div key={i} className="flex items-center gap-1 text-xs bg-muted/30 rounded-lg p-2">
              <select value={c.field} onChange={(e) => store.updateCondition(i, { ...c, field: e.target.value })}
                className="flex-1 border rounded px-1 py-0.5 bg-background min-w-0">
                {(store.fields.length > 0 ? store.fields : FIELD_DEFAULTS).map((f) => (
                  <option key={f.name} value={f.name}>{f.label}</option>
                ))}
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
            <button onClick={store.runScreen} disabled={store.loading || store.universe.length === 0}
              className="flex-1 px-3 py-1.5 bg-primary text-primary-foreground rounded text-sm font-medium disabled:opacity-50">
              {store.loading ? "运行中..." : (t.screenerRun || "运行选股")}
            </button>
            <button onClick={() => setShowSave(true)} className="px-3 py-1.5 border rounded text-sm hover:bg-muted"><Save className="h-4 w-4" /></button>
          </div>
          {showSave && (
            <div className="flex gap-1 text-xs">
              <input value={presetName} onChange={(e) => setPresetName(e.target.value)} placeholder="预设名称..." className="flex-1 border rounded px-2 py-1 bg-background" />
              <button onClick={() => { store.savePreset(presetName); setShowSave(false); setPresetName(""); }}
                className="px-2 py-1 bg-primary text-primary-foreground rounded">保存</button>
            </div>
          )}

          {/* AI Recommend */}
          <button onClick={async () => { const r = await store.aiRecommend(); if (Array.isArray(r) && r.length > 0) { store.applyAiRecommend(r[0]); } }}
            className="flex items-center justify-center gap-1 px-3 py-1.5 rounded text-xs border border-dashed hover:bg-muted/50 transition">
            <Sparkles className="h-3 w-3" />{t.screenerAiRec || "AI 推荐"}
          </button>

          {/* Presets */}
          {store.presets.length > 0 && <h4 className="text-xs font-semibold mt-2">{t.screenerPresets || "预设方案"}</h4>}
          {store.presets.map((p) => (
            <div
              key={p.id}
              onClick={() => store.applyPreset(p)}
              className="flex items-center justify-between text-xs py-1 px-2 rounded hover:bg-muted/50 cursor-pointer"
            >
              <span>{p.name} {p.is_system && <Star className="h-2.5 w-2.5 inline text-amber-500" />}</span>
              {!p.is_system && <button onClick={(e) => { e.stopPropagation(); store.deletePreset(p.id); }} className="text-destructive"><Trash2 className="h-3 w-3" /></button>}
            </div>
          ))}
        </div>

        {/* Right: results table */}
        <div className="flex-1 border rounded-xl overflow-auto">
          {/* Error banner when data loading fails */}
          {store.dataSource === "error" && store.results.length === 0 && (
            <div className="m-3 p-3 rounded-lg bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 text-xs text-down space-y-1">
              <p className="font-semibold">⚠ 数据加载失败</p>
              <p>无法从 DataStore 获取股票行情数据。请检查：</p>
              <ul className="list-disc pl-4 space-y-0.5">
                <li>数据源配置是否可用（tushare / futu / eastmoney）</li>
                <li>网络连接是否正常</li>
                <li>尝试选择更小的股票池（如「活跃A股(100只)」）</li>
              </ul>
            </div>
          )}
          {store.results.length === 0 ? (
            <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
              {t.screenerNoResults || "点击「运行选股」查看结果"}
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between px-3 py-2 border-b bg-muted/30">
                <span className="text-xs text-muted-foreground">
                  {store.results.length} 条结果
                </span>
                <ExportToWorkflowButton
                  sourcePage="screener"
                  config={{
                    mode: store.mode || "filter",
                    conditions: store.conditions || [],
                    universe: store.universe || [],
                  }}
                />
              </div>
          ) : (
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-card border-b">
                <tr>
                  <th className="text-left py-2 px-3 w-8"></th>
                  <th className="text-left py-2 px-3">代码</th>
                  <th className="text-left py-2 px-3">名称</th>
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
            </>
          )}
        </div>
      </div>

      {/* Batch actions */}
      {selectedSymbols.size > 0 && (
        <div className="flex items-center gap-2 p-2 border rounded-lg bg-muted/20 text-xs">
          <span>已选 {selectedSymbols.size} 只</span>
          <button onClick={() => store.batchAddWatchlist([...selectedSymbols])} className="px-2 py-1 bg-primary/10 text-primary rounded hover:bg-primary/20">
            <Star className="h-3 w-3 inline mr-1" />加入自选
          </button>
          <button onClick={() => store.batchBacktest([...selectedSymbols])} className="px-2 py-1 bg-primary/10 text-primary rounded hover:bg-primary/20">
            <BarChart3 className="h-3 w-3 inline mr-1" />批量回测
          </button>
          <button className="px-2 py-1 border rounded hover:bg-muted">
            <Download className="h-3 w-3 inline mr-1" />导出 CSV
          </button>
        </div>
      )}
    </div>
  );
}
