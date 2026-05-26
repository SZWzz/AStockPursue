import { useCallback, useEffect, useState } from "react";
import { Code, FlaskConical, Play, Save, Sparkles, ChevronDown, Trash2, Plus, Clock, Library, Layers, ChevronsRight, ChevronsLeft } from "lucide-react";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n";
import { authHeaders } from "@/lib/apiAuth";
import { CodeEditor } from "@/components/indicator-lab/CodeEditor";
import { QualityHints } from "@/components/indicator-lab/QualityHints";
import { ParamPanel } from "@/components/indicator-lab/ParamPanel";
import { ChartPanel } from "@/components/indicator-lab/ChartPanel";
import { HistoryPanel } from "@/components/indicator-lab/HistoryPanel";
import { BuiltinIndicators, type BuiltinIndicator } from "@/components/indicator-lab/BuiltinIndicators";
import { TemplateBrowser, type TemplateItem } from "@/components/indicator-lab/TemplateBrowser";
import { AlphaZooBrowser } from "@/components/indicator-lab/AlphaZooBrowser";
import type {
  IndicatorInfo,
  IndicatorDetail,
  VerifyResult,
} from "@/components/indicator-lab/types";
import { useBacktest } from "@/hooks/useBacktest";

const API_BASE = "/v1/indicator-lab";

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json", ...authHeaders() as Record<string, string> };
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers: { ...headers, ...(options?.headers as Record<string, string> || {}) } });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ── Built-in indicators ───────────────────────────────────────────────────

const BUILTIN_INDICATORS: BuiltinIndicator[] = [
  {
    key: "sma",
    name: "Simple Moving Average",
    description: "Classic SMA with configurable period. Use as trend filter or overlay.",
    category: "trend",
    code: `my_indicator_name = "Simple Moving Average"
my_indicator_description = "Classic SMA trend indicator"

# @param period int 20 SMA period range=5:200:5
# @strategy stopLossPct 0.02
# @strategy takeProfitPct 0.05

df = df.copy()
period = params.get("period", 20)
sma = df["close"].rolling(window=period, min_periods=period).mean()
df["buy"] = (df["close"] > sma) & (df["close"].shift(1) <= sma.shift(1))
df["sell"] = (df["close"] < sma) & (df["close"].shift(1) >= sma.shift(1))

output = {
    "name": my_indicator_name,
    "plots": [{"name": f"SMA{period}", "data": sma.tolist(), "color": "#2196F3", "overlay": True}],
    "signals": [
        {"type": "buy", "text": "Buy", "data": df["buy"].where(df["buy"]).reindex(df.index).tolist(), "color": "#4CAF50"},
        {"type": "sell", "text": "Sell", "data": df["sell"].where(df["sell"]).reindex(df.index).tolist(), "color": "#F44336"},
    ],
}`,
  },
  {
    key: "ema",
    name: "Exponential Moving Average",
    description: "EMA crossover — faster response than SMA for trend changes.",
    category: "trend",
    code: `my_indicator_name = "EMA Crossover"
my_indicator_description = "Fast EMA crossing slow EMA"

# @param fast int 12 Fast EMA period range=5:50:1
# @param slow int 26 Slow EMA period range=10:100:1
# @strategy stopLossPct 0.02
# @strategy takeProfitPct 0.05

df = df.copy()
fast = params.get("fast", 12)
slow = params.get("slow", 26)
ema_fast = df["close"].ewm(span=fast, adjust=False, min_periods=fast).mean()
ema_slow = df["close"].ewm(span=slow, adjust=False, min_periods=slow).mean()
df["buy"] = (ema_fast > ema_slow) & (ema_fast.shift(1) <= ema_slow.shift(1))
df["sell"] = (ema_fast < ema_slow) & (ema_fast.shift(1) >= ema_slow.shift(1))

output = {
    "name": my_indicator_name,
    "plots": [
        {"name": f"EMA{fast}", "data": ema_fast.tolist(), "color": "#2196F3", "overlay": True},
        {"name": f"EMA{slow}", "data": ema_slow.tolist(), "color": "#FF9800", "overlay": True},
    ],
    "signals": [
        {"type": "buy", "text": "Buy", "data": df["buy"].where(df["buy"]).reindex(df.index).tolist(), "color": "#4CAF50"},
        {"type": "sell", "text": "Sell", "data": df["sell"].where(df["sell"]).reindex(df.index).tolist(), "color": "#F44336"},
    ],
}`,
  },
  {
    key: "rsi",
    name: "Relative Strength Index",
    description: "Momentum oscillator measuring speed and change of price movements.",
    category: "momentum",
    code: `my_indicator_name = "RSI"
my_indicator_description = "RSI oversold/overbought signals"

# @param period int 14 RSI period range=5:50:1
# @param oversold int 30 Oversold threshold range=10:40:5
# @param overbought int 70 Overbought threshold range=60:90:5
# @strategy stopLossPct 0.02
# @strategy takeProfitPct 0.05

df = df.copy()
period = params.get("period", 14)
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
    "plots": [{"name": "RSI", "data": rsi.tolist(), "color": "#9C27B0", "overlay": False}],
    "signals": [
        {"type": "buy", "text": "Buy", "data": df["buy"].where(df["buy"]).reindex(df.index).tolist(), "color": "#4CAF50"},
        {"type": "sell", "text": "Sell", "data": df["sell"].where(df["sell"]).reindex(df.index).tolist(), "color": "#F44336"},
    ],
}`,
  },
  {
    key: "macd",
    name: "MACD",
    description: "Moving Average Convergence Divergence — trend + momentum in one.",
    category: "momentum",
    code: `my_indicator_name = "MACD"
my_indicator_description = "MACD crossover signals"

# @param fast int 12 Fast EMA range=5:50:1
# @param slow int 26 Slow EMA range=10:100:1
# @param signal int 9 Signal line period range=3:20:1
# @strategy stopLossPct 0.02
# @strategy takeProfitPct 0.05

df = df.copy()
fast = params.get("fast", 12)
slow_p = params.get("slow", 26)
sig_period = params.get("signal", 9)
ema_fast = df["close"].ewm(span=fast, adjust=False, min_periods=fast).mean()
ema_slow = df["close"].ewm(span=slow_p, adjust=False, min_periods=slow_p).mean()
macd = ema_fast - ema_slow
signal_line = macd.ewm(span=sig_period, adjust=False, min_periods=sig_period).mean()
histogram = macd - signal_line
df["buy"] = (macd > signal_line) & (macd.shift(1) <= signal_line.shift(1))
df["sell"] = (macd < signal_line) & (macd.shift(1) >= signal_line.shift(1))

output = {
    "name": my_indicator_name,
    "plots": [
        {"name": "MACD", "data": macd.tolist(), "color": "#2196F3", "overlay": False},
        {"name": "Signal", "data": signal_line.tolist(), "color": "#FF9800", "overlay": False},
        {"name": "Hist", "data": histogram.tolist(), "color": "#9C27B0", "overlay": False},
    ],
    "signals": [
        {"type": "buy", "text": "Buy", "data": df["buy"].where(df["buy"]).reindex(df.index).tolist(), "color": "#4CAF50"},
        {"type": "sell", "text": "Sell", "data": df["sell"].where(df["sell"]).reindex(df.index).tolist(), "color": "#F44336"},
    ],
}`,
  },
  {
    key: "bollinger",
    name: "Bollinger Bands",
    description: "Volatility bands around a moving average — fade the extremes.",
    category: "volatility",
    code: `my_indicator_name = "Bollinger Bands"
my_indicator_description = "Bollinger Band mean reversion"

# @param period int 20 MA period range=10:50:5
# @param std_dev float 2.0 Standard deviations range=1.0:4.0:0.5
# @strategy stopLossPct 0.02
# @strategy takeProfitPct 0.05

df = df.copy()
period = params.get("period", 20)
std_dev = params.get("std_dev", 2.0)
mid = df["close"].rolling(window=period, min_periods=period).mean()
std = df["close"].rolling(window=period, min_periods=period).std()
upper = mid + std_dev * std
lower = mid - std_dev * std
df["buy"] = df["close"] < lower
df["sell"] = df["close"] > upper

output = {
    "name": my_indicator_name,
    "plots": [
        {"name": "Mid", "data": mid.tolist(), "color": "#2196F3", "overlay": True},
        {"name": "Upper", "data": upper.tolist(), "color": "#FF9800", "overlay": True},
        {"name": "Lower", "data": lower.tolist(), "color": "#FF9800", "overlay": True},
    ],
    "signals": [
        {"type": "buy", "text": "Buy", "data": df["buy"].where(df["buy"]).reindex(df.index).tolist(), "color": "#4CAF50"},
        {"type": "sell", "text": "Sell", "data": df["sell"].where(df["sell"]).reindex(df.index).tolist(), "color": "#F44336"},
    ],
}`,
  },
  {
    key: "atr",
    name: "Average True Range",
    description: "Volatility measure — use for dynamic stop-loss and position sizing.",
    category: "volatility",
    code: `my_indicator_name = "ATR Trailing Stop"
my_indicator_description = "ATR-based dynamic trailing stop"

# @param period int 14 ATR period range=5:50:1
# @param multiplier float 2.0 ATR multiplier range=1.0:5.0:0.5
# @strategy stopLossPct 0.04
# @strategy takeProfitPct 0.10

df = df.copy()
period = params.get("period", 14)
mult = params.get("multiplier", 2.0)
prev_close = df["close"].shift(1)
tr = pd.concat([df["high"] - df["low"], (df["high"] - prev_close).abs(), (df["low"] - prev_close).abs()], axis=1).max(axis=1)
atr = tr.ewm(alpha=1.0/period, adjust=False, min_periods=period).mean()
stop_long = df["close"] - mult * atr
stop_short = df["close"] + mult * atr
df["buy"] = df["close"] > stop_long.shift(1)
df["sell"] = df["close"] < stop_short.shift(1)

output = {
    "name": my_indicator_name,
    "plots": [
        {"name": "ATR", "data": atr.tolist(), "color": "#9C27B0", "overlay": False},
        {"name": "Stop Long", "data": stop_long.tolist(), "color": "#4CAF50", "overlay": True},
        {"name": "Stop Short", "data": stop_short.tolist(), "color": "#F44336", "overlay": True},
    ],
    "signals": [
        {"type": "buy", "text": "Buy", "data": df["buy"].where(df["buy"]).reindex(df.index).tolist(), "color": "#4CAF50"},
        {"type": "sell", "text": "Sell", "data": df["sell"].where(df["sell"]).reindex(df.index).tolist(), "color": "#F44336"},
    ],
}`,
  },
  {
    key: "obv",
    name: "On-Balance Volume",
    description: "Cumulative volume indicator — confirm price trends with volume flow.",
    category: "volume",
    code: `my_indicator_name = "OBV Divergence"
my_indicator_description = "OBV trend confirmation and divergence signals"

# @param smooth int 5 OBV smoothing period range=3:20:1
# @strategy stopLossPct 0.02
# @strategy takeProfitPct 0.05

df = df.copy()
smooth = params.get("smooth", 5)
price_change = df["close"].diff()
obv = pd.Series(0.0, index=df.index)
for i in range(1, len(df)):
    if price_change.iloc[i] > 0:
        obv.iloc[i] = obv.iloc[i - 1] + df["volume"].iloc[i]
    elif price_change.iloc[i] < 0:
        obv.iloc[i] = obv.iloc[i - 1] - df["volume"].iloc[i]
    else:
        obv.iloc[i] = obv.iloc[i - 1]
obv_sma = obv.rolling(window=smooth, min_periods=smooth).mean()
df["buy"] = (obv > obv_sma) & (obv.shift(1) <= obv_sma.shift(1))
df["sell"] = (obv < obv_sma) & (obv.shift(1) >= obv_sma.shift(1))

output = {
    "name": my_indicator_name,
    "plots": [
        {"name": "OBV", "data": obv.tolist(), "color": "#2196F3", "overlay": False},
        {"name": "OBV MA", "data": obv_sma.tolist(), "color": "#FF9800", "overlay": False},
    ],
    "signals": [
        {"type": "buy", "text": "Buy", "data": df["buy"].where(df["buy"]).reindex(df.index).tolist(), "color": "#4CAF50"},
        {"type": "sell", "text": "Sell", "data": df["sell"].where(df["sell"]).reindex(df.index).tolist(), "color": "#F44336"},
    ],
}`,
  },
  {
    key: "kdj",
    name: "KDJ Indicator",
    description: "Stochastic oscillator variant popular in China A-share markets.",
    category: "momentum",
    code: `my_indicator_name = "KDJ"
my_indicator_description = "KDJ oversold/overbought signals"

# @param period int 9 KDJ period range=5:30:1
# @param signal int 3 Signal smoothing range=2:10:1
# @strategy stopLossPct 0.02
# @strategy takeProfitPct 0.05

df = df.copy()
period = params.get("period", 9)
sig_period = params.get("signal", 3)
low_min = df["low"].rolling(window=period, min_periods=period).min()
high_max = df["high"].rolling(window=period, min_periods=period).max()
rsv = ((df["close"] - low_min) / (high_max - low_min).replace(0, np.nan)) * 100
k = rsv.ewm(span=sig_period, adjust=False, min_periods=sig_period).mean()
d = k.ewm(span=sig_period, adjust=False, min_periods=sig_period).mean()
j = 3 * k - 2 * d
df["buy"] = (k < 20) & (k > d) & (k.shift(1) <= d.shift(1))
df["sell"] = (k > 80) & (k < d) & (k.shift(1) >= d.shift(1))

output = {
    "name": my_indicator_name,
    "plots": [
        {"name": "K", "data": k.tolist(), "color": "#2196F3", "overlay": False},
        {"name": "D", "data": d.tolist(), "color": "#FF9800", "overlay": False},
        {"name": "J", "data": j.tolist(), "color": "#9C27B0", "overlay": False},
    ],
    "signals": [
        {"type": "buy", "text": "Buy", "data": df["buy"].where(df["buy"]).reindex(df.index).tolist(), "color": "#4CAF50"},
        {"type": "sell", "text": "Sell", "data": df["sell"].where(df["sell"]).reindex(df.index).tolist(), "color": "#F44336"},
    ],
}`,
  },
  {
    key: "ichimoku",
    name: "Ichimoku Cloud",
    description: "All-in-one indicator: trend direction, support/resistance, momentum.",
    category: "trend",
    code: `my_indicator_name = "Ichimoku Cloud"
my_indicator_description = "Ichimoku Kinko Hyo — cloud-based trend system"

# @param tenkan int 9 Conversion line range=5:30:1
# @param kijun int 26 Base line range=10:50:1
# @param senkou_b int 52 Span B range=26:100:1
# @strategy stopLossPct 0.03
# @strategy takeProfitPct 0.08

df = df.copy()
tenkan_p = params.get("tenkan", 9)
kijun_p = params.get("kijun", 26)
senkou_b_p = params.get("senkou_b", 52)
high_tenkan = df["high"].rolling(window=tenkan_p, min_periods=tenkan_p).max()
low_tenkan = df["low"].rolling(window=tenkan_p, min_periods=tenkan_p).min()
tenkan = (high_tenkan + low_tenkan) / 2
high_kijun = df["high"].rolling(window=kijun_p, min_periods=kijun_p).max()
low_kijun = df["low"].rolling(window=kijun_p, min_periods=kijun_p).min()
kijun = (high_kijun + low_kijun) / 2
senkou_a = ((tenkan + kijun) / 2).shift(kijun_p)
senkou_b = ((df["high"].rolling(window=senkou_b_p, min_periods=senkou_b_p).max() + df["low"].rolling(window=senkou_b_p, min_periods=senkou_b_p).min()) / 2).shift(kijun_p)
chikou = df["close"].shift(-kijun_p)
df["buy"] = (tenkan > kijun) & (tenkan.shift(1) <= kijun.shift(1)) & (df["close"] > senkou_a) & (df["close"] > senkou_b)
df["sell"] = (tenkan < kijun) & (tenkan.shift(1) >= kijun.shift(1)) & (df["close"] < senkou_a) & (df["close"] < senkou_b)

output = {
    "name": my_indicator_name,
    "plots": [
        {"name": "Tenkan", "data": tenkan.tolist(), "color": "#2196F3", "overlay": True},
        {"name": "Kijun", "data": kijun.tolist(), "color": "#FF9800", "overlay": True},
        {"name": "Senkou A", "data": senkou_a.tolist(), "color": "#4CAF50", "overlay": True},
        {"name": "Senkou B", "data": senkou_b.tolist(), "color": "#F44336", "overlay": True},
    ],
    "signals": [
        {"type": "buy", "text": "Buy", "data": df["buy"].where(df["buy"]).reindex(df.index).tolist(), "color": "#4CAF50"},
        {"type": "sell", "text": "Sell", "data": df["sell"].where(df["sell"]).reindex(df.index).tolist(), "color": "#F44336"},
    ],
}`,
  },
];

const INDICATOR_TEMPLATES: TemplateItem[] = [
  { key: "ma_crossover", name: "MA Crossover", description: "Dual moving average crossover — buy on golden cross, sell on death cross.", category: "trend", difficulty: "beginner", tags: ["MA", "crossover"] },
  { key: "rsi_reversal", name: "RSI Mean Reversion", description: "Buy when RSI drops below oversold, sell when above overbought.", category: "reversal", difficulty: "beginner", tags: ["RSI", "oscillator"] },
  { key: "macd_divergence", name: "MACD Crossover", description: "MACD line crossing signal line with histogram confirmation.", category: "trend", difficulty: "beginner", tags: ["MACD"] },
  { key: "bollinger_squeeze", name: "Bollinger Band", description: "Fade extremes — buy at lower band, sell at upper band.", category: "reversal", difficulty: "beginner", tags: ["Bollinger", "volatility"] },
  { key: "kdj", name: "KDJ Extreme", description: "KDJ overbought/oversold with golden cross confirmation.", category: "reversal", difficulty: "intermediate", tags: ["KDJ"] },
  { key: "supertrend", name: "SuperTrend", description: "ATR-based trailing stop trend following system.", category: "trend", difficulty: "intermediate", tags: ["ATR", "trailing"] },
];

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
  const [sidePanel, setSidePanel] = useState<"params" | "quality" | "indicators" | "history" | "builtins" | "templates" | "alphazoo">("indicators");
  const [rightCollapsed, setRightCollapsed] = useState(false);
  // ── Chart state ────────────────────────────────────────────────────────────

  const [chartSymbol, setChartSymbol] = useState("");
  const [chartStartDate, setChartStartDate] = useState("2024-01-01");
  const [chartEndDate, setChartEndDate] = useState("2025-12-31");
  const [chartSource, setChartSource] = useState("auto");
  const [chartInterval, setChartInterval] = useState("1D");
  const [initialCash, setInitialCash] = useState(100000);
  const [chartTitle, setChartTitle] = useState("");

  const {
    priceData,
    chartLoading, chartError,
    backtestRunning,
    btTradeMarkers,
    btEquityCurve,
    btIndicatorSeries,
    btMetrics,
    handleRunBacktest: runBacktest,
    fetchOHLCV,
    clearPolling,
  } = useBacktest();

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

  useEffect(() => {
    return () => { clearPolling(); };
  }, [clearPolling]);

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
      setChartTitle(data.name);
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
        headers: { "Content-Type": "application/json", ...authHeaders() },
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
    setChartTitle("AI Generated");
    setMessage("Generated code loaded into editor");
  };

  // ── Chart data fetch ───────────────────────────────────────────────────────

  const handleFetchOHLCV = useCallback(async () => {
    await fetchOHLCV(chartSymbol, chartStartDate, chartEndDate, chartSource, chartInterval);
  }, [fetchOHLCV, chartSymbol, chartStartDate, chartEndDate, chartSource, chartInterval]);

  // ── Run backtest + poll ────────────────────────────────────────────────────

  const handleRunBacktest = useCallback(async () => {
    if (!chartSymbol) return;
    await runBacktest(async () => {
      const res = await fetch("/v1/indicator-lab/backtest", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({
          code,
          symbol: chartSymbol,
          start_date: chartStartDate,
          end_date: chartEndDate,
          source: chartSource,
          interval: chartInterval,
          initial_cash: initialCash,
          leverage: 1,
        }),
      });
      const data = await res.json();
      if (!data.success || !data.run_id) throw new Error(data.error || "Backtest failed");
      return data.run_id;
    });
  }, [code, chartSymbol, chartStartDate, chartEndDate, chartSource, chartInterval, initialCash, runBacktest]);

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
    setChartTitle("");
    setVerifyResult(null);
    setMessage(null);
    setGeneratedCode("");
  };

  // Built-in indicator selection
  const handleBuiltinSelect = (indicator: BuiltinIndicator) => {
    setCode(indicator.code);
    setMessage(`Loaded: ${indicator.name}`);
    setSidePanel("indicators");
  };

  // Template selection — fetch template code from backend
  const handleTemplateSelect = async (template: TemplateItem) => {
    try {
      const data = await apiFetch<{ code: string }>(`/templates/${template.key}/generate`, {
        method: "POST",
      });
      setCode(data.code);
      setMessage(`Loaded template: ${template.name}`);
      setSidePanel("indicators");
    } catch (e) {
      setMessage(`Failed to load template: ${String(e)}`);
    }
  };

  // Alpha Zoo factor selection — convert and load into editor
  const handleAlphaZooSelect = (code: string, name: string) => {
    setCode(code);
    setMessage(`Loaded alpha: ${name}`);
    setSidePanel("indicators");
  };

  const isError = message && (message.includes("failed") || message.includes("error") || message.includes("Error"));

  return (
    <div className="flex h-[calc(100vh-3rem)]">
      {/* Main editor area */}
      <div className="flex-1 flex flex-col min-w-0 min-w-[320px]">
        {/* Header */}
        <div className="page-header">
          <div className="page-header-title">
            <div className="h-7 w-7 rounded-lg bg-primary/10 flex items-center justify-center">
              <FlaskConical className="h-4 w-4 text-primary" />
            </div>
            <div>
              <h1>{t.indicatorLab}</h1>
              <p className="page-header-desc">{t.indicatorLabPageDesc}</p>
            </div>
          </div>
          <div className="page-header-actions">
            <button onClick={handleNew} className="btn-sm btn-ghost">
              <Plus className="h-3.5 w-3.5" />
              {t.indicatorLabNew}
            </button>
            <button onClick={handleGenerate} disabled={generating} className="btn-sm btn-outline">
              <Sparkles className="h-3.5 w-3.5" />
              {generating ? t.indicatorLabGenerating : t.indicatorLabAIGenerate}
            </button>
            <button onClick={handleVerify} disabled={verifying} className="btn-sm btn-warning">
              <Play className="h-3.5 w-3.5" />
              {verifying ? t.indicatorLabVerifying : t.indicatorLabVerify}
            </button>
            <button onClick={handleSave} disabled={saving} className="btn-sm btn-primary">
              <Save className="h-3.5 w-3.5" />
              {saving ? t.indicatorLabSaving : t.indicatorLabSave}
            </button>
          </div>
        </div>

        {/* Message bar */}
        {message && (
          <div className={cn("message-bar", isError ? "error" : "success")}>
            {message}
          </div>
        )}

        {/* Generated code preview */}
        {generatedCode && (
          <div className="mx-5 mt-4 border border-primary/30 rounded-lg overflow-hidden bg-[#1e1e2e] shrink-0 max-h-52 animate-scale-in">
            <div className="flex items-center justify-between px-4 py-2 bg-primary/10">
              <span className="text-sm text-primary font-medium">AI Generated Code</span>
              <div className="flex items-center gap-2">
                <button onClick={acceptGenerated} className="btn-sm btn-primary">
                  Accept
                </button>
                <button onClick={() => setGeneratedCode("")} className="btn-sm btn-ghost">
                  Dismiss
                </button>
              </div>
            </div>
            <pre className="p-4 text-sm text-[#cdd6f4] overflow-auto font-mono">{generatedCode}</pre>
          </div>
        )}

        {/* Editor */}
        <div className="flex-1 p-5 min-h-0">
          <CodeEditor
            value={code}
            onChange={setCode}
            onSave={handleSave}
            onVerify={handleVerify}
          />
        </div>
      </div>

      {/* Chart panel */}
      <div className="flex-1 flex flex-col min-w-0 min-w-[380px] border-l">
        <ChartPanel
          symbol={chartSymbol}
          onSymbolChange={setChartSymbol}
          startDate={chartStartDate}
          endDate={chartEndDate}
          onStartDateChange={setChartStartDate}
          onEndDateChange={setChartEndDate}
          source={chartSource}
          onSourceChange={setChartSource}
          interval={chartInterval}
          onIntervalChange={setChartInterval}
          initialCash={initialCash}
          onInitialCashChange={setInitialCash}
          onFetch={handleFetchOHLCV}
          onRunBacktest={handleRunBacktest}
          priceData={priceData}
          loading={chartLoading}
          error={chartError}
          tradeMarkers={btTradeMarkers}
          equityCurve={btEquityCurve}
          indicatorSeries={btIndicatorSeries}
          metrics={btMetrics}
          backtestRunning={backtestRunning}
          title={chartTitle || undefined}
          backtestLabel={t.indicatorLabRunBacktest}
        />
      </div>

      {/* Right sidebar */}
      <aside className={cn(
        "border-l bg-card flex flex-col shrink-0 transition-all duration-200",
        rightCollapsed ? "w-10" : "w-80"
      )}>
        {/* Collapse toggle */}
        <div className={cn("flex items-center border-b", rightCollapsed ? "justify-center py-2" : "justify-end px-2 py-1")}>
          <button
            onClick={() => setRightCollapsed(!rightCollapsed)}
            className="p-1 text-muted-foreground hover:text-foreground rounded transition-colors"
            title={rightCollapsed ? t.expandSidebar : t.collapseSidebar}
          >
            {rightCollapsed ? <ChevronsLeft className="h-4 w-4" /> : <ChevronsRight className="h-4 w-4" />}
          </button>
        </div>

        {!rightCollapsed && (
        <>
        {/* Panel tabs */}
        <div className="tab-bar">
          {([
            ["indicators", t.indicatorLabList, Code],
            ["builtins", t.indicatorLabBuiltins, Library],
            ["templates", t.indicatorLabTemplates, Layers],
            ["params", t.indicatorLabParams, FlaskConical],
            ["quality", t.indicatorLabQuality, ChevronDown],
            ["alphazoo", t.alphaZoo, Layers],
            ["history", t.indicatorLabHistory, Clock],
          ] as const).map(([key, label, Icon]) => (
            <button
              key={key}
              onClick={() => setSidePanel(key)}
              className={cn("tab-item", sidePanel === key && "active")}
            >
              <Icon className="h-3.5 w-3.5" />
              {label}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-auto p-4">
          {sidePanel === "indicators" && (
            <div className="space-y-1">
              {indicators.length === 0 && (
                <div className="empty-state">
                  <Code className="empty-state-icon" />
                  <p className="empty-state-text">{t.indicatorLabNoIndicators}</p>
                  <p className="empty-state-hint">{t.indicatorLabNoIndicatorsHint}</p>
                </div>
              )}
              {indicators.map((ind) => (
                <div
                  key={ind.id}
                  className={cn(
                    "flex items-center justify-between px-3 py-2.5 rounded-lg text-sm cursor-pointer transition-all duration-150 group",
                    selectedId === ind.id
                      ? "bg-primary/10 text-primary font-medium shadow-sm"
                      : "hover:bg-muted text-muted-foreground hover:text-foreground"
                  )}
                  onClick={() => { setSelectedId(ind.id); setChartTitle(ind.name); }}
                >
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-medium">{ind.name}</div>
                    <div className="text-xs opacity-60 mt-0.5">{ind.param_count} params</div>
                  </div>
                  <button
                    onClick={(e) => { e.stopPropagation(); handleDelete(ind.id); }}
                    className="p-1.5 opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-danger rounded-md transition-all"
                    title="Delete"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
            </div>
          )}

          {sidePanel === "builtins" && (
            <BuiltinIndicators
              indicators={BUILTIN_INDICATORS}
              onSelect={handleBuiltinSelect}
            />
          )}

          {sidePanel === "templates" && (
            <TemplateBrowser
              templates={INDICATOR_TEMPLATES}
              onSelect={handleTemplateSelect}
            />
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

          {sidePanel === "alphazoo" && (
            <AlphaZooBrowser onSelect={handleAlphaZooSelect} />
          )}

          {sidePanel === "history" && (
            <HistoryPanel indicatorId={selectedId || ""} />
          )}
        </div>

        {/* Strategy config footer */}
        {verifyResult?.strategy_config && Object.keys(verifyResult.strategy_config).length > 0 && (
          <div className="border-t p-4 shrink-0 bg-muted/20">
            <div className="text-xs font-semibold text-muted-foreground mb-2 uppercase tracking-wider">{t.indicatorLabStrategyConfig}</div>
            <div className="grid grid-cols-2 gap-2">
              {Object.entries(verifyResult.strategy_config).map(([key, val]) => (
                <div key={key} className="text-xs">
                  <span className="text-muted-foreground">{key}</span>
                  <span className="ml-1.5 font-mono text-foreground font-medium">{String(val)}</span>
                </div>
              ))}
            </div>
          </div>
        )}
        </>
        )}
      </aside>

    </div>
  );
}
