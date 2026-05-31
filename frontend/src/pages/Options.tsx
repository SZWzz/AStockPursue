import { useState } from "react";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { TrendingUp, Calculator, Activity } from "lucide-react";

interface GreeksResult {
  price: number; delta: number; gamma: number; theta: number; vega: number; rho: number;
}

export function Options() {
  const { t } = useI18n();
  const [S, setS] = useState("100");
  const [K, setK] = useState("105");
  const [T, setT] = useState("0.5");
  const [rate, setRate] = useState("0.03");
  const [sigma, setSigma] = useState("0.25");
  const [optType, setOptType] = useState<"call" | "put">("call");
  const [result, setResult] = useState<GreeksResult | null>(null);
  const [binomialResult, setBinomialResult] = useState<number | null>(null);
  const [ivPrice, setIvPrice] = useState("");
  const [ivResult, setIvResult] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);

  const calcBS = async () => {
    setLoading(true);
    try {
      const resp = await (api as any).optionsBlackScholes({ S: +S, K: +K, T: +T, r: +rate, sigma: +sigma, option_type: optType });
      setResult(resp);
    } catch { setResult(null); }
    setLoading(false);
  };

  const calcBinomial = async () => {
    try {
      const resp = await (api as any).optionsBinomial({ S: +S, K: +K, T: +T, r: +rate, sigma: +sigma, n_steps: 100, option_type: optType });
      setBinomialResult(resp?.price);
    } catch { /* ignore */ }
  };

  const calcIV = async () => {
    if (!ivPrice) return;
    try {
      const resp = await (api as any).optionsImpliedVol({ S: +S, K: +K, T: +T, r: +rate, market_price: +ivPrice, option_type: optType });
      setIvResult(resp?.implied_vol);
    } catch { setIvResult(null); }
  };

  const greeksLabels: { key: keyof GreeksResult; label: string; fmt: string }[] = [
    { key: "price", label: "Price", fmt: "0.0000" },
    { key: "delta", label: "Delta Δ", fmt: "0.0000" },
    { key: "gamma", label: "Gamma Γ", fmt: "0.000000" },
    { key: "theta", label: "Theta Θ /day", fmt: "0.000000" },
    { key: "vega", label: "Vega ν /1%", fmt: "0.0000" },
    { key: "rho", label: "Rho ρ /1%", fmt: "0.0000" },
  ];

  return (
    <div className="flex flex-col h-full p-4 gap-3">
      <h1 className="text-lg font-bold flex items-center gap-2"><TrendingUp className="h-5 w-5" />{t.options || "Options Analysis"}</h1>

      <div className="flex gap-3 flex-1 min-h-0">
        {/* Input panel */}
        <div className="w-72 shrink-0 border rounded-xl p-3 space-y-2 overflow-y-auto">
          <h3 className="text-sm font-semibold">{t.optionsParams || "Parameters"}</h3>
          {[
            { label: "Spot (S)", val: S, set: setS },
            { label: "Strike (K)", val: K, set: setK },
            { label: "Time (T, years)", val: T, set: setT },
            { label: "Rate (r)", val: rate, set: setRate },
            { label: "Vol (σ)", val: sigma, set: setSigma },
          ].map((f) => (
            <div key={f.label}>
              <label className="text-[10px] text-muted-foreground">{f.label}</label>
              <input type="number" step="0.01" value={f.val} onChange={(e) => f.set(e.target.value)}
                className="w-full border rounded px-2 py-1 text-sm bg-background" />
            </div>
          ))}
          <div className="flex gap-2">
            <button onClick={() => setOptType("call")} className={cn("flex-1 px-2 py-1 rounded text-xs", optType === "call" ? "bg-success/20 text-success font-medium" : "bg-muted")}>CALL</button>
            <button onClick={() => setOptType("put")} className={cn("flex-1 px-2 py-1 rounded text-xs", optType === "put" ? "bg-destructive/20 text-destructive font-medium" : "bg-muted")}>PUT</button>
          </div>
          <button onClick={calcBS} disabled={loading}
            className="w-full flex items-center justify-center gap-1 px-3 py-2 bg-primary text-primary-foreground rounded text-sm disabled:opacity-50">
            <Calculator className="h-4 w-4" />{loading ? "Calculating..." : "Black-Scholes + Greeks"}
          </button>
          <button onClick={calcBinomial}
            className="w-full px-3 py-1.5 border rounded text-xs hover:bg-muted">
            Binomial Tree (100 steps)
          </button>

          {/* Implied Vol */}
          <div className="border-t pt-2 mt-2">
            <label className="text-[10px] text-muted-foreground">Market Price → Implied Vol</label>
            <div className="flex gap-1">
              <input type="number" step="0.01" value={ivPrice} onChange={(e) => setIvPrice(e.target.value)}
                placeholder="Market price" className="flex-1 border rounded px-2 py-1 text-sm bg-background" />
              <button onClick={calcIV} className="px-2 py-1 bg-muted rounded text-xs hover:bg-muted/70">
                <Activity className="h-4 w-4" />
              </button>
            </div>
            {ivResult != null && <div className="text-xs mt-1">σ_implied = <span className="font-mono font-bold">{ivResult.toFixed(6)}</span></div>}
          </div>
        </div>

        {/* Results panel */}
        <div className="flex-1 border rounded-xl p-4 overflow-auto">
          {!result ? (
            <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
              {t.optionsHint || "Enter parameters and click Calculate"}
            </div>
          ) : (
            <div className="space-y-4">
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {greeksLabels.map((g) => (
                  <div key={g.key} className="border rounded-lg p-3 text-center">
                    <div className="text-xs text-muted-foreground">{g.label}</div>
                    <div className="text-lg font-bold font-mono">{result[g.key]?.toFixed?.(g.key === "gamma" || g.key === "theta" ? 6 : 4)}</div>
                  </div>
                ))}
              </div>
              {binomialResult != null && (
                <div className="border rounded-lg p-3 bg-muted/20 text-sm">
                  <span className="text-muted-foreground">Binomial (100-step): </span>
                  <span className="font-mono font-bold">{binomialResult.toFixed(4)}</span>
                  {result && <span className="text-muted-foreground text-xs ml-2">vs BS: {Math.abs(binomialResult - result.price).toFixed(6)}</span>}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
