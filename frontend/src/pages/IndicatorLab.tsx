import { useCallback, useEffect, useState } from "react";
import { Code, FlaskConical, Play, Save, Sparkles, ChevronDown, Trash2, Plus, BarChart3, Clock } from "lucide-react";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n";
import { authHeaders } from "@/lib/apiAuth";
import { CodeEditor } from "@/components/indicator-lab/CodeEditor";
import { QualityHints } from "@/components/indicator-lab/QualityHints";
import { ParamPanel } from "@/components/indicator-lab/ParamPanel";
import { BacktestPanel } from "@/components/indicator-lab/BacktestPanel";
import { HistoryPanel } from "@/components/indicator-lab/HistoryPanel";
import type {
  IndicatorInfo,
  IndicatorDetail,
  VerifyResult,
} from "@/components/indicator-lab/types";

const API_BASE = "/indicator-lab";

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json", ...authHeaders() as Record<string, string> };
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers: { ...headers, ...(options?.headers as Record<string, string> || {}) } });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

const DEFAULT_CODE = `my_indicator_name = "My First Indicator"
my_indicator_description = "A simple RSI-based strategy"

# @param rsi_period int 14 RSI lookback period
# @param oversold int 30 Oversold threshold
# @param overbought int 70 Overbought threshold
# @strategy stopLossPct 0.02
# @strategy takeProfitPct 0.05
# @strategy entryPct 0.5

df = df.copy()

period = params.get("rsi_period", 14)
oversold = params.get("oversold", 30)
overbought = params.get("overbought", 70)

delta = df["close"].diff()
gain = delta.where(delta > 0, 0.0)
loss = (-delta).where(delta < 0, 0.0)
avg_gain = gain.rolling(window=period, min_periods=period).mean()
avg_loss = loss.rolling(window=period, min_periods=period).mean()
rs = avg_gain / avg_loss.replace(0, np.nan)
rsi = 100.0 - (100.0 / (1.0 + rs))

df["buy"] = rsi < oversold
df["sell"] = rsi > overbought

output = {
    "name": my_indicator_name,
    "plots": [
        {"name": "RSI", "data": rsi.tolist(), "color": "#9C27B0", "overlay": False},
    ],
    "signals": [
        {"type": "buy", "text": "Buy", "data": df["buy"].where(df["buy"]).reindex(df.index).tolist(), "color": "#4CAF50"},
        {"type": "sell", "text": "Sell", "data": df["sell"].where(df["sell"]).reindex(df.index).tolist(), "color": "#F44336"},
    ],
}
`;

export function IndicatorLab() {
  const { t } = useI18n();
  const [code, setCode] = useState(DEFAULT_CODE);
  const [indicators, setIndicators] = useState<IndicatorInfo[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [verifyResult, setVerifyResult] = useState<VerifyResult | null>(null);
  const [saving, setSaving] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [generatedCode, setGeneratedCode] = useState("");
  const [paramValues, setParamValues] = useState<Record<string, string | number | boolean>>({});
  const [sidePanel, setSidePanel] = useState<"params" | "quality" | "indicators" | "history">("indicators");
  const [showBacktest, setShowBacktest] = useState(false);

  // Load indicator list
  const loadList = useCallback(async () => {
    try {
      const data = await apiFetch<{ indicators: IndicatorInfo[] }>("/list");
      setIndicators(data.indicators);
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    loadList();
  }, [loadList]);

  // Load selected indicator
  useEffect(() => {
    if (!selectedId) return;
    apiFetch<IndicatorDetail>(`/${selectedId}`)
      .then((data) => {
        setCode(data.code);
        setMessage(null);
      })
      .catch(() => setMessage("Failed to load indicator"));
  }, [selectedId]);

  // Save
  const handleSave = async () => {
    setSaving(true);
    setMessage(null);
    try {
      const data = await apiFetch<IndicatorInfo>("/save", {
        method: "POST",
        body: JSON.stringify({ code, indicator_id: selectedId || undefined }),
      });
      setSelectedId(data.id);
      setMessage(`Saved as "${data.name}"`);
      loadList();
    } catch (e) {
      setMessage(String(e));
    } finally {
      setSaving(false);
    }
  };

  // Verify
  const handleVerify = async () => {
    setVerifying(true);
    setMessage(null);
    try {
      const result = await apiFetch<VerifyResult>("/verify", {
        method: "POST",
        body: JSON.stringify({ code }),
      });
      setVerifyResult(result);

      // Initialize param values from defaults
      const pv: Record<string, string | number | boolean> = {};
      for (const p of result.params) {
        pv[p.name] = p.default;
      }
      setParamValues(pv);

      if (result.success) {
        setMessage(`Verification passed: ${result.plots_count} plots, ${result.signals_count} signals${result.has_buy_sell ? ", buy/sell columns" : ""}`);
        setSidePanel("params");
      } else {
        setMessage(`Verification failed: ${result.error}`);
        setSidePanel("quality");
      }
    } catch (e) {
      setMessage(String(e));
      setVerifyResult({ success: false, error: String(e), quality_hints: [], params: [], strategy_config: {}, plots_count: 0, signals_count: 0, has_buy_sell: false });
    } finally {
      setVerifying(false);
    }
  };

  // Generate
  const handleGenerate = async () => {
    setGenerating(true);
    setGeneratedCode("");
    setMessage(null);
    try {
      const res = await fetch(`${API_BASE}/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: "Create a momentum-based trading indicator with RSI and MACD confirmation", style: "momentum" }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const reader = res.body?.getReader();
      if (!reader) throw new Error("No response body");

      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const evt = JSON.parse(line.slice(6));
            if (evt.type === "code") {
              setGeneratedCode((prev) => prev + evt.content);
            } else if (evt.type === "done") {
              setMessage("Generation complete");
            } else if (evt.type === "error") {
              setMessage(`Generation error: ${evt.message}`);
            }
          } catch { /* ignore parse errors */ }
        }
      }
    } catch (e) {
      setMessage(String(e));
    } finally {
      setGenerating(false);
    }
  };

  // Accept generated code
  const acceptGenerated = () => {
    setCode(generatedCode);
    setGeneratedCode("");
    setMessage("Generated code loaded into editor");
  };

  // Delete
  const handleDelete = async (id: string) => {
    try {
      await apiFetch(`/delete/${id}`, { method: "POST" });
      if (selectedId === id) setSelectedId(null);
      loadList();
      setMessage("Indicator deleted");
    } catch (e) {
      setMessage(String(e));
    }
  };

  // New
  const handleNew = () => {
    setCode(DEFAULT_CODE);
    setSelectedId(null);
    setVerifyResult(null);
    setMessage(null);
    setGeneratedCode("");
  };

  return (
    <div className="flex h-[calc(100vh-3rem)]">
      {/* Main editor area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-2 border-b bg-card shrink-0">
          <div className="flex items-center gap-2">
            <FlaskConical className="h-4 w-4 text-primary" />
            <h1 className="text-sm font-semibold">{t.indicatorLab}</h1>
          </div>
          <div className="flex items-center gap-1.5">
            <button
              onClick={handleNew}
              className="flex items-center gap-1 px-2 py-1 text-xs rounded hover:bg-muted transition-colors"
              title={t.indicatorLabNewIndicator}
            >
              <Plus className="h-3 w-3" />
              {t.indicatorLabNew}
            </button>
            <button
              onClick={handleGenerate}
              disabled={generating}
              className="flex items-center gap-1 px-2 py-1 text-xs rounded bg-primary/10 text-primary hover:bg-primary/20 transition-colors disabled:opacity-50"
            >
              <Sparkles className="h-3 w-3" />
              {generating ? t.indicatorLabGenerating : t.indicatorLabAIGenerate}
            </button>
            <button
              onClick={() => setShowBacktest(true)}
              className="flex items-center gap-1 px-2 py-1 text-xs rounded bg-success/10 text-success hover:bg-success/20 transition-colors"
            >
              <BarChart3 className="h-3 w-3" />
              {t.indicatorLabBacktest}
            </button>
            <button
              onClick={handleVerify}
              disabled={verifying}
              className="flex items-center gap-1 px-2 py-1 text-xs rounded bg-warning/10 text-warning hover:bg-warning/20 transition-colors disabled:opacity-50"
            >
              <Play className="h-3 w-3" />
              {verifying ? t.indicatorLabVerifying : t.indicatorLabVerify}
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="flex items-center gap-1 px-2 py-1 text-xs rounded bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
            >
              <Save className="h-3 w-3" />
              {saving ? t.indicatorLabSaving : t.indicatorLabSave}
            </button>
          </div>
        </div>

        {/* Message bar */}
        {message && (
          <div className={cn(
            "px-4 py-1.5 text-xs border-b shrink-0",
            message.includes("failed") || message.includes("error") || message.includes("Error")
              ? "bg-danger/10 text-danger border-danger/20"
              : "bg-success/10 text-success border-success/20"
          )}>
            {message}
          </div>
        )}

        {/* Generated code preview */}
        {generatedCode && (
          <div className="mx-4 mt-3 border border-primary/30 rounded-lg overflow-hidden bg-[#1e1e2e] shrink-0 max-h-48">
            <div className="flex items-center justify-between px-3 py-1 bg-primary/10">
              <span className="text-xs text-primary font-medium">AI Generated Code</span>
              <div className="flex items-center gap-1.5">
                <button
                  onClick={acceptGenerated}
                  className="px-2 py-0.5 text-xs rounded bg-primary text-primary-foreground hover:bg-primary/90"
                >
                  Accept
                </button>
                <button
                  onClick={() => setGeneratedCode("")}
                  className="px-2 py-0.5 text-xs rounded bg-muted text-muted-foreground hover:bg-muted/80"
                >
                  Dismiss
                </button>
              </div>
            </div>
            <pre className="p-3 text-xs text-[#cdd6f4] overflow-auto font-mono">{generatedCode}</pre>
          </div>
        )}

        {/* Editor */}
        <div className="flex-1 p-4 min-h-0">
          <CodeEditor
            value={code}
            onChange={setCode}
            onSave={handleSave}
            onVerify={handleVerify}
          />
        </div>
      </div>

      {/* Right sidebar */}
      <aside className="w-80 border-l bg-card flex flex-col shrink-0">
        {/* Panel tabs */}
        <div className="flex border-b shrink-0">
          {([
            ["indicators", t.indicatorLabList, Code],
            ["params", t.indicatorLabParams, FlaskConical],
            ["quality", t.indicatorLabQuality, ChevronDown],
            ["history", t.indicatorLabHistory, Clock],
          ] as const).map(([key, label, Icon]) => (
            <button
              key={key}
              onClick={() => setSidePanel(key)}
              className={cn(
                "flex-1 flex items-center justify-center gap-1 py-2 text-xs transition-colors",
                sidePanel === key
                  ? "text-primary border-b-2 border-primary bg-primary/5 font-medium"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              <Icon className="h-3 w-3" />
              {label}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-auto p-3">
          {sidePanel === "indicators" && (
            <div className="space-y-1">
              {indicators.length === 0 && (
                <p className="text-xs text-muted-foreground text-center py-8">
                  {t.indicatorLabNoIndicators}
                </p>
              )}
              {indicators.map((ind) => (
                <div
                  key={ind.id}
                  className={cn(
                    "flex items-center justify-between px-2 py-1.5 rounded text-xs cursor-pointer transition-colors group",
                    selectedId === ind.id
                      ? "bg-primary/10 text-primary"
                      : "hover:bg-muted text-muted-foreground hover:text-foreground"
                  )}
                  onClick={() => setSelectedId(ind.id)}
                >
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-medium">{ind.name}</div>
                    <div className="text-[10px] opacity-60">{ind.param_count} params</div>
                  </div>
                  <button
                    onClick={(e) => { e.stopPropagation(); handleDelete(ind.id); }}
                    className="p-1 opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-danger rounded transition-all"
                    title="Delete"
                  >
                    <Trash2 className="h-3 w-3" />
                  </button>
                </div>
              ))}
            </div>
          )}

          {sidePanel === "params" && (
            <ParamPanel
              params={verifyResult?.params || []}
              values={paramValues}
              onChange={(name, value) => setParamValues((prev) => ({ ...prev, [name]: value }))}
            />
          )}

          {sidePanel === "quality" && (
            <QualityHints hints={verifyResult?.quality_hints || []} />
          )}

          {sidePanel === "history" && (
            <HistoryPanel indicatorId={selectedId || ""} />
          )}
        </div>

        {/* Strategy config footer */}
        {verifyResult?.strategy_config && Object.keys(verifyResult.strategy_config).length > 0 && (
          <div className="border-t p-3 shrink-0">
            <div className="text-xs font-medium text-muted-foreground mb-2">{t.indicatorLabStrategyConfig}</div>
            <div className="grid grid-cols-2 gap-1">
              {Object.entries(verifyResult.strategy_config).map(([key, val]) => (
                <div key={key} className="text-[10px]">
                  <span className="text-muted-foreground">{key}</span>
                  <span className="ml-1 font-mono text-foreground">{String(val)}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </aside>

      {/* Backtest modal */}
      {showBacktest && (
        <BacktestPanel code={code} onClose={() => setShowBacktest(false)} />
      )}
    </div>
  );
}
