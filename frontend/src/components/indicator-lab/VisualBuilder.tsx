import { useState } from "react";
import { X, Plus, Trash2, Wand2 } from "lucide-react";
import { useI18n } from "@/lib/i18n";
import { authHeaders } from "@/lib/apiAuth";

interface Rule {
  indicator: string;
  condition: string;
  period: number;
  value: number;
}

interface VisualBuilderProps {
  mode: "indicator" | "strategy";
  onClose: () => void;
  onCodeGenerated: (code: string, name: string) => void;
}

const INDICATORS: Record<string, string> = {
  ema: "EMA",
  ma: "MA",
  rsi: "RSI",
  macd: "MACD",
  bollinger: "Bollinger",
  kdj: "KDJ",
  supertrend: "SuperTrend",
};

const CONDITIONS_BY_INDICATOR: Record<string, Record<string, string>> = {
  ema: { cross_up: "上穿", cross_down: "下穿", price_above: "价格在上", price_below: "价格在下" },
  ma: { cross_up: "上穿", cross_down: "下穿", price_above: "价格在上", price_below: "价格在下" },
  rsi: { cross_up: "上穿阈值", cross_down: "下穿阈值", ">": "大于", "<": "小于" },
  macd: { gold_cross: "金叉", death_cross: "死叉", diff_gt_dea: "DIF > DEA", diff_lt_dea: "DIF < DEA" },
  bollinger: { price_above_upper: "突破上轨", price_below_lower: "跌破下轨", price_above_mid: "突破中轨", price_below_mid: "跌破中轨" },
  kdj: { gold_cross: "金叉", death_cross: "死叉", j_oversold: "J超卖", j_overbought: "J超买" },
  supertrend: { trend_bullish: "趋势转多", trend_bearish: "趋势转空" },
};

const DEFAULT_PERIODS: Record<string, number> = {
  ema: 20, ma: 20, rsi: 14, macd: 12, bollinger: 20, kdj: 9, supertrend: 10,
};

function emptyRule(): Rule {
  return { indicator: "ema", condition: "cross_up", period: 20, value: 30 };
}

const labelClass = "text-[11px] font-medium text-muted-foreground";
const inputClass = "w-full text-xs rounded-lg border border-border bg-background px-2 py-1.5 focus:outline-none focus:border-primary/50 transition-all duration-150";

export function VisualBuilder({ mode, onClose, onCodeGenerated }: VisualBuilderProps) {
  const { t } = useI18n();
  const [name, setName] = useState("");
  const [logic, setLogic] = useState<"and" | "or">("and");
  const [entryRules, setEntryRules] = useState<Rule[]>([emptyRule()]);
  const [exitRules, setExitRules] = useState<Rule[]>([emptyRule()]);
  const [stopLoss, setStopLoss] = useState(false);
  const [stopLossVal, setStopLossVal] = useState(5);
  const [takeProfit, setTakeProfit] = useState(false);
  const [takeProfitVal, setTakeProfitVal] = useState(10);
  const [trailingStop, setTrailingStop] = useState(false);
  const [trailingStopVal, setTrailingStopVal] = useState(3);
  const [positionSize, setPositionSize] = useState(50);
  const [compiling, setCompiling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const updateRule = (rules: Rule[], setRules: (r: Rule[]) => void, idx: number, patch: Partial<Rule>) => {
    const next = rules.map((r, i) => {
      if (i !== idx) return r;
      const updated = { ...r, ...patch };
      if (patch.indicator && patch.indicator !== r.indicator) {
        updated.condition = Object.keys(CONDITIONS_BY_INDICATOR[patch.indicator] || {})[0] || "";
        updated.period = DEFAULT_PERIODS[patch.indicator] || 20;
      }
      return updated;
    });
    setRules(next);
  };

  const removeRule = (rules: Rule[], setRules: (r: Rule[]) => void, idx: number) => {
    if (rules.length <= 1) return;
    setRules(rules.filter((_, i) => i !== idx));
  };

  const buildConfig = () => ({
    name: name || "Custom Strategy",
    logic,
    entry_rules: entryRules.map((r) => ({
      indicator: r.indicator,
      operator: r.condition,
      params: { period: r.period },
      value: r.value,
    })),
    exit_rules: exitRules.map((r) => ({
      indicator: r.indicator,
      operator: r.condition,
      params: { period: r.period },
      value: r.value,
    })),
    risk_management: {
      stop_loss: { enabled: stopLoss, value: stopLossVal },
      take_profit: { enabled: takeProfit, value: takeProfitVal },
      trailing_stop: { enabled: trailingStop, value: trailingStopVal, activation: trailingStopVal + 1 },
    },
    position_config: { initial_size_pct: positionSize, leverage: 1, max_pyramiding: 0 },
  });

  const handleCompile = async () => {
    setCompiling(true);
    setError(null);
    try {
      const config = buildConfig();
      const endpoint = mode === "strategy" ? "/v1/strategy-lab/compile" : "/v1/indicator-lab/compile";
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify(config),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error((d as { detail?: string }).detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      onCodeGenerated(data.code, config.name);
      onClose();
    } catch (e) {
      setError(String(e));
    } finally {
      setCompiling(false);
    }
  };

  const renderRuleRow = (rule: Rule, rules: Rule[], setRules: (r: Rule[]) => void, idx: number) => {
    const conditions = CONDITIONS_BY_INDICATOR[rule.indicator] || {};
    return (
      <div key={idx} className="flex items-center gap-1.5 p-2 rounded-lg bg-muted/30 border border-border/50">
        <select
          value={rule.indicator}
          onChange={(e) => updateRule(rules, setRules, idx, { indicator: e.target.value })}
          className={inputClass}
          style={{ width: 100 }}
        >
          {Object.entries(INDICATORS).map(([k, v]) => (<option key={k} value={k}>{v}</option>))}
        </select>
        <select
          value={rule.condition}
          onChange={(e) => updateRule(rules, setRules, idx, { condition: e.target.value })}
          className={inputClass}
          style={{ width: 110 }}
        >
          {Object.entries(conditions).map(([k, v]) => (<option key={k} value={k}>{v}</option>))}
        </select>
        <input
          type="number"
          value={rule.period}
          onChange={(e) => updateRule(rules, setRules, idx, { period: Number(e.target.value) || 1 })}
          className={inputClass}
          style={{ width: 56 }}
          placeholder={t.visualBuilderPeriod}
        />
        {rule.condition.includes(">") || rule.condition.includes("<") || rule.condition.includes("over") ? (
          <input
            type="number"
            value={rule.value}
            onChange={(e) => updateRule(rules, setRules, idx, { value: Number(e.target.value) || 0 })}
            className={inputClass}
            style={{ width: 56 }}
            placeholder={t.visualBuilderValue}
          />
        ) : (
          <div style={{ width: 56 }} />
        )}
        <button
          onClick={() => removeRule(rules, setRules, idx)}
          disabled={rules.length <= 1}
          className="btn-ghost p-1 rounded-md disabled:opacity-20 shrink-0"
        >
          <Trash2 className="h-3.5 w-3.5 text-muted-foreground" />
        </button>
      </div>
    );
  };

  const renderSection = (
    title: string,
    rules: Rule[],
    setRules: (r: Rule[]) => void,
  ) => (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">{title}</span>
        <div className="flex-1" />
        <button
          onClick={() => setRules([...rules, emptyRule()])}
          className="btn-ghost p-1 rounded-md text-xs text-muted-foreground hover:text-primary flex items-center gap-1"
        >
          <Plus className="h-3 w-3" />
          {t.visualBuilderAddRule}
        </button>
      </div>
      <div className="space-y-1.5">
        {rules.map((r, i) => renderRuleRow(r, rules, setRules, i))}
      </div>
    </div>
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div
        className="bg-card border rounded-2xl shadow-2xl w-[600px] max-h-[85vh] overflow-auto animate-scale-in"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b sticky top-0 bg-card rounded-t-2xl z-10">
          <div className="flex items-center gap-2.5">
            <div className="h-7 w-7 rounded-lg bg-primary/10 flex items-center justify-center">
              <Wand2 className="h-4 w-4 text-primary" />
            </div>
            <h2 className="text-base font-semibold">{t.customModeTitle}</h2>
          </div>
          <button onClick={onClose} className="btn-ghost p-1.5 rounded-lg"><X className="h-4 w-4" /></button>
        </div>

        {/* Body */}
        <div className="p-5 space-y-5">
          {/* Name */}
          <div className="space-y-1.5">
            <label className={labelClass}>{t.visualBuilderName}</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className={inputClass}
              placeholder="My Custom Strategy"
            />
          </div>

          {/* Logic */}
          <div className="flex items-center gap-2">
            <label className={labelClass}>{t.visualBuilderAnd}:</label>
            <select value={logic} onChange={(e) => setLogic(e.target.value as "and" | "or")} className={inputClass} style={{ width: 160 }}>
              <option value="and">{t.visualBuilderLogicAnd}</option>
              <option value="or">{t.visualBuilderLogicOr}</option>
            </select>
          </div>

          {/* Entry rules */}
          {renderSection(t.visualBuilderEntryRules, entryRules, setEntryRules)}

          {/* Exit rules */}
          {renderSection(t.visualBuilderExitRules, exitRules, setExitRules)}

          {/* Risk settings */}
          <div className="space-y-3">
            <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">{t.visualBuilderRiskSettings}</span>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <label className="flex items-center gap-1.5 text-xs">
                  <input type="checkbox" checked={stopLoss} onChange={(e) => setStopLoss(e.target.checked)} className="rounded" />
                  {t.visualBuilderStopLoss}
                </label>
                {stopLoss && (
                  <div className="flex items-center gap-2">
                    <input type="range" min={1} max={20} value={stopLossVal} onChange={(e) => setStopLossVal(Number(e.target.value))} className="flex-1" />
                    <span className="text-xs font-mono w-10 text-right">{stopLossVal}%</span>
                  </div>
                )}
              </div>
              <div className="space-y-1.5">
                <label className="flex items-center gap-1.5 text-xs">
                  <input type="checkbox" checked={takeProfit} onChange={(e) => setTakeProfit(e.target.checked)} className="rounded" />
                  {t.visualBuilderTakeProfit}
                </label>
                {takeProfit && (
                  <div className="flex items-center gap-2">
                    <input type="range" min={1} max={50} value={takeProfitVal} onChange={(e) => setTakeProfitVal(Number(e.target.value))} className="flex-1" />
                    <span className="text-xs font-mono w-10 text-right">{takeProfitVal}%</span>
                  </div>
                )}
              </div>
              <div className="space-y-1.5 col-span-2">
                <label className="flex items-center gap-1.5 text-xs">
                  <input type="checkbox" checked={trailingStop} onChange={(e) => setTrailingStop(e.target.checked)} className="rounded" />
                  {t.visualBuilderTrailingStop}
                </label>
                {trailingStop && (
                  <div className="flex items-center gap-2">
                    <input type="range" min={1} max={15} value={trailingStopVal} onChange={(e) => setTrailingStopVal(Number(e.target.value))} className="flex-1" />
                    <span className="text-xs font-mono w-10 text-right">{trailingStopVal}%</span>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Position size */}
          <div className="space-y-1.5">
            <label className={labelClass}>{t.visualBuilderPositionSize}</label>
            <div className="flex items-center gap-2">
              <input type="range" min={10} max={100} step={5} value={positionSize} onChange={(e) => setPositionSize(Number(e.target.value))} className="flex-1" />
              <span className="text-xs font-mono w-10 text-right">{positionSize}%</span>
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="px-4 py-2.5 rounded-lg text-sm bg-danger/10 text-danger border border-danger/20">{error}</div>
          )}

          {/* Compile button */}
          <button
            onClick={handleCompile}
            disabled={compiling}
            className="btn-md btn-primary w-full justify-center"
          >
            <Wand2 className="h-4 w-4" />
            {compiling ? t.visualBuilderCompiling : t.visualBuilderCompile}
          </button>
        </div>
      </div>
    </div>
  );
}
