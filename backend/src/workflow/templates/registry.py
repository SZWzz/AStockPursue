"""Strategy template registry and pattern matcher.

Each template defines a common strategy pattern as a {nodes, edges} dict.
The pattern matcher analyses Python SignalEngine code and scores it against
known templates.  Scores ≥ 0.7 are considered matches.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── Template definitions ──────────────────────────────────────────────────────
# Each template: {id, name, description, nodes, edges, patterns}
# patterns: list of regex rules that must all match for this template


TEMPLATES: List[Dict[str, Any]] = [
    # ── 1. Single-factor ranking ───────────────────────────────────────────
    {
        "id": "single_factor_rank",
        "name": "Single Factor Ranking",
        "description": "Compute one factor, rank stocks cross-sectionally, buy top N",
        "patterns": {
            "has_one_factor": True,        # Only 1 factor computation
            "has_rank_or_sort": True,       # Uses rank/sort/sorted
            "has_top_n": True,              # Uses top_n or [:N] slicing
            "has_rebalance": "optional",    # Optional rebalance frequency
        },
        "nodes": [
            {"id": "t_data", "node_type": "column_extract", "label": "close",
             "position": {"x": 0, "y": 0}, "config": {"column": "close"}},
            {"id": "t_factor", "node_type": "pct_change", "label": "Δ%(20)",
             "position": {"x": 260, "y": 0}, "config": {"periods": 20}},
            {"id": "t_select", "node_type": "rank_select", "label": "Top 10",
             "position": {"x": 520, "y": 0}, "config": {"top_n": 10, "ascending": "false"}},
            {"id": "t_weight", "node_type": "signal_weight", "label": "Equal Weight",
             "position": {"x": 780, "y": 0}, "config": {"mode": "equal"}},
            {"id": "t_rebalance", "node_type": "rebalance", "label": "Rebalance(20)",
             "position": {"x": 1040, "y": 0}, "config": {"frequency": 20}},
        ],
        "edges": [
            {"id": "e1", "source": "t_data", "source_port": "series", "target": "t_factor", "target_port": "series"},
            {"id": "e2", "source": "t_factor", "source_port": "returns", "target": "t_select", "target_port": "factor"},
            {"id": "e3", "source": "t_select", "source_port": "signal", "target": "t_weight", "target_port": "signal"},
            {"id": "e4", "source": "t_weight", "source_port": "signal", "target": "t_rebalance", "target_port": "signal"},
        ],
    },
    # ── 2. Dual MA crossover ───────────────────────────────────────────────
    {
        "id": "dual_ma_crossover",
        "name": "Dual MA Crossover",
        "description": "Golden cross / death cross with MA crossover and position holding",
        "patterns": {
            "has_two_mas": True,             # Two moving averages
            "has_crossover_logic": True,      # Crossover detection
            "has_position_state": True,       # in_position / holding state
        },
        "nodes": [
            {"id": "t_data", "node_type": "column_extract", "label": "close",
             "position": {"x": 0, "y": -100}, "config": {"column": "close"}},
            {"id": "t_ma5", "node_type": "ma", "label": "MA(5)",
             "position": {"x": 260, "y": -180}, "config": {"window": 5}},
            {"id": "t_ma20", "node_type": "ma", "label": "MA(20)",
             "position": {"x": 260, "y": -20}, "config": {"window": 20}},
            {"id": "t_golden", "node_type": "cross_over", "label": "Golden Cross",
             "position": {"x": 520, "y": -180}, "config": {"direction": "above"}},
            {"id": "t_death", "node_type": "cross_over", "label": "Death Cross",
             "position": {"x": 520, "y": -20}, "config": {"direction": "below"}},
            {"id": "t_hold", "node_type": "hold_signal", "label": "Hold",
             "position": {"x": 780, "y": -100}, "config": {"initial": "flat"}},
        ],
        "edges": [
            {"id": "e1", "source": "t_data", "source_port": "series", "target": "t_ma5", "target_port": "series"},
            {"id": "e2", "source": "t_data", "source_port": "series", "target": "t_ma20", "target_port": "series"},
            {"id": "e3", "source": "t_ma5", "source_port": "ma", "target": "t_golden", "target_port": "fast"},
            {"id": "e4", "source": "t_ma20", "source_port": "ma", "target": "t_golden", "target_port": "slow"},
            {"id": "e5", "source": "t_ma5", "source_port": "ma", "target": "t_death", "target_port": "fast"},
            {"id": "e6", "source": "t_ma20", "source_port": "ma", "target": "t_death", "target_port": "slow"},
            {"id": "e7", "source": "t_golden", "source_port": "signal", "target": "t_hold", "target_port": "enter"},
            {"id": "e8", "source": "t_death", "source_port": "signal", "target": "t_hold", "target_port": "exit"},
        ],
    },
    # ── 3. Multi-factor composite ───────────────────────────────────────────
    {
        "id": "multi_factor_composite",
        "name": "Multi-Factor Composite",
        "description": "Multiple factors → zscore → equal-weight composite → rank → top N",
        "patterns": {
            "has_multiple_factors": True,     # ≥2 factors computed
            "has_zscore_or_standardize": True, # zscore / standardisation
            "has_composite_score": True,       # Composite / sum / equal weight
        },
        "nodes": [
            {"id": "t_data", "node_type": "column_extract", "label": "close",
             "position": {"x": 0, "y": 0}, "config": {"column": "close"}},
            {"id": "t_mom", "node_type": "pct_change", "label": "Momentum(20)",
             "position": {"x": 260, "y": -100}, "config": {"periods": 20}},
            {"id": "t_std", "node_type": "std_dev", "label": "Std(20)",
             "position": {"x": 260, "y": 100}, "config": {"window": 20}},
            {"id": "t_z1", "node_type": "scale", "label": "ZScore",
             "position": {"x": 520, "y": -100}, "config": {"method": "zscore"}},
            {"id": "t_z2", "node_type": "scale", "label": "ZScore",
             "position": {"x": 520, "y": 100}, "config": {"method": "zscore"}},
            {"id": "t_neg", "node_type": "math_transform", "label": "−x",
             "position": {"x": 780, "y": 100}, "config": {"op": "neg"}},
            {"id": "t_add", "node_type": "arithmetic", "label": "+",
             "position": {"x": 780, "y": -100}, "config": {"op": "add"}},
            {"id": "t_select", "node_type": "rank_select", "label": "Top 10",
             "position": {"x": 1040, "y": -100}, "config": {"top_n": 10, "ascending": "false"}},
            {"id": "t_weight", "node_type": "signal_weight", "label": "Equal Weight",
             "position": {"x": 1300, "y": -100}, "config": {"mode": "equal"}},
        ],
        "edges": [
            {"id": "e1", "source": "t_data", "source_port": "series", "target": "t_mom", "target_port": "series"},
            {"id": "e2", "source": "t_data", "source_port": "series", "target": "t_std", "target_port": "series"},
            {"id": "e3", "source": "t_mom", "source_port": "returns", "target": "t_z1", "target_port": "series"},
            {"id": "e4", "source": "t_std", "source_port": "std", "target": "t_z2", "target_port": "series"},
            {"id": "e5", "source": "t_z2", "source_port": "scaled", "target": "t_neg", "target_port": "series"},
            {"id": "e6", "source": "t_z1", "source_port": "scaled", "target": "t_add", "target_port": "a"},
            {"id": "e7", "source": "t_neg", "source_port": "result", "target": "t_add", "target_port": "b"},
            {"id": "e8", "source": "t_add", "source_port": "result", "target": "t_select", "target_port": "factor"},
            {"id": "e9", "source": "t_select", "source_port": "signal", "target": "t_weight", "target_port": "signal"},
        ],
    },
    # ── 4. Threshold breakout ────────────────────────────────────────────────
    {
        "id": "threshold_breakout",
        "name": "Threshold Breakout",
        "description": "Buy when factor crosses above/below a fixed threshold",
        "patterns": {
            "has_threshold": True,            # Uses a fixed threshold value
            "has_single_factor": True,        # One primary factor
            "has_no_ranking": True,           # No ranking (uses threshold instead)
        },
        "nodes": [
            {"id": "t_data", "node_type": "column_extract", "label": "close",
             "position": {"x": 0, "y": 0}, "config": {"column": "close"}},
            {"id": "t_factor", "node_type": "pct_change", "label": "Δ%(5)",
             "position": {"x": 260, "y": 0}, "config": {"periods": 5}},
            {"id": "t_select", "node_type": "threshold_select", "label": "> 0.02",
             "position": {"x": 520, "y": 0}, "config": {"threshold": 0.02, "op": "gt"}},
        ],
        "edges": [
            {"id": "e1", "source": "t_data", "source_port": "series", "target": "t_factor", "target_port": "series"},
            {"id": "e2", "source": "t_factor", "source_port": "returns", "target": "t_select", "target_port": "factor"},
        ],
    },
    # ── 5. RSI mean-reversion ────────────────────────────────────────────────
    {
        "id": "rsi_mean_reversion",
        "name": "RSI Mean Reversion",
        "description": "Buy when RSI < oversold, sell when RSI > overbought",
        "patterns": {
            "has_rsi": True,                  # RSI calculation
            "has_overbought_oversold": True,   # Thresholds like 30/70
        },
        "nodes": [
            {"id": "t_data", "node_type": "column_extract", "label": "close",
             "position": {"x": 0, "y": 0}, "config": {"column": "close"}},
            {"id": "t_delta", "node_type": "delta", "label": "Δ(1)",
             "position": {"x": 260, "y": -80}, "config": {"periods": 1}},
            {"id": "t_gain", "node_type": "rolling_extremum", "label": "Gain(14)",
             "position": {"x": 520, "y": -160}, "config": {"window": 14, "op": "max"}},
            {"id": "t_loss", "node_type": "math_transform", "label": "−x",
             "position": {"x": 520, "y": -80}, "config": {"op": "neg"}},
            {"id": "t_loss_avg", "node_type": "ma", "label": "AvgLoss(14)",
             "position": {"x": 780, "y": -80}, "config": {"window": 14}},
            {"id": "t_gain_avg", "node_type": "ma", "label": "AvgGain(14)",
             "position": {"x": 780, "y": -160}, "config": {"window": 14}},
            {"id": "t_rs", "node_type": "arithmetic", "label": "÷",
             "position": {"x": 1040, "y": -120}, "config": {"op": "div"}},
            {"id": "t_select", "node_type": "threshold_select", "label": "< 30",
             "position": {"x": 1300, "y": -120}, "config": {"threshold": 30, "op": "lt"}},
        ],
        "edges": [
            {"id": "e1", "source": "t_data", "source_port": "series", "target": "t_delta", "target_port": "series"},
            {"id": "e2", "source": "t_delta", "source_port": "delta", "target": "t_gain", "target_port": "series"},
            {"id": "e3", "source": "t_delta", "source_port": "delta", "target": "t_loss", "target_port": "series"},
            {"id": "e4", "source": "t_loss", "source_port": "result", "target": "t_loss_avg", "target_port": "series"},
            {"id": "e5", "source": "t_gain", "source_port": "result", "target": "t_gain_avg", "target_port": "series"},
            {"id": "e6", "source": "t_gain_avg", "source_port": "ma", "target": "t_rs", "target_port": "a"},
            {"id": "e7", "source": "t_loss_avg", "source_port": "ma", "target": "t_rs", "target_port": "b"},
            {"id": "e8", "source": "t_rs", "source_port": "result", "target": "t_select", "target_port": "factor"},
        ],
    },
    # ── 6. Bollinger Bands ───────────────────────────────────────────────────
    {
        "id": "bollinger_bands",
        "name": "Bollinger Bands Breakout",
        "description": "Buy when price crosses above/below Bollinger Bands",
        "patterns": {
            "has_ma": True,                   # Has moving average
            "has_std_bands": True,            # Has ±N×std bands
            "has_band_comparison": True,       # Price vs band comparison
        },
        "nodes": [
            {"id": "t_data", "node_type": "column_extract", "label": "close",
             "position": {"x": 0, "y": 0}, "config": {"column": "close"}},
            {"id": "t_ma", "node_type": "ma", "label": "MA(20)",
             "position": {"x": 260, "y": -80}, "config": {"window": 20}},
            {"id": "t_std", "node_type": "std_dev", "label": "Std(20)",
             "position": {"x": 260, "y": 80}, "config": {"window": 20}},
            {"id": "t_upper", "node_type": "arithmetic", "label": "+2σ",
             "position": {"x": 520, "y": -120}, "config": {"op": "add"}},
            {"id": "t_lower", "node_type": "arithmetic", "label": "−2σ",
             "position": {"x": 520, "y": 120}, "config": {"op": "sub"}},
            {"id": "t_compare", "node_type": "compare", "label": "price < lower",
             "position": {"x": 780, "y": 0}, "config": {"op": "lt"}},
        ],
        "edges": [
            {"id": "e1", "source": "t_data", "source_port": "series", "target": "t_ma", "target_port": "series"},
            {"id": "e2", "source": "t_data", "source_port": "series", "target": "t_std", "target_port": "series"},
            {"id": "e3", "source": "t_ma", "source_port": "ma", "target": "t_upper", "target_port": "a"},
            {"id": "e4", "source": "t_std", "source_port": "std", "target": "t_upper", "target_port": "b"},
            {"id": "e5", "source": "t_ma", "source_port": "ma", "target": "t_lower", "target_port": "a"},
            {"id": "e6", "source": "t_std", "source_port": "std", "target": "t_lower", "target_port": "b"},
            {"id": "e7", "source": "t_data", "source_port": "series", "target": "t_compare", "target_port": "a"},
            {"id": "e8", "source": "t_lower", "source_port": "result", "target": "t_compare", "target_port": "b"},
        ],
    },
    # ── 7. Volume-price confirmation ─────────────────────────────────────────
    {
        "id": "volume_price_confirm",
        "name": "Volume-Price Confirmation",
        "description": "Buy when price up AND volume above average",
        "patterns": {
            "has_volume": True,               # Volume analysis
            "has_price_condition": True,       # Price condition
            "has_and_logic": True,             # AND combination
        },
        "nodes": [
            {"id": "t_close", "node_type": "column_extract", "label": "close",
             "position": {"x": 0, "y": -100}, "config": {"column": "close"}},
            {"id": "t_vol", "node_type": "column_extract", "label": "volume",
             "position": {"x": 0, "y": 100}, "config": {"column": "volume"}},
            {"id": "t_ret", "node_type": "pct_change", "label": "Ret(1)",
             "position": {"x": 260, "y": -100}, "config": {"periods": 1}},
            {"id": "t_vol_ma", "node_type": "ma", "label": "VolMA(20)",
             "position": {"x": 260, "y": 100}, "config": {"window": 20}},
            {"id": "t_price_up", "node_type": "compare", "label": "ret > 0",
             "position": {"x": 520, "y": -100}, "config": {"op": "gt"}},
            {"id": "t_vol_up", "node_type": "compare", "label": "vol > ma",
             "position": {"x": 520, "y": 100}, "config": {"op": "gt"}},
            {"id": "t_zero", "node_type": "constant", "label": "0",
             "position": {"x": 260, "y": -200}, "config": {"constant": 0.0}},
            {"id": "t_and", "node_type": "bool_combine", "label": "AND",
             "position": {"x": 780, "y": 0}, "config": {"op": "and"}},
        ],
        "edges": [
            {"id": "e1", "source": "t_close", "source_port": "series", "target": "t_ret", "target_port": "series"},
            {"id": "e2", "source": "t_vol", "source_port": "series", "target": "t_vol_ma", "target_port": "series"},
            {"id": "e3", "source": "t_ret", "source_port": "returns", "target": "t_price_up", "target_port": "a"},
            {"id": "e4", "source": "t_zero", "source_port": "value", "target": "t_price_up", "target_port": "b"},
            {"id": "e5", "source": "t_vol", "source_port": "series", "target": "t_vol_up", "target_port": "a"},
            {"id": "e6", "source": "t_vol_ma", "source_port": "ma", "target": "t_vol_up", "target_port": "b"},
            {"id": "e7", "source": "t_price_up", "source_port": "result", "target": "t_and", "target_port": "a"},
            {"id": "e8", "source": "t_vol_up", "source_port": "result", "target": "t_and", "target_port": "b"},
        ],
    },
    # ── 8. Momentum rotation ─────────────────────────────────────────────────
    {
        "id": "momentum_rotation",
        "name": "Momentum Rotation",
        "description": "Buy top N assets by momentum, weight proportional to factor, rotate periodically",
        "patterns": {
            "has_momentum": True,             # Momentum/return calculation
            "has_top_n": True,                # Top N selection
            "has_proportional_weight": True,  # Factor-proportional weighting
            "has_rotation": True,             # Periodic rebalancing
        },
        "nodes": [
            {"id": "t_data", "node_type": "column_extract", "label": "close",
             "position": {"x": 0, "y": 0}, "config": {"column": "close"}},
            {"id": "t_mom", "node_type": "pct_change", "label": "Δ%(20)",
             "position": {"x": 260, "y": 0}, "config": {"periods": 20}},
            {"id": "t_select", "node_type": "rank_select", "label": "Top 5",
             "position": {"x": 520, "y": 0}, "config": {"top_n": 5, "ascending": "false"}},
            {"id": "t_weight", "node_type": "signal_weight", "label": "Factor Prop",
             "position": {"x": 780, "y": 0}, "config": {"mode": "factor_proportional"}},
            {"id": "t_rebalance", "node_type": "rebalance", "label": "Rebalance(5)",
             "position": {"x": 1040, "y": 0}, "config": {"frequency": 5}},
        ],
        "edges": [
            {"id": "e1", "source": "t_data", "source_port": "series", "target": "t_mom", "target_port": "series"},
            {"id": "e2", "source": "t_mom", "source_port": "returns", "target": "t_select", "target_port": "factor"},
            {"id": "e3", "source": "t_select", "source_port": "signal", "target": "t_weight", "target_port": "signal"},
            {"id": "e4", "source": "t_mom", "source_port": "returns", "target": "t_weight", "target_port": "factor"},
            {"id": "e5", "source": "t_weight", "source_port": "signal", "target": "t_rebalance", "target_port": "signal"},
        ],
    },
]


# ── Pattern matching ──────────────────────────────────────────────────────────


def match_template(code: str) -> Optional[Tuple[Dict[str, Any], float]]:
    """Analyse Python SignalEngine code and return the best matching template.

    Args:
        code: Python source code of a SignalEngine class.

    Returns:
        (template_dict, score) if a template matches with score ≥ 0.7,
        otherwise None.
    """
    if not code or "class SignalEngine" not in code:
        return None

    best_template = None
    best_score = 0.0

    for template in TEMPLATES:
        score = _score_template(template, code)
        if score > best_score:
            best_score = score
            best_template = template

    if best_template and best_score >= 0.7:
        logger.info("Template match: %s (score=%.2f)", best_template["id"], best_score)
        return best_template, best_score

    return None


def _score_template(template: Dict[str, Any], code: str) -> float:
    """Score how well a strategy matches a template pattern."""
    patterns = template.get("patterns", {})
    if not patterns:
        return 0.0

    scores = []
    for key, required in patterns.items():
        if isinstance(required, bool):
            scores.append(1.0 if _check_pattern(key, code) else 0.0)
        elif required == "optional":
            scores.append(0.5)  # neutral for optional patterns

    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def _check_pattern(key: str, code: str) -> bool:
    """Check if a code pattern exists in the strategy source."""
    checks = {
        "has_one_factor": lambda c: (
            len(re.findall(r'(?:\.rolling\(|\.pct_change\(|\.diff\(|\.shift\(|\.mean\(\)|\.std\()', c)) == 1
        ),
        "has_single_factor": lambda c: (
            len(re.findall(r'(?:\.rolling\(|\.pct_change\(|\.diff\(|\.shift\()', c)) <= 2
        ),
        "has_multiple_factors": lambda c: (
            len(re.findall(r'(?:\.rolling\(|\.pct_change\(|\.diff\(|\.shift\(|\.std\()', c)) >= 3
        ),
        "has_rank_or_sort": lambda c: (
            bool(re.search(r'\b(?:rank|sorted|sort_values|argsort|nlargest|nsmallest)\b', c))
        ),
        "has_top_n": lambda c: (
            bool(re.search(r'\b(?:top_n|top_n\s*=|\[\s*:\s*N\s*\]|head\s*\(|nlargest)', c))
        ),
        "has_rebalance": lambda c: (
            bool(re.search(r'\b(?:rebalance|rebalance_freq|rebalance_frequency|%)\s*(?:freq|frequency|period)', c))
        ),
        "has_two_mas": lambda c: (
            len(re.findall(r'\.rolling\([^)]*\)\.mean\(\)', c)) >= 2
        ),
        "has_crossover_logic": lambda c: (
            bool(re.search(r'(?:>\s*\w+.*<\s*\w+|cross|crossover|golden|death)', c, re.IGNORECASE))
        ),
        "has_position_state": lambda c: (
            bool(re.search(r'\b(?:in_position|in_trade|is_long|position\s*=\s*(?:True|False|1|0))', c))
        ),
        "has_threshold": lambda c: (
            bool(re.search(r'(?:>\s*[\d.]+|<\s*[\d.]+|threshold)', c))
        ),
        "has_no_ranking": lambda c: (
            not bool(re.search(r'\b(?:rank|sorted|sort_values|nlargest)\b', c))
        ),
        "has_zscore_or_standardize": lambda c: (
            bool(re.search(r'\b(?:zscore|z_score|standardize|standardize|normalize|normalize)', c))
        ),
        "has_composite_score": lambda c: (
            bool(re.search(r'\b(?:composite|composite_score|score\s*\+=\s*|score\s*=\s*score\s*\+)', c))
        ),
        "has_rsi": lambda c: (
            bool(re.search(r'\b(?:[Rr][Ss][Ii]|rsi_|avg_gain|avg_loss|rs\s*=\s*)', c))
        ),
        "has_overbought_oversold": lambda c: (
            bool(re.search(r'\b(?:overbought|oversold|30|70)\b', c))
        ),
        "has_ma": lambda c: (
            bool(re.search(r'\.rolling\([^)]*\)\.mean\(\)', c))
        ),
        "has_std_bands": lambda c: (
            bool(re.search(r'(?:\.std\(\)|\bstd\b|upper|lower|band)', c))
        ),
        "has_band_comparison": lambda c: (
            bool(re.search(r'(?:upper|lower|band|\+.*\*.*std)', c))
        ),
        "has_volume": lambda c: (
            bool(re.search(r'\b(?:volume|vol_ratio|volume_ratio|vol\b)', c))
        ),
        "has_price_condition": lambda c: (
            bool(re.search(r'(?:close|price|ret(?:urn)?s?).*[><]', c))
        ),
        "has_and_logic": lambda c: (
            bool(re.search(r'&|\band\b|\bAND\b|\band\b', c))
        ),
        "has_momentum": lambda c: (
            bool(re.search(r'\b(?:momentum|momentum_|pct_change|\.pct_change\(|return)', c))
        ),
        "has_proportional_weight": lambda c: (
            bool(re.search(r'(?:\/\s*sum|\/\s*total|proportional|factor.*weight|weight.*factor)', c))
        ),
        "has_rotation": lambda c: (
            bool(re.search(r'\b(?:rotation|rotate|rebalance|rebalance_freq|periodically)', c))
        ),
    }

    checker = checks.get(key)
    if checker:
        try:
            return checker(code)
        except Exception:
            return False
    return False


def load_template(template_id: str) -> Optional[Dict[str, Any]]:
    """Load a template by ID, returning {nodes, edges} for canvas insertion."""
    for t in TEMPLATES:
        if t["id"] == template_id:
            return {
                "name": t["name"],
                "description": t["description"],
                "nodes": t["nodes"],
                "edges": t["edges"],
            }
    return None
