import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import {
  Code, Save, Trash2, Plus, Target, Play, CheckSquare,
  Square, Layers, Clock, X, ChevronsRight, ChevronsLeft,
  FlaskConical,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n";
import { authHeaders } from "@/lib/apiAuth";
import { request } from "@/lib/api";
import { createApiFetch } from "@/lib/apiFetch";
import { CodeEditor } from "@/components/indicator-lab/CodeEditor";
import { ChartPanel } from "@/components/indicator-lab/ChartPanel";
import { AiChatPanel } from "@/components/indicator-lab/AiChatPanel";
import { VisualBuilder } from "@/components/indicator-lab/VisualBuilder";
import { TemplateBrowser, type TemplateItem } from "@/components/indicator-lab/TemplateBrowser";
import { StrategyVerifyPanel } from "@/components/indicator-lab/StrategyVerifyPanel";
import { OptimizationPanel } from "@/components/trading/OptimizationPanel";
import type { QualityHint } from "@/components/indicator-lab/types";
import { useBacktest } from "@/hooks/useBacktest";

const API_BASE = "/v1/strategy-lab";
const apiFetch = createApiFetch(API_BASE);

const DEFAULT_CODE = `"""
多因子信号引擎 — 由策略实验室生成。

合约约定：
  class SignalEngine:
      def generate(self, data_map: dict[str, pd.DataFrame]) -> dict[str, pd.Series]:
          ...
          return signal_map  # 取值 [-1, 1]，正数=做多，负数=做空

data_map 的键为标的代码，值为 OHLCV DataFrame，包含以下列：
open, high, low, close, volume。索引为 DatetimeIndex，名称为 "trade_date"。
"""

import pandas as pd
import numpy as np
from typing import Dict


class SignalEngine:
    """横截面动量策略。"""

    def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
        signal_map: Dict[str, pd.Series] = {}

        for code, df in data_map.items():
            if len(df) < 20:
                continue
            returns = df["close"].pct_change(5).iloc[-1]
            signal = pd.Series(0.0, index=df.index)
            if returns > 0:
                signal.iloc[-1] = 0.5   # 做多 50%
            else:
                signal.iloc[-1] = -0.5  # 做空 50%
            signal_map[code] = signal

        return signal_map
`;

interface StrategyInfo {
  id: string;
  name: string;
  description: string;
  param_count: number;
  created_at: string;
  updated_at: string;
}

interface BacktestHistoryEntry {
  id: string;
  symbols: string;
  startDate: string;
  endDate: string;
  runId: string;
  timestamp: string;
}

// ── Templates embedded ────────────────────────────────────────────────────────

const STRATEGY_TEMPLATES: TemplateItem[] = [
  {
    key: "ma_crossover",
    name: "Dual MA Crossover",
    description: "Classic dual moving average crossover — go long on golden cross, short on death cross.",
    category: "trend",
    difficulty: "beginner",
    tags: ["MA", "crossover", "trend"],
  },
  {
    key: "macd_trend",
    name: "MACD Trend Following",
    description: "MACD line vs signal line crossover with histogram confirmation for trend entries.",
    category: "trend",
    difficulty: "beginner",
    tags: ["MACD", "trend", "momentum"],
  },
  {
    key: "supertrend",
    name: "SuperTrend ATR",
    description: "ATR-based trailing stop strategy — flip long/short when price crosses the SuperTrend band.",
    category: "trend",
    difficulty: "intermediate",
    tags: ["ATR", "trailing", "trend"],
  },
  {
    key: "rsi_reversal",
    name: "RSI Mean Reversion",
    description: "Buy when RSI drops below oversold threshold, sell when above overbought. Classic mean reversion.",
    category: "reversal",
    difficulty: "beginner",
    tags: ["RSI", "mean-reversion", "oscillator"],
  },
  {
    key: "bollinger_reversal",
    name: "Bollinger Band Reversal",
    description: "Fade extremes — go long at lower band, short at upper band with volatility-adjusted sizing.",
    category: "reversal",
    difficulty: "beginner",
    tags: ["Bollinger", "mean-reversion", "volatility"],
  },
  {
    key: "kdj_extreme",
    name: "KDJ Extreme Zones",
    description: "KDJ indicator overbought/oversold strategy with golden/death cross confirmation.",
    category: "reversal",
    difficulty: "intermediate",
    tags: ["KDJ", "oscillator", "extreme"],
  },
  {
    key: "grid_trading",
    name: "Grid Trading",
    description: "Place buy/sell orders at predetermined price intervals — profit from sideways chop.",
    category: "grid",
    difficulty: "intermediate",
    tags: ["grid", "range", "automation"],
  },
  {
    key: "pair_arbitrage",
    name: "Pairs Trading",
    description: "Statistical arbitrage — trade the spread between two correlated assets when it deviates.",
    category: "arbitrage",
    difficulty: "advanced",
    tags: ["pairs", "spread", "cointegration"],
  },
  {
    key: "multi_factor_momentum",
    name: "Multi-Factor Momentum",
    description: "Combine momentum, volatility, and volume factors with IC-weighted signal blending.",
    category: "multiFactor",
    difficulty: "advanced",
    tags: ["multi-factor", "momentum", "IC"],
  },
  {
    key: "risk_parity",
    name: "Risk Parity Portfolio",
    description: "Allocate capital inversely proportional to asset volatility — equal risk contribution.",
    category: "multiFactor",
    difficulty: "advanced",
    tags: ["risk-parity", "portfolio", "allocation"],
  },
];

const TEMPLATE_CODE_MAP: Record<string, string> = {
  ma_crossover: `"""
Dual MA Crossover Signal Engine.
"""
import pandas as pd
import numpy as np
from typing import Dict


class SignalEngine:
    """Dual moving average crossover strategy."""

    def __init__(self):
        self.fast = 10
        self.slow = 30

    def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
        signal_map: Dict[str, pd.Series] = {}

        for code, df in data_map.items():
            if len(df) < self.slow:
                continue
            fast_ma = df["close"].rolling(self.fast).mean()
            slow_ma = df["close"].rolling(self.slow).mean()
            signal = pd.Series(0.0, index=df.index)
            # Golden cross → long
            golden = (fast_ma > slow_ma) & (fast_ma.shift(1) <= slow_ma.shift(1))
            death = (fast_ma < slow_ma) & (fast_ma.shift(1) >= slow_ma.shift(1))
            signal[golden.fillna(False)] = 1.0
            signal[death.fillna(False)] = -1.0
            signal_map[code] = signal

        return signal_map
`,
  macd_trend: `"""
MACD Trend Following Signal Engine.
"""
import pandas as pd
import numpy as np
from typing import Dict


class SignalEngine:
    """MACD crossover with histogram confirmation."""

    def __init__(self):
        self.fast = 12
        self.slow = 26
        self.signal_period = 9

    def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
        signal_map: Dict[str, pd.Series] = {}

        for code, df in data_map.items():
            if len(df) < self.slow + self.signal_period:
                continue
            ema_fast = df["close"].ewm(span=self.fast, adjust=False).mean()
            ema_slow = df["close"].ewm(span=self.slow, adjust=False).mean()
            macd = ema_fast - ema_slow
            signal_line = macd.ewm(span=self.signal_period, adjust=False).mean()
            histogram = macd - signal_line

            sig = pd.Series(0.0, index=df.index)
            cross_up = (macd > signal_line) & (macd.shift(1) <= signal_line.shift(1))
            cross_down = (macd < signal_line) & (macd.shift(1) >= signal_line.shift(1))
            sig[cross_up.fillna(False) & (histogram > 0)] = 1.0
            sig[cross_down.fillna(False) & (histogram < 0)] = -1.0
            signal_map[code] = sig

        return signal_map
`,
  rsi_reversal: `"""
RSI Mean Reversion Signal Engine.
"""
import pandas as pd
import numpy as np
from typing import Dict


class SignalEngine:
    """RSI oversold/overbought mean reversion."""

    def __init__(self):
        self.period = 14
        self.oversold = 30
        self.overbought = 70

    def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
        signal_map: Dict[str, pd.Series] = {}

        for code, df in data_map.items():
            if len(df) < self.period:
                continue
            delta = df["close"].diff()
            gain = delta.where(delta > 0, 0.0)
            loss = (-delta).where(delta < 0, 0.0)
            avg_gain = gain.rolling(self.period).mean()
            avg_loss = loss.rolling(self.period).mean()
            rs = avg_gain / avg_loss.replace(0, np.nan)
            rsi = 100.0 - (100.0 / (1.0 + rs))

            sig = pd.Series(0.0, index=df.index)
            sig[rsi < self.oversold] = 0.8
            sig[rsi > self.overbought] = -0.8
            signal_map[code] = sig

        return signal_map
`,
  bollinger_reversal: `"""
Bollinger Band Mean Reversion Signal Engine.
"""
import pandas as pd
import numpy as np
from typing import Dict


class SignalEngine:
    """Fade Bollinger Band extremes."""

    def __init__(self):
        self.period = 20
        self.std_dev = 2.0

    def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
        signal_map: Dict[str, pd.Series] = {}

        for code, df in data_map.items():
            if len(df) < self.period:
                continue
            mid = df["close"].rolling(self.period).mean()
            std = df["close"].rolling(self.period).std()
            upper = mid + self.std_dev * std
            lower = mid - self.std_dev * std

            sig = pd.Series(0.0, index=df.index)
            below = df["close"] < lower
            above = df["close"] > upper
            sig[below.fillna(False)] = 0.6
            sig[above.fillna(False)] = -0.6
            signal_map[code] = sig

        return signal_map
`,
  grid_trading: `"""
Grid Trading Signal Engine — places orders at fixed price intervals.
"""
import pandas as pd
import numpy as np
from typing import Dict


class SignalEngine:
    """Grid trading strategy for sideways markets."""

    def __init__(self):
        self.grid_levels = 5
        self.grid_spacing_pct = 0.02  # 2% between grid lines

    def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
        signal_map: Dict[str, pd.Series] = {}

        for code, df in data_map.items():
            if len(df) < 50:
                continue
            mid_price = df["close"].iloc[-1]
            sig = pd.Series(0.0, index=df.index)
            current = df["close"].iloc[-1]

            for i in range(1, self.grid_levels + 1):
                buy_price = mid_price * (1 - self.grid_spacing_pct * i)
                sell_price = mid_price * (1 + self.grid_spacing_pct * i)
                if current <= buy_price:
                    sig.iloc[-1] = min(1.0, sig.iloc[-1] + 0.2)
                if current >= sell_price:
                    sig.iloc[-1] = max(-1.0, sig.iloc[-1] - 0.2)

            signal_map[code] = sig

        return signal_map
`,
  pair_arbitrage: `"""
Pairs Trading Signal Engine — trade cointegrated spread.
"""
import pandas as pd
import numpy as np
from typing import Dict


class SignalEngine:
    """Statistical arbitrage via z-score on pair spread."""

    def __init__(self):
        self.lookback = 60
        self.entry_z = 2.0
        self.exit_z = 0.5

    def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
        signal_map: Dict[str, pd.Series] = {}
        codes = list(data_map.keys())
        if len(codes) < 2:
            return signal_map

        a, b = codes[0], codes[1]
        df_a = data_map[a]
        df_b = data_map[b]
        common_len = min(len(df_a), len(df_b))
        if common_len < self.lookback:
            return signal_map

        spread = df_a["close"].iloc[-common_len:] - df_b["close"].iloc[-common_len:]
        z_score = (spread - spread.rolling(self.lookback).mean()) / spread.rolling(self.lookback).std()

        sig_a = pd.Series(0.0, index=df_a.index)
        sig_b = pd.Series(0.0, index=df_b.index)

        if abs(z_score.iloc[-1]) > self.entry_z:
            if z_score.iloc[-1] > 0:
                sig_a.iloc[-1] = -0.5
                sig_b.iloc[-1] = 0.5
            else:
                sig_a.iloc[-1] = 0.5
                sig_b.iloc[-1] = -0.5

        signal_map[a] = sig_a
        signal_map[b] = sig_b
        return signal_map
`,
  multi_factor_momentum: `"""
Multi-Factor Momentum Signal Engine — IC-weighted factor blend.
"""
import pandas as pd
import numpy as np
from typing import Dict


class SignalEngine:
    """Combine momentum, volatility, and volume factors."""

    def __init__(self):
        self.mom_period = 20
        self.vol_period = 20
        self.vol_period_short = 60

    def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
        signal_map: Dict[str, pd.Series] = {}

        for code, df in data_map.items():
            if len(df) < self.vol_period_short:
                continue

            mom = df["close"].pct_change(self.mom_period).iloc[-1]
            mom_signal = np.clip(mom * 5, -1, 1)

            returns = df["close"].pct_change().dropna()
            recent_vol = returns.iloc[-self.vol_period:].std()
            hist_vol = returns.iloc[-self.vol_period_short:].std()
            vol_signal = np.clip((hist_vol - recent_vol) / hist_vol, -1, 1) if hist_vol > 0 else 0

            avg_vol = df["volume"].iloc[-self.vol_period_short:].mean()
            recent_vol_amt = df["volume"].iloc[-5:].mean()
            vol_ratio = recent_vol_amt / avg_vol if avg_vol > 0 else 1
            vol_signal_amt = np.clip((vol_ratio - 1) * np.sign(mom), -1, 1)

            composite = (0.4 * mom_signal + 0.3 * vol_signal + 0.3 * vol_signal_amt)
            sig = pd.Series(0.0, index=df.index)
            sig.iloc[-1] = composite
            signal_map[code] = sig

        return signal_map
`,
  risk_parity: `"""
Risk Parity Signal Engine — inverse-volatility allocation.
"""
import pandas as pd
import numpy as np
from typing import Dict


class SignalEngine:
    """Allocate capital inversely proportional to each asset's volatility."""

    def __init__(self):
        self.vol_lookback = 60
        self.target_vol = 0.15  # 15% annualized

    def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
        signal_map: Dict[str, pd.Series] = {}
        vols: Dict[str, float] = {}

        for code, df in data_map.items():
            if len(df) < self.vol_lookback:
                continue
            returns = df["close"].pct_change().dropna().iloc[-self.vol_lookback:]
            vols[code] = returns.std() * np.sqrt(252)

        if not vols:
            return signal_map

        inv_vol_sum = sum(1.0 / max(v, 0.01) for v in vols.values())
        for code, vol in vols.items():
            df = data_map[code]
            weight = (1.0 / max(vol, 0.01)) / inv_vol_sum if inv_vol_sum > 0 else 0
            weight = weight * (self.target_vol / vol) if vol > 0 else weight
            weight = np.clip(weight, -1.0, 1.0)
            sig = pd.Series(weight, index=df.index)
            signal_map[code] = sig

        return signal_map
`,
};

const KDJ_TEMPLATE_CODE = `"""
KDJ Extreme Zones Signal Engine.
"""
import pandas as pd
import numpy as np
from typing import Dict


class SignalEngine:
    """KDJ overbought/oversold with golden/death cross confirmation."""

    def __init__(self):
        self.period = 9
        self.signal_period = 3

    def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
        signal_map: Dict[str, pd.Series] = {}

        for code, df in data_map.items():
            if len(df) < self.period + self.signal_period:
                continue
            low_min = df["low"].rolling(self.period).min()
            high_max = df["high"].rolling(self.period).max()
            rsv = ((df["close"] - low_min) / (high_max - low_min).replace(0, np.nan)) * 100
            k = rsv.ewm(span=self.signal_period, adjust=False).mean()
            d = k.ewm(span=self.signal_period, adjust=False).mean()

            sig = pd.Series(0.0, index=df.index)
            gold_cross = (k > d) & (k.shift(1) <= d.shift(1))
            death_cross = (k < d) & (k.shift(1) >= d.shift(1))
            sig[(k < 20) & gold_cross.fillna(False)] = 0.7
            sig[(k > 80) & death_cross.fillna(False)] = -0.7
            signal_map[code] = sig

        return signal_map
`;

const SUPERTREND_TEMPLATE_CODE = `"""
SuperTrend ATR Signal Engine.
"""
import pandas as pd
import numpy as np
from typing import Dict


class SignalEngine:
    """ATR-based SuperTrend — flip direction on band cross."""

    def __init__(self):
        self.atr_period = 10
        self.multiplier = 3.0

    def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
        signal_map: Dict[str, pd.Series] = {}

        for code, df in data_map.items():
            if len(df) < self.atr_period + 1:
                continue
            cl = df["close"]
            hi = df["high"]
            lo = df["low"]
            prev_cl = cl.shift(1)
            tr = pd.concat([hi - lo, (hi - prev_cl).abs(), (lo - prev_cl).abs()], axis=1).max(axis=1)
            atr = tr.ewm(alpha=1.0 / self.atr_period, adjust=False).mean()
            hl2 = (hi + lo) / 2
            upper = hl2 + self.multiplier * atr
            lower = hl2 - self.multiplier * atr

            trend = pd.Series(1.0, index=df.index)
            for i in range(1, len(df)):
                if cl.iloc[i] > upper.iloc[i - 1]:
                    trend.iloc[i] = 1.0
                elif cl.iloc[i] < lower.iloc[i - 1]:
                    trend.iloc[i] = -1.0
                else:
                    trend.iloc[i] = trend.iloc[i - 1]

            sig = pd.Series(0.0, index=df.index)
            sig[(trend == 1.0) & (trend.shift(1) == -1.0)] = 1.0
            sig[(trend == -1.0) & (trend.shift(1) == 1.0)] = -1.0
            signal_map[code] = sig

        return signal_map
`;

const ALL_TEMPLATE_CODES: Record<string, string> = {
  ...TEMPLATE_CODE_MAP,
  kdj_extreme: KDJ_TEMPLATE_CODE,
  supertrend: SUPERTREND_TEMPLATE_CODE,
};

// ── Backtest history (localStorage) ───────────────────────────────────────────

const HISTORY_KEY = "strategy-lab-backtest-history";

function loadBacktestHistory(): BacktestHistoryEntry[] {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

// ── Page Component ────────────────────────────────────────────────────────────

type SidePanelTab = "list" | "templates" | "history" | "optimize";

export function StrategyLab() {
  const { t } = useI18n();
  const [code, setCode] = useState(DEFAULT_CODE);
  const [strategies, setStrategies] = useState<StrategyInfo[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [aiChatVisible, setAiChatVisible] = useState(false);
  const [customModeOpen, setCustomModeOpen] = useState(false);
  const [verifyResult, setVerifyResult] = useState<{
    success: boolean;
    error: string | null;
    quality_hints: QualityHint[];
    params: { name: string; type: string; default: unknown; description: string }[];
    has_generate_method: boolean;
    has_signal_map_return: boolean;
    symbol_count: number;
  } | null>(null);
  const [sidePanel, setSidePanel] = useState<SidePanelTab>("list");
  const [rightCollapsed, setRightCollapsed] = useState(() => {
    return localStorage.getItem("strategy-lab-sidebar-collapsed") === "true";
  });

  const handleToggleSidebar = () => {
    setRightCollapsed((prev) => {
      const next = !prev;
      localStorage.setItem("strategy-lab-sidebar-collapsed", String(next));
      return next;
    });
  };

  // Batch selection
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // Preserve sidebar scroll position across re-renders
  const sidebarScrollRef = useRef<HTMLDivElement>(null);
  const sidebarScrollTopRef = useRef(0);
  useLayoutEffect(() => {
    const el = sidebarScrollRef.current;
    if (el) el.scrollTop = sidebarScrollTopRef.current;
  });
  const saveSidebarScroll = () => {
    const el = sidebarScrollRef.current;
    if (el) sidebarScrollTopRef.current = el.scrollTop;
  };

  // Backtest history (loaded from localStorage)
  const [backtestHistory] = useState<BacktestHistoryEntry[]>(loadBacktestHistory);

  // ── Chart state ─────────────────────────────────────────────────────────────

  const [chartSymbols, setChartSymbols] = useState("");
  const [chartStartDate, setChartStartDate] = useState("2024-01-01");
  const [chartEndDate, setChartEndDate] = useState("2025-12-31");
  const [chartSource, setChartSource] = useState("auto");
  const [chartInterval, setChartInterval] = useState("1D");
  const [initialCash, setInitialCash] = useState(100000);
  const [slippage, setSlippage] = useState(0.1);
  const [slippageMode, setSlippageMode] = useState<"fixed" | "volume">("fixed");
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

  // AI generation abort controller
  const aiAbortRef = useRef<AbortController | null>(null);

  // ── Data loading ──────────────────────────────────────────────────────────

  const loadList = useCallback(async () => {
    try {
      const data = await apiFetch<{ strategies: StrategyInfo[] }>("/list");
      setStrategies(data.strategies);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    loadList();
  }, [loadList]);

  useEffect(() => {
    if (!selectedId) return;
    apiFetch<{ code: string }>(`/${selectedId}`)
      .then((data) => {
        setCode(data.code);
        setMessage(null);
      })
      .catch(() => setMessage("Failed to load strategy"));
  }, [selectedId]);

  useEffect(() => {
    return () => {
      clearPolling();
      if (aiAbortRef.current) aiAbortRef.current.abort();
    };
  }, [clearPolling]);

  // ── Save ──────────────────────────────────────────────────────────────────

  const handleSave = async () => {
    setSaving(true);
    setMessage(null);
    try {
      const data = await apiFetch<StrategyInfo>("/save", {
        method: "POST",
        body: JSON.stringify({ code, strategy_id: selectedId || undefined }),
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

  // ── Verify ────────────────────────────────────────────────────────────────

  const handleVerify = async () => {
    setVerifying(true);
    setMessage(null);
    try {
      const result = await apiFetch<StrategyVerifyResult>("/verify", {
        method: "POST",
        body: JSON.stringify({ code }),
      });
      setVerifyResult(result);
      if (result.success) {
        setMessage("Verification passed");
      } else {
        setMessage(`Verification failed: ${result.error}`);
      }
    } catch (e) {
      setMessage(String(e));
      setVerifyResult({
        success: false,
        error: String(e),
        quality_hints: [],
        params: [],
        has_generate_method: false,
        has_signal_map_return: false,
        symbol_count: 0,
      });
    } finally {
      setVerifying(false);
    }
  };

  // ── AI Generate ───────────────────────────────────────────────────────────

  const handleGenerate = async (prompt: string) => {
    setGenerating(true);
    setMessage(null);
    const controller = new AbortController();
    aiAbortRef.current = controller;
    let streamed = "";
    try {
      const res = await fetch(`${API_BASE}/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() as Record<string, string> },
        body: JSON.stringify({ prompt, style: "custom" }),
        signal: controller.signal,
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
              streamed += evt.content;
              setCode(streamed);
            } else if (evt.type === "done") {
              setMessage(t.aiChatSend + " " + "complete");
              // Auto-save to sync sidebar list
              try {
                const data = await apiFetch<StrategyInfo>("/save", {
                  method: "POST",
                  body: JSON.stringify({ code: streamed }),
                });
                setSelectedId(data.id);
                setChartTitle(data.name);
                loadList();
              } catch { /* save failure is non-fatal */ }
            } else if (evt.type === "error") {
              setMessage(`Generation error: ${evt.message}`);
            }
          } catch {
            /* ignore parse errors */
          }
        }
      }
    } catch (e: unknown) {
      if (e instanceof DOMException && e.name === "AbortError") {
        setMessage("Generation cancelled");
      } else {
        setMessage(String(e));
      }
    } finally {
      setGenerating(false);
      aiAbortRef.current = null;
    }
  };

  const handleCancelGenerate = () => {
    if (aiAbortRef.current) aiAbortRef.current.abort();
  };

  // ── Chart data fetch ───────────────────────────────────────────────────────

  const handleFetchOHLCV = useCallback(async () => {
    await fetchOHLCV(chartSymbols, chartStartDate, chartEndDate, chartSource, chartInterval);
  }, [fetchOHLCV, chartSymbols, chartStartDate, chartEndDate, chartSource, chartInterval]);

  // ── Run backtest + poll ────────────────────────────────────────────────────

  const handleRunBacktest = useCallback(async () => {
    const codes = chartSymbols.split(",").map((s) => s.trim()).filter(Boolean);
    if (!codes.length) return;

    await runBacktest(async () => {
      const data = await request<{ success: boolean; run_id?: string; error?: string }>("/strategy-lab/backtest", {
        method: "POST",
        body: JSON.stringify({
          code,
          codes,
          start_date: chartStartDate,
          end_date: chartEndDate,
          source: chartSource,
          interval: chartInterval,
          initial_cash: initialCash,
          slippage: slippage / 100,  // % → decimal
          slippage_mode: slippageMode,
          benchmark: "auto",
        }),
      });
      if (!data.success || !data.run_id) throw new Error(data.error || "Backtest failed");
      return data.run_id;
    });

    // Save to backtest history
    try {
      const raw = localStorage.getItem(HISTORY_KEY);
      const history: BacktestHistoryEntry[] = raw ? JSON.parse(raw) : [];
      history.unshift({
        id: Date.now().toString(),
        runId: Date.now().toString(),
        symbols: codes.join(", "),
        startDate: chartStartDate,
        endDate: chartEndDate,
        timestamp: new Date().toISOString(),
      });
      localStorage.setItem(HISTORY_KEY, JSON.stringify(history.slice(0, 50)));
    } catch { /* ignore */ }
  }, [code, chartSymbols, chartStartDate, chartEndDate, chartSource, chartInterval, initialCash, runBacktest]);

  // ── Delete / Batch ────────────────────────────────────────────────────────

  const handleDelete = async (id: string) => {
    try {
      await apiFetch(`/delete/${id}`, { method: "POST" });
      if (selectedId === id) setSelectedId(null);
      setSelectedIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
      loadList();
      setMessage("Strategy deleted");
    } catch (e) {
      setMessage(String(e));
    }
  };

  const handleBatchDelete = async () => {
    if (!confirm(`确定要删除选中的 ${selectedIds.size} 个策略吗？此操作不可恢复。`)) return;
    for (const id of selectedIds) {
      try {
        await apiFetch(`/delete/${id}`, { method: "POST" });
        if (selectedId === id) setSelectedId(null);
      } catch {
        /* continue */
      }
    }
    setSelectedIds(new Set());
    loadList();
    setMessage(`${selectedIds.size} strategies deleted`);
  };

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectAll = () => setSelectedIds(new Set(strategies.map((s) => s.id)));
  const deselectAll = () => setSelectedIds(new Set());

  // ── Template select ───────────────────────────────────────────────────────

  const handleTemplateSelect = (template: TemplateItem) => {
    const templateCode = ALL_TEMPLATE_CODES[template.key];
    if (templateCode) {
      setCode(templateCode);
      setChartTitle(template.name);
      setMessage(`Loaded template: ${template.name}`);
      setSidePanel("list");
    }
  };

  // ── New ───────────────────────────────────────────────────────────────────

  const handleNew = () => {
    setCode(DEFAULT_CODE);
    setSelectedId(null);
    setChartTitle("");
    setVerifyResult(null);
    setMessage(null);
  };

  // ── Derived ───────────────────────────────────────────────────────────────

  const isError = message && (message.includes("failed") || message.includes("error"));

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="flex h-[calc(100vh-3rem)] gap-3 p-3">
      {/* Main editor area */}
      <div className="flex-1 flex flex-col min-w-0 min-w-[320px] gap-3">
        {/* Header */}
        <div className="page-header">
          <div className="page-header-title">
            <div className="h-7 w-7 rounded-lg bg-primary/10 flex items-center justify-center">
              <Target className="h-4 w-4 text-primary" />
            </div>
            <div>
              <h1>{t.strategyLab || "Strategy Lab"}</h1>
              <p className="page-header-desc">{t.strategyLabPageDesc}</p>
            </div>
          </div>
          <div className="page-header-actions">
            <button onClick={handleNew} className="btn-sm btn-ghost">
              <Plus className="h-3.5 w-3.5" />
              {t.indicatorLabNew}
            </button>
            <button onClick={() => setCustomModeOpen(true)} className="btn-sm btn-outline">
              <Layers className="h-3.5 w-3.5" />
              {t.customMode}
            </button>
            <button onClick={handleVerify} disabled={verifying} className="btn-sm btn-warning">
              <Play className="h-3.5 w-3.5" />
              {verifying ? t.strategyLabVerifying : t.strategyLabVerify}
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

        {/* Contract hint */}
        <div className="shrink-0 mx-0 px-4 py-2 text-xs text-muted-foreground bg-muted/40 rounded-xl border border-border/50">
          <strong className="font-semibold text-foreground">SignalEngine</strong>
          <span className="mx-1.5 text-muted-foreground/40">—</span>
          <code className="bg-muted px-1.5 py-0.5 rounded text-xs">
            generate(self, data_map) → dict[str, pd.Series]
          </code>
          <span className="ml-1.5">返回 signal_map，取值 [-1, 1]，正=做多，负=做空</span>
        </div>

        {/* Verify result inline display */}
        {verifyResult && (
          <div className="shrink-0 border border-border rounded-2xl bg-card shadow-sm max-h-60 overflow-auto animate-scale-in">
            <div className="flex items-center justify-between px-4 py-2.5 bg-muted/30 rounded-t-2xl">
              <span className="text-sm font-medium">Verification Results</span>
              <button
                onClick={() => setVerifyResult(null)}
                className="btn-ghost p-1 rounded-md"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
            <div className="p-4">
              <StrategyVerifyPanel result={verifyResult} />
            </div>
          </div>
        )}

        {/* Editor */}
        <div className="flex-1 min-h-0 section-card">
          <CodeEditor value={code} onChange={setCode} onSave={handleSave} filename="strategy.py" mode="strategy" />
        </div>

        {/* AI Chat panel */}
        <AiChatPanel
          visible={aiChatVisible}
          onToggle={() => setAiChatVisible(!aiChatVisible)}
          generating={generating}
          onGenerate={handleGenerate}
          onCancel={handleCancelGenerate}
        />
      </div>

      {/* Chart panel */}
      <div className="flex-1 flex flex-col min-w-0 min-w-[380px] section-card">
        <ChartPanel
          symbol={chartSymbols}
          onSymbolChange={setChartSymbols}
          multiSymbol
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
          slippage={slippage}
          onSlippageChange={setSlippage}
          slippageMode={slippageMode}
          onSlippageModeChange={setSlippageMode}
        />
      </div>

      {/* Right sidebar */}
      <aside className={cn(
        "section-card shrink-0 transition-all duration-200",
        rightCollapsed ? "w-10" : "w-80"
      )}>
        {/* Collapse toggle */}
        <div className={cn("flex items-center rounded-t-2xl bg-muted/30", rightCollapsed ? "justify-center py-2" : "justify-end px-2 py-1")}>
          <button
            onClick={handleToggleSidebar}
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
            ["list", t.indicatorLabList, Code],
            ["templates", t.strategyLabTemplates, Layers],
            ["history", t.strategyLabHistory, Clock],
            ["optimize", t.tradingOptimize || "优化", FlaskConical],
          ] as const).map(([key, label, Icon]) => (
            <button
              key={key}
              onClick={() => setSidePanel(key)}
              className={cn("tab-item relative", sidePanel === key && "active")}
            >
              <Icon className="h-3.5 w-3.5" />
              {label}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-auto p-4" ref={sidebarScrollRef} onScroll={saveSidebarScroll}>
          {/* ── List tab ────────────────────────────────────────────────── */}
          {sidePanel === "list" && (
            <div className="space-y-1">
              {/* Batch toolbar */}
              {strategies.length > 0 && (
                <div className="flex items-center justify-between pb-3 mb-2 border-b border-border">
                  <div className="flex items-center gap-2">
                    <button onClick={selectAll} className="text-xs text-muted-foreground hover:text-foreground transition-colors">
                      {t.strategyLabSelectAll}
                    </button>
                    <button onClick={deselectAll} className="text-xs text-muted-foreground hover:text-foreground transition-colors">
                      {t.strategyLabDeselectAll}
                    </button>
                  </div>
                  {selectedIds.size > 0 && (
                    <button onClick={handleBatchDelete} className="btn-sm btn-danger">
                      <Trash2 className="h-3.5 w-3.5" />
                      {t.strategyLabBatchDelete} ({selectedIds.size})
                    </button>
                  )}
                </div>
              )}

              {strategies.length === 0 && (
                <div className="empty-state">
                  <Code className="empty-state-icon" />
                  <p className="empty-state-text">{t.strategyLabNoStrategies}</p>
                  <p className="empty-state-hint">{t.strategyLabNoStrategiesHint}</p>
                </div>
              )}

              {strategies.map((s) => (
                <div
                  key={s.id}
                  className={cn(
                    "flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm cursor-pointer transition-all duration-150 group",
                    selectedId === s.id
                      ? "bg-primary/10 text-primary font-medium shadow-sm"
                      : "hover:bg-muted text-muted-foreground hover:text-foreground"
                  )}
                >
                  {/* Checkbox */}
                  <button
                    onClick={(e) => { e.stopPropagation(); toggleSelect(s.id); }}
                    className="shrink-0 text-muted-foreground hover:text-primary transition-colors"
                  >
                    {selectedIds.has(s.id) ? (
                      <CheckSquare className="h-4 w-4 text-primary" />
                    ) : (
                      <Square className="h-4 w-4" />
                    )}
                  </button>

                  {/* Content */}
                  <div className="min-w-0 flex-1" onClick={() => { setSelectedId(s.id); setChartTitle(s.name); }}>
                    <div className="truncate font-medium">{s.name}</div>
                    <div className="flex items-center gap-2 text-xs opacity-60 mt-0.5">
                      <span>{s.param_count} params</span>
                      <span>{s.created_at?.slice(0, 10)}</span>
                    </div>
                  </div>

                  {/* Actions */}
                  <button
                    onClick={(e) => { e.stopPropagation(); handleDelete(s.id); }}
                    className="p-1.5 opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-danger rounded-md transition-all shrink-0"
                    title="Delete"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* ── Templates tab ───────────────────────────────────────────── */}
          {sidePanel === "templates" && (
            <TemplateBrowser
              templates={STRATEGY_TEMPLATES}
              onSelect={handleTemplateSelect}
            />
          )}

          {/* ── History tab ─────────────────────────────────────────────── */}
          {sidePanel === "history" && (
            <div className="space-y-2">
              {backtestHistory.length === 0 ? (
                <div className="empty-state">
                  <Clock className="empty-state-icon" />
                  <p className="empty-state-text">{t.strategyLabNoBacktests}</p>
                </div>
              ) : (
                backtestHistory.map((entry) => (
                  <div
                    key={entry.id}
                    className="card p-3.5 hover:border-primary/20 transition-colors"
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-sm font-medium font-mono truncate">
                        {entry.symbols}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {entry.timestamp?.slice(0, 16).replace("T", " ")}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <span>{entry.startDate} → {entry.endDate}</span>
                    </div>
                    <div className="text-xs font-mono text-muted-foreground mt-1.5">
                      Run: {entry.runId?.slice(0, 8)}
                    </div>
                  </div>
                ))
              )}
            </div>
          )}

          {/* ── Optimize tab ──────────────────────────────────────────────── */}
          {sidePanel === "optimize" && (
            <div className="space-y-3">
              <p className="text-xs text-muted-foreground">
                对策略参数进行网格搜索、随机搜索或贝叶斯优化，找到最优参数组合。
              </p>
              <OptimizationPanel symbol={chartSymbols.split(/[,;\s]+/).filter(Boolean)[0]?.trim() || ""} />
            </div>
          )}

        </div>
        </>
        )}
      </aside>

      {/* Custom mode modal */}
      {customModeOpen && (
        <VisualBuilder
          mode="strategy"
          onClose={() => setCustomModeOpen(false)}
          onCodeGenerated={(code, name) => {
            setCode(code);
            setChartTitle(name);
            handleSave();
          }}
        />
      )}

    </div>
  );
}

interface StrategyVerifyResult {
  success: boolean;
  error: string | null;
  quality_hints: QualityHint[];
  params: { name: string; type: string; default: unknown; description: string }[];
  has_generate_method: boolean;
  has_signal_map_return: boolean;
  symbol_count: number;
}
