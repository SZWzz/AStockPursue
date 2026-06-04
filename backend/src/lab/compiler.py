"""Strategy compiler: generates indicator code from structured rule configs.

Ported from QuantDinger's strategy_compiler.py. Supports 7 indicator types
(supertrend, ema, rsi, macd, bollinger, kdj, ma) with operator-based entry/exit logic.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ── Sanitization helpers (defense against template injection) ──────────────


def _sanitize_ident(name: str) -> str:
    """Allow only alphanumeric + underscore for code-gen identifiers.

    Raises ValueError if the name contains anything else, preventing
    injection of arbitrary Python code through {col}/{val} in templates.
    """
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", name):
        raise ValueError(f"Invalid identifier in strategy compile: {name!r}")
    return name


def _sanitize_numeric(val: str) -> float:
    """Ensure value is a valid number. Rejects non-numeric injection."""
    try:
        return float(val)
    except (ValueError, TypeError):
        raise ValueError(f"Invalid numeric value in strategy compile: {val!r}")

# Operator → (buy_condition_template, sell_condition_template)
# Templates use {col} for the indicator column name and {val} for threshold value.
_OPERATOR_MAP: dict[str, dict[str, tuple[str, str]]] = {
    "ema": {
        "price_above":  ("df['close'] > {col}", "df['close'] < {col}"),
        "price_below":  ("df['close'] < {col}", "df['close'] > {col}"),
        "cross_up":     ("(df['close'] > {col}) & (df['close'].shift(1) <= {col}.shift(1))",
                         "(df['close'] < {col}) & (df['close'].shift(1) >= {col}.shift(1))"),
        "cross_down":   ("(df['close'] < {col}) & (df['close'].shift(1) >= {col}.shift(1))",
                         "(df['close'] > {col}) & (df['close'].shift(1) <= {col}.shift(1))"),
    },
    "ma": {
        "price_above":  ("df['close'] > {col}", "df['close'] < {col}"),
        "price_below":  ("df['close'] < {col}", "df['close'] > {col}"),
        "cross_up":     ("(df['close'] > {col}) & (df['close'].shift(1) <= {col}.shift(1))",
                         "(df['close'] < {col}) & (df['close'].shift(1) >= {col}.shift(1))"),
        "cross_down":   ("(df['close'] < {col}) & (df['close'].shift(1) >= {col}.shift(1))",
                         "(df['close'] > {col}) & (df['close'].shift(1) <= {col}.shift(1))"),
    },
    "rsi": {
        "<":     ("{col} < {val}", "{col} > {val}"),
        ">":     ("{col} > {val}", "{col} < {val}"),
        "cross_up":   ("({col} > {val}) & ({col}.shift(1) <= {val})",
                       "({col} < {val}) & ({col}.shift(1) >= {val})"),
        "cross_down": ("({col} < {val}) & ({col}.shift(1) >= {val})",
                       "({col} > {val}) & ({col}.shift(1) <= {val})"),
    },
    "macd": {
        "diff_gt_dea": ("{line} > {sig}", "{line} < {sig}"),
        "diff_lt_dea": ("{line} < {sig}", "{line} > {sig}"),
        "cross_up":    ("({line} > {sig}) & ({line}.shift(1) <= {sig}.shift(1))",
                        "({line} < {sig}) & ({line}.shift(1) >= {sig}.shift(1))"),
        "cross_down":  ("({line} < {sig}) & ({line}.shift(1) >= {sig}.shift(1))",
                        "({line} > {sig}) & ({line}.shift(1) <= {sig}.shift(1))"),
    },
    "bollinger": {
        "price_above_upper":  ("df['close'] > {upper}", "df['close'] < {lower}"),
        "price_below_lower":  ("df['close'] < {lower}", "df['close'] > {upper}"),
        "price_above_mid":    ("df['close'] > {mid}", "df['close'] < {mid}"),
        "price_below_mid":    ("df['close'] < {mid}", "df['close'] > {mid}"),
        "cross_up_lower":     ("(df['close'] > {lower}) & (df['close'].shift(1) <= {lower}.shift(1))",
                               "(df['close'] < {upper}) & (df['close'].shift(1) >= {upper}.shift(1))"),
        "cross_down_upper":   ("(df['close'] < {upper}) & (df['close'].shift(1) >= {upper}.shift(1))",
                               "(df['close'] > {lower}) & (df['close'].shift(1) <= {lower}.shift(1))"),
    },
    "kdj": {
        "k_gt_d":      ("{k} > {d}", "{k} < {d}"),
        "k_lt_d":      ("{k} < {d}", "{k} > {d}"),
        "gold_cross":  ("({k} > {d}) & ({k}.shift(1) <= {d}.shift(1))",
                        "({k} < {d}) & ({k}.shift(1) >= {d}.shift(1))"),
        "death_cross": ("({k} < {d}) & ({k}.shift(1) >= {d}.shift(1))",
                        "({k} > {d}) & ({k}.shift(1) <= {d}.shift(1))"),
    },
    "supertrend": {
        "trend_bullish":  ("(st_trend == 1.0) & (st_trend.shift(1) == -1.0)",
                           "(st_trend == -1.0) & (st_trend.shift(1) == 1.0)"),
        "is_uptrend":     ("st_trend == 1.0", "st_trend == -1.0"),
    },
}


def compile_strategy(config: dict[str, Any]) -> str:
    """Compile a strategy config into executable indicator code.

    Config format::

        {
            "name": "My Strategy",
            "entry_rules": [
                {"indicator": "ema", "params": {"period": 20}, "operator": "cross_up"},
                {"indicator": "rsi", "params": {"period": 14}, "operator": "<", "value": 30}
            ],
            "position_config": {"initial_size_pct": 50, "leverage": 1, "max_pyramiding": 0},
            "pyramiding_rules": {"enabled": false},
            "risk_management": {
                "stop_loss": {"enabled": true, "value": 5},
                "trailing_stop": {"enabled": false}
            }
        }

    Returns complete Python indicator source code.
    """
    name = config.get("name", "Compiled Strategy")
    entry_rules = config.get("entry_rules", [])
    pos = config.get("position_config", {})
    pyr = config.get("pyramiding_rules", {})
    risk = config.get("risk_management", {})

    sl = risk.get("stop_loss", {})
    ts = risk.get("trailing_stop", {})
    sl_pct = sl.get("value", 0) / 100.0 if sl.get("enabled") else 0.0
    ts_pct = ts.get("callback_pct", 0) / 100.0 if ts.get("enabled") else 0.0

    params_block = _build_params_block(entry_rules)

    code = f'''my_indicator_name = "{name}"
my_indicator_description = "Compiled strategy: {', '.join(r.get('indicator', '?') for r in entry_rules)}"
{params_block}
# @strategy stopLossPct {sl_pct}
# @strategy entryPct 0.5

df = df.copy()

{_build_indicators(entry_rules)}
{_build_signals(entry_rules)}

output = {{
    "name": my_indicator_name,
    "plots": [
{_build_plots(entry_rules)}
    ],
    "signals": [],
}}
'''
    return code


def _build_params_block(rules: list[dict]) -> str:
    """Generate # @param annotations from rule configs."""
    lines: list[str] = []
    has_rsi = any(r["indicator"] == "rsi" for r in rules)
    for rule in rules:
        ind = rule["indicator"]
        params = rule.get("params", {})
        if ind == "ema" or ind == "ma":
            lines.append(f"# @param {ind}_period int {params.get('period', 20)} {ind.upper()} period")
        elif ind == "rsi":
            lines.append(f"# @param rsi_period int {params.get('period', 14)} RSI period")
        elif ind == "macd":
            lines.append(f"# @param macd_fast int {params.get('fast_period', 12)} MACD fast period")
            lines.append(f"# @param macd_slow int {params.get('slow_period', 26)} MACD slow period")
            lines.append(f"# @param macd_signal int {params.get('signal_period', 9)} MACD signal period")
        elif ind == "bollinger":
            lines.append(f"# @param bb_period int {params.get('period', 20)} Bollinger period")
            lines.append(f"# @param bb_std float {params.get('std_dev', 2.0)} Std deviations")
        elif ind == "kdj":
            lines.append(f"# @param kdj_period int {params.get('period', 9)} KDJ period")
        elif ind == "supertrend":
            lines.append(f"# @param st_period int {params.get('period', 14)} SuperTrend ATR period")
            lines.append(f"# @param st_mult float {params.get('multiplier', 3.0)} SuperTrend multiplier")
    if has_rsi and any(rule.get("operator") in ("<", ">", "cross_up", "cross_down") for rule in rules if rule["indicator"] == "rsi"):
        for rule in rules:
            if rule["indicator"] == "rsi" and "value" in rule:
                safe_val = int(_sanitize_numeric(str(rule["value"])))
                lines.append(f"# @param rsi_threshold int {safe_val} RSI threshold")
    return "\n".join(lines)


def _build_indicators(rules: list[dict]) -> str:
    """Generate indicator calculation code."""
    lines: list[str] = ["# === Indicator Calculations ==="]
    calculated: set[str] = set()

    for rule in rules:
        ind = rule["indicator"]
        params = rule.get("params", {})

        if ind == "ema":
            p = params.get("period", 20)
            key = f"ema_{p}"
            if key not in calculated:
                lines.append(f"df['{key}'] = df['close'].ewm(span={p}, adjust=False, min_periods={p}).mean()")
                calculated.add(key)

        elif ind == "ma":
            p = params.get("period", 20)
            t = params.get("ma_type", "sma")
            key = f"ma_{t}_{p}"
            if key not in calculated:
                if t == "sma":
                    lines.append(f"df['{key}'] = df['close'].rolling(window={p}, min_periods={p}).mean()")
                else:
                    lines.append(f"df['{key}'] = df['close'].ewm(span={p}, adjust=False, min_periods={p}).mean()")
                calculated.add(key)

        elif ind == "rsi":
            p = params.get("period", 14)
            key = f"rsi_{p}"
            if key not in calculated:
                lines.append(f"delta = df['close'].diff()")
                lines.append(f"gain = delta.where(delta > 0, 0.0)")
                lines.append(f"loss = (-delta).where(delta < 0, 0.0)")
                lines.append(f"avg_gain = gain.rolling(window={p}, min_periods={p}).mean()")
                lines.append(f"avg_loss = loss.rolling(window={p}, min_periods={p}).mean()")
                lines.append(f"rs = avg_gain / avg_loss.replace(0, np.nan)")
                lines.append(f"df['{key}'] = 100.0 - (100.0 / (1.0 + rs))")
                calculated.add(key)

        elif ind == "macd":
            f = params.get("fast_period", 12)
            s = params.get("slow_period", 26)
            sig = params.get("signal_period", 9)
            line_key = f"macd_{f}_{s}_line"
            sig_key = f"macd_{f}_{s}_sig"
            if line_key not in calculated:
                lines.append(f"ema_f = df['close'].ewm(span={f}, adjust=False, min_periods={f}).mean()")
                lines.append(f"ema_s = df['close'].ewm(span={s}, adjust=False, min_periods={s}).mean()")
                lines.append(f"df['{line_key}'] = ema_f - ema_s")
                lines.append(f"df['{sig_key}'] = df['{line_key}'].ewm(span={sig}, adjust=False, min_periods={sig}).mean()")
                calculated.add(line_key)

        elif ind == "bollinger":
            p = params.get("period", 20)
            d = params.get("std_dev", 2.0)
            key = f"bb_{p}_{d}"
            if key not in calculated:
                lines.append(f"df['{key}_mid'] = df['close'].rolling(window={p}, min_periods={p}).mean()")
                lines.append(f"df['{key}_std'] = df['close'].rolling(window={p}, min_periods={p}).std()")
                lines.append(f"df['{key}_upper'] = df['{key}_mid'] + {d} * df['{key}_std']")
                lines.append(f"df['{key}_lower'] = df['{key}_mid'] - {d} * df['{key}_std']")
                calculated.add(key)

        elif ind == "kdj":
            p = params.get("period", 9)
            sig = params.get("signal_period", 3)
            key = f"kdj_{p}_{sig}"
            if key not in calculated:
                lines.append(f"lo_min = df['low'].rolling({p}, min_periods={p}).min()")
                lines.append(f"hi_max = df['high'].rolling({p}, min_periods={p}).max()")
                lines.append(f"rsv = ((df['close'] - lo_min) / (hi_max - lo_min).replace(0, np.nan)) * 100")
                lines.append(f"df['{key}_k'] = rsv.ewm(span={sig}, adjust=False, min_periods={sig}).mean()")
                lines.append(f"df['{key}_d'] = df['{key}_k'].ewm(span={sig}, adjust=False, min_periods={sig}).mean()")
                lines.append(f"df['{key}_j'] = 3 * df['{key}_k'] - 2 * df['{key}_d']")
                calculated.add(key)

        elif ind == "supertrend":
            p = params.get("period", 14)
            m = params.get("multiplier", 3.0)
            key = f"st_{p}_{m}"
            if key not in calculated:
                lines.append(f"cl = df['close']; hi = df['high']; lo = df['low']")
                lines.append(f"tr = pd.concat([hi - lo, (hi - cl.shift(1)).abs(), (lo - cl.shift(1)).abs()], axis=1).max(axis=1)")
                lines.append(f"atr = tr.ewm(alpha=1.0/{p}, adjust=False, min_periods={p}).mean()")
                lines.append(f"hl2 = (hi + lo) / 2")
                lines.append(f"b_upper = hl2 + {m} * atr")
                lines.append(f"b_lower = hl2 - {m} * atr")
                lines.append(f"st_trend = pd.Series(0.0, index=df.index)")
                lines.append(f"st_trend.iloc[0] = 1.0")
                lines.append(f"for i in range(1, len(df)):")
                lines.append(f"    if cl.iloc[i] > b_upper.iloc[i-1] if not pd.isna(b_upper.iloc[i-1]) else False:")
                lines.append(f"        st_trend.iloc[i] = 1.0")
                lines.append(f"    elif cl.iloc[i] < b_lower.iloc[i-1] if not pd.isna(b_lower.iloc[i-1]) else False:")
                lines.append(f"        st_trend.iloc[i] = -1.0")
                lines.append(f"    else:")
                lines.append(f"        st_trend.iloc[i] = st_trend.iloc[i-1]")
                calculated.add(key)

    return "\n".join(lines)


def _build_signals(rules: list[dict]) -> str:
    """Generate buy/sell signal code from entry rules."""
    buy_conds: list[str] = []
    sell_conds: list[str] = []

    for rule in rules:
        ind = rule["indicator"]
        params = rule.get("params", {})
        operator = rule.get("operator", "")
        value = rule.get("value")

        op_map = _OPERATOR_MAP.get(ind, {})
        if operator not in op_map:
            continue
        buy_tpl, sell_tpl = op_map[operator]

        # Build template variables
        tpl_vars: dict[str, str] = {}
        if ind == "ema":
            tpl_vars["col"] = f"df['ema_{params.get('period', 20)}']"
        elif ind == "ma":
            t = params.get("ma_type", "sma")
            tpl_vars["col"] = f"df['ma_{t}_{params.get('period', 20)}']"
        elif ind == "rsi":
            tpl_vars["col"] = f"df['rsi_{_sanitize_ident(str(params.get('period', 14)))}']"
            tpl_vars["val"] = str(_sanitize_numeric(str(value or 30)))
        elif ind == "macd":
            f = params.get("fast_period", 12)
            s = params.get("slow_period", 26)
            tpl_vars["line"] = f"df['macd_{f}_{s}_line']"
            tpl_vars["sig"] = f"df['macd_{f}_{s}_sig']"
        elif ind == "bollinger":
            p = params.get("period", 20)
            d = params.get("std_dev", 2.0)
            tpl_vars["upper"] = f"df['bb_{p}_{d}_upper']"
            tpl_vars["lower"] = f"df['bb_{p}_{d}_lower']"
            tpl_vars["mid"] = f"df['bb_{p}_{d}_mid']"
        elif ind == "kdj":
            p = params.get("period", 9)
            sig = params.get("signal_period", 3)
            tpl_vars["k"] = f"df['kdj_{p}_{sig}_k']"
            tpl_vars["d"] = f"df['kdj_{p}_{sig}_d']"

        if tpl_vars:
            buy_conds.append(buy_tpl.format(**tpl_vars))
            sell_conds.append(sell_tpl.format(**tpl_vars))
        elif ind == "supertrend":
            buy_conds.append(buy_tpl)
            sell_conds.append(sell_tpl)

    lines = ["# === Entry/Exit Signals ==="]
    if buy_conds:
        lines.append(f"df['buy'] = ({' & '.join(buy_conds)}).fillna(False)")
    else:
        lines.append("df['buy'] = False")
    if sell_conds:
        lines.append(f"df['sell'] = ({' & '.join(sell_conds)}).fillna(False)")
    else:
        lines.append("df['sell'] = False")

    return "\n".join(lines)


def _build_plots(rules: list[dict]) -> str:
    """Generate output plots entries."""
    plot_lines: list[str] = []
    for rule in rules:
        ind = rule["indicator"]
        params = rule.get("params", {})
        if ind == "ema":
            p = params.get("period", 20)
            plot_lines.append(f'        {{"name": "EMA {p}", "data": df["ema_{p}"].tolist(), "color": "#FF9800", "overlay": True}},')
        elif ind == "ma":
            t = params.get("ma_type", "sma")
            p = params.get("period", 20)
            plot_lines.append(f'        {{"name": "{t.upper()} {p}", "data": df["ma_{t}_{p}"].tolist(), "color": "#2196F3", "overlay": True}},')
        elif ind == "rsi":
            p = params.get("period", 14)
            plot_lines.append(f'        {{"name": "RSI {p}", "data": df["rsi_{p}"].tolist(), "color": "#9C27B0", "overlay": False}},')
        elif ind == "macd":
            f = params.get("fast_period", 12)
            s = params.get("slow_period", 26)
            plot_lines.append(f'        {{"name": "MACD", "data": df["macd_{f}_{s}_line"].tolist(), "color": "#2196F3", "overlay": False}},')
        elif ind == "bollinger":
            p = params.get("period", 20)
            d = params.get("std_dev", 2.0)
            plot_lines.append(f'        {{"name": "BB Mid", "data": df["bb_{p}_{d}_mid"].tolist(), "color": "#2196F3", "overlay": True}},')
            plot_lines.append(f'        {{"name": "BB Upper", "data": df["bb_{p}_{d}_upper"].tolist(), "color": "#FF9800", "overlay": True}},')
            plot_lines.append(f'        {{"name": "BB Lower", "data": df["bb_{p}_{d}_lower"].tolist(), "color": "#FF9800", "overlay": True}},')
        elif ind == "supertrend":
            plot_lines.append(f'        {{"name": "SuperTrend", "data": st_trend.tolist(), "color": "#4CAF50", "overlay": False}},')
        elif ind == "kdj":
            p = params.get("period", 9)
            sig = params.get("signal_period", 3)
            plot_lines.append(f'        {{"name": "K", "data": df["kdj_{p}_{sig}_k"].tolist(), "color": "#2196F3", "overlay": False}},')
            plot_lines.append(f'        {{"name": "D", "data": df["kdj_{p}_{sig}_d"].tolist(), "color": "#FF9800", "overlay": False}},')

    return "\n".join(plot_lines) if plot_lines else ""
