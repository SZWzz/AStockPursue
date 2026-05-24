"""Generate indicator code from strategy templates.

Each template has default params; the generator produces a complete
indicator script following the QD contract (my_indicator_name,
df['buy']/df['sell'], output dict).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_TEMPLATES_PATH = Path(__file__).parent / "templates.json"


def _build_indicator_code(name: str, desc: str, core_logic: str, plots: str, params_block: str, strategy_block: str, extra_buy_logic: str = "") -> str:
    """Assemble a complete indicator script from parts."""
    return f'''my_indicator_name = "{name}"
my_indicator_description = "{desc}"
{strategy_block}
{params_block}
df = df.copy()

{core_logic}

# === Signals ===
df["buy"] = False
df["sell"] = False
{extra_buy_logic}

output = {{
    "name": my_indicator_name,
    "plots": [
        {plots}
    ],
    "signals": [
        {{"type": "buy", "text": "Buy", "data": get_marks(df["buy"]), "color": "#4CAF50"}},
        {{"type": "sell", "text": "Sell", "data": get_marks(df["sell"]), "color": "#F44336"}},
    ],
}}

# Helper: convert boolean Series to marker list (price or None)
def get_marks(signal, price_col=None):
    import numpy as np
    if price_col is None:
        price_col = df["close"]
    arr = np.full(len(df), np.nan)
    for i in range(len(df)):
        if signal.iloc[i]:
            arr[i] = price_col.iloc[i]
    return arr.tolist()
'''


# ── Template generators ────────────────────────────────────────────────────


def _generate_ma_crossover(params: dict) -> str:
    fast = params.get("fast_period", 10)
    slow = params.get("slow_period", 30)
    logic = f'''# @param fast_period int {fast} Fast MA period
# @param slow_period int {slow} Slow MA period
# @strategy stopLossPct 0.02
# @strategy takeProfitPct 0.05

fast_period = params.get("fast_period", {fast})
slow_period = params.get("slow_period", {slow})
fast_ma = df["close"].rolling(window=fast_period, min_periods=fast_period).mean()
slow_ma = df["close"].rolling(window=slow_period, min_periods=slow_period).mean()
golden_cross = (fast_ma > slow_ma) & (fast_ma.shift(1) <= slow_ma.shift(1))
death_cross = (fast_ma < slow_ma) & (fast_ma.shift(1) >= slow_ma.shift(1))
df["buy"] = golden_cross.fillna(False)
df["sell"] = death_cross.fillna(False)'''
    plots = '{"name": f"MA{fast_period}", "data": fast_ma.tolist(), "color": "#2196F3", "overlay": True}, {"name": f"MA{slow_period}", "data": slow_ma.tolist(), "color": "#FF9800", "overlay": True}'
    return _build_indicator_code(
        "MA Crossover", f"Dual moving average crossover: fast={fast}, slow={slow}",
        logic, plots, "", ""
    )


def _generate_rsi_oversold(params: dict) -> str:
    period = params.get("period", 14)
    oversold = params.get("oversold", 30)
    overbought = params.get("overbought", 70)
    logic = f'''# @param period int {period} RSI period
# @param oversold int {oversold} Oversold threshold
# @param overbought int {overbought} Overbought threshold
# @strategy stopLossPct 0.02
# @strategy takeProfitPct 0.05

period = params.get("period", {period})
oversold = params.get("oversold", {oversold})
overbought = params.get("overbought", {overbought})
delta = df["close"].diff()
gain = delta.where(delta > 0, 0.0)
loss = (-delta).where(delta < 0, 0.0)
avg_gain = gain.rolling(window=period, min_periods=period).mean()
avg_loss = loss.rolling(window=period, min_periods=period).mean()
rs = avg_gain / avg_loss.replace(0, np.nan)
rsi = 100.0 - (100.0 / (1.0 + rs))
df["buy"] = rsi < oversold
df["sell"] = rsi > overbought'''
    plots = '{"name": "RSI", "data": rsi.tolist(), "color": "#9C27B0", "overlay": False}'
    return _build_indicator_code(
        "RSI Mean Reversion", f"RSI oversold/overbought: period={period}",
        logic, plots, "", ""
    )


def _generate_bollinger_band(params: dict) -> str:
    period = params.get("period", 20)
    std_dev = params.get("std_dev", 2.0)
    logic = f'''# @param period int {period} Bollinger period
# @param std_dev float {std_dev} Standard deviations
# @strategy stopLossPct 0.02
# @strategy takeProfitPct 0.05

period = params.get("period", {period})
std_dev = params.get("std_dev", {std_dev})
mid = df["close"].rolling(window=period, min_periods=period).mean()
std = df["close"].rolling(window=period, min_periods=period).std()
upper = mid + std_dev * std
lower = mid - std_dev * std
df["buy"] = (df["close"] < lower).fillna(False)
df["sell"] = (df["close"] > upper).fillna(False)'''
    plots = '{"name": "Mid", "data": mid.tolist(), "color": "#2196F3", "overlay": True}, {"name": "Upper", "data": upper.tolist(), "color": "#FF9800", "overlay": True}, {"name": "Lower", "data": lower.tolist(), "color": "#FF9800", "overlay": True}'
    return _build_indicator_code(
        "Bollinger Band Mean Reversion", f"Bollinger bands: period={period}, std={std_dev}",
        logic, plots, "", ""
    )


def _generate_macd(params: dict) -> str:
    fast = params.get("fast_period", 12)
    slow = params.get("slow_period", 26)
    sig = params.get("signal_period", 9)
    logic = f'''# @param fast_period int {fast} Fast EMA period
# @param slow_period int {slow} Slow EMA period
# @param signal_period int {sig} Signal EMA period
# @strategy stopLossPct 0.02
# @strategy takeProfitPct 0.05

fast_period = params.get("fast_period", {fast})
slow_period = params.get("slow_period", {slow})
signal_period = params.get("signal_period", {sig})
ema_fast = df["close"].ewm(span=fast_period, adjust=False, min_periods=fast_period).mean()
ema_slow = df["close"].ewm(span=slow_period, adjust=False, min_periods=slow_period).mean()
macd_line = ema_fast - ema_slow
signal_line = macd_line.ewm(span=signal_period, adjust=False, min_periods=signal_period).mean()
histogram = macd_line - signal_line
cross_up = (macd_line > signal_line) & (macd_line.shift(1) <= signal_line.shift(1))
cross_down = (macd_line < signal_line) & (macd_line.shift(1) >= signal_line.shift(1))
df["buy"] = cross_up.fillna(False)
df["sell"] = cross_down.fillna(False)'''
    plots = '{"name": "MACD", "data": macd_line.tolist(), "color": "#2196F3", "overlay": False}, {"name": "Signal", "data": signal_line.tolist(), "color": "#FF9800", "overlay": False}, {"name": "Histogram", "data": histogram.tolist(), "color": "#9C27B0", "overlay": False}'
    return _build_indicator_code(
        "MACD Crossover", f"MACD crossover: fast={fast}, slow={slow}, signal={sig}",
        logic, plots, "", ""
    )


def _generate_kdj(params: dict) -> str:
    period = params.get("period", 9)
    sig = params.get("signal_period", 3)
    logic = f'''# @param period int {period} KDJ period
# @param signal_period int {sig} Signal period
# @strategy stopLossPct 0.02
# @strategy takeProfitPct 0.05

period = params.get("period", {period})
signal_period = params.get("signal_period", {sig})
low_min = df["low"].rolling(window=period, min_periods=period).min()
high_max = df["high"].rolling(window=period, min_periods=period).max()
rsv = ((df["close"] - low_min) / (high_max - low_min).replace(0, np.nan)) * 100
k = rsv.ewm(span=signal_period, adjust=False, min_periods=signal_period).mean()
d = k.ewm(span=signal_period, adjust=False, min_periods=signal_period).mean()
j = 3 * k - 2 * d
gold_cross = (k > d) & (k.shift(1) <= d.shift(1))
death_cross = (k < d) & (k.shift(1) >= d.shift(1))
df["buy"] = (k < 20) & gold_cross.fillna(False)
df["sell"] = (k > 80) & death_cross.fillna(False)'''
    plots = '{"name": "K", "data": k.tolist(), "color": "#2196F3", "overlay": False}, {"name": "D", "data": d.tolist(), "color": "#FF9800", "overlay": False}, {"name": "J", "data": j.tolist(), "color": "#9C27B0", "overlay": False}'
    return _build_indicator_code(
        "KDJ Overbought/Oversold", f"KDJ strategy: period={period}",
        logic, plots, "", ""
    )


def _generate_supertrend(params: dict) -> str:
    period = params.get("atr_period", 10)
    mult = params.get("multiplier", 3.0)
    logic = f'''# @param atr_period int {period} ATR period range=7:21:1
# @param multiplier float {mult} ATR multiplier range=1.5:5.0:0.5
# @strategy stopLossPct 0.04
# @strategy takeProfitPct 0.10

atr_period = params.get("atr_period", {period})
multiplier = params.get("multiplier", {mult})
cl = df["close"]
hi = df["high"]
lo = df["low"]
prev_cl = cl.shift(1)
tr = pd.concat([hi - lo, (hi - prev_cl).abs(), (lo - prev_cl).abs()], axis=1).max(axis=1)
atr = tr.ewm(alpha=1.0 / atr_period, adjust=False, min_periods=atr_period).mean()
hl2 = (hi + lo) / 2
basic_upper = hl2 + multiplier * atr
basic_lower = hl2 - multiplier * atr
final_upper = basic_upper.copy()
final_lower = basic_lower.copy()
# Trailing bands: tighten only (no widening)
for i in range(1, len(df)):
    if cl.iloc[i] <= final_upper.iloc[i - 1] if not pd.isna(final_upper.iloc[i - 1]) else True:
        final_upper.iloc[i] = min(basic_upper.iloc[i], final_upper.iloc[i - 1]) if not pd.isna(final_upper.iloc[i - 1]) else basic_upper.iloc[i]
    if cl.iloc[i] >= final_lower.iloc[i - 1] if not pd.isna(final_lower.iloc[i - 1]) else True:
        final_lower.iloc[i] = max(basic_lower.iloc[i], final_lower.iloc[i - 1]) if not pd.isna(final_lower.iloc[i - 1]) else basic_lower.iloc[i]
trend = pd.Series(0.0, index=df.index)
trend.iloc[0] = 1.0
for i in range(1, len(df)):
    if cl.iloc[i] > final_upper.iloc[i - 1] if not pd.isna(final_upper.iloc[i - 1]) else False:
        trend.iloc[i] = 1.0
    elif cl.iloc[i] < final_lower.iloc[i - 1] if not pd.isna(final_lower.iloc[i - 1]) else False:
        trend.iloc[i] = -1.0
    else:
        trend.iloc[i] = trend.iloc[i - 1]
df["buy"] = (trend == 1.0) & (trend.shift(1) == -1.0)
df["sell"] = (trend == -1.0) & (trend.shift(1) == 1.0)'''
    plots = '{"name": "Upper", "data": final_upper.tolist(), "color": "#F44336", "overlay": True}, {"name": "Lower", "data": final_lower.tolist(), "color": "#4CAF50", "overlay": True}'
    return _build_indicator_code(
        "SuperTrend", f"SuperTrend trend following: ATR={period}, mult={mult}",
        logic, plots, "", ""
    )


# ── Generator registry ─────────────────────────────────────────────────────

_GENERATORS: dict[str, Any] = {
    "ma_crossover": _generate_ma_crossover,
    "rsi_oversold": _generate_rsi_oversold,
    "bollinger_squeeze": _generate_bollinger_band,
    "macd_divergence": _generate_macd,
    "kdj": _generate_kdj,
    "supertrend": _generate_supertrend,
}


# ── Public API ──────────────────────────────────────────────────────────────

def load_templates() -> list[dict[str, Any]]:
    """Load all available strategy templates."""
    if _TEMPLATES_PATH.exists():
        with open(_TEMPLATES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def generate_from_template(template_key: str, params_override: dict[str, Any] | None = None) -> str | None:
    """Generate complete indicator code from a template.

    Args:
        template_key: Template identifier (e.g. "ma_crossover").
        params_override: Optional parameter overrides.

    Returns:
        Full Python indicator source code, or None if template unknown.
    """
    templates = load_templates()
    template = next((t for t in templates if t.get("key") == template_key), None)
    if template is None:
        logger.warning(f"Template not found: {template_key}")
        return None

    params = {**template.get("default_params", {})}
    if params_override:
        params.update(params_override)

    generator = _GENERATORS.get(template_key)
    if generator:
        return generator(params)

    # Generic fallback for templates without a custom generator
    name = template.get("name_en", template.get("key", "Custom Strategy"))
    desc = template.get("description_en", "")
    return _build_indicator_code(name, desc, "# TODO: implement strategy logic", "", "", "")
