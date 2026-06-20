"""DuckDB-accelerated factor expression evaluator — Phase C P2.

Benchmarks Pandas vs DuckDB on 10 typical factor expressions before
committing to migration.  Only proceeds if speedup > 5x.

The evaluator compiles ExpressionTree nodes into DuckDB SQL using
window functions for time-series operations.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import numpy as np
import pandas as pd

from src.factors.mining.expression_tree import ExpressionTree, ExpressionNode

logger = logging.getLogger(__name__)


# Benchmarks: 10 factors covering different complexity levels
BENCHMARK_FACTORS: list[tuple[str, dict[str, Any]]] = [
    # Simple (1-2 nodes)
    ("ts_delta_close_20", {"op": "ts_delta", "children": [{"feature_id": "close"}], "window": 20}),
    ("rank_close", {"op": "rank", "children": [{"feature_id": "close"}]}),
    ("ts_mean_volume_10", {"op": "ts_mean", "children": [{"feature_id": "volume"}], "window": 10}),
    # Medium (3-4 nodes)
    ("rank_delta_over_mean", {
        "op": "rank",
        "children": [{"op": "div", "children": [
            {"op": "ts_delta", "children": [{"feature_id": "close"}], "window": 20},
            {"op": "ts_mean", "children": [{"feature_id": "close"}], "window": 20},
        ]}],
    }),
    ("volume_ratio_ranked", {
        "op": "rank",
        "children": [{"op": "div", "children": [
            {"feature_id": "volume"},
            {"op": "ts_mean", "children": [{"feature_id": "volume"}], "window": 20},
        ]}],
    }),
    ("zscore_close_20", {
        "op": "ts_zscore", "children": [{"feature_id": "close"}], "window": 20,
    }),
    # Complex (5-7 nodes)
    ("corr_rank_volume", {
        "op": "ts_corr",
        "children": [
            {"op": "rank", "children": [{"feature_id": "close"}]},
            {"op": "ts_mean", "children": [{"feature_id": "volume"}], "window": 10},
        ],
        "window": 30,
    }),
    ("volume_confirmed_momentum", {
        "op": "mul",
        "children": [
            {"op": "ts_delta", "children": [{"feature_id": "close"}], "window": 20},
            {"op": "div", "children": [
                {"feature_id": "volume"},
                {"op": "ts_mean", "children": [{"feature_id": "volume"}], "window": 20},
            ]},
        ],
    }),
    ("reversal_vol_filtered", {
        "op": "div",
        "children": [
            {"op": "neg", "children": [
                {"op": "ts_pct", "children": [{"feature_id": "close"}], "window": 5},
            ]},
            {"op": "ts_std", "children": [{"feature_id": "close"}], "window": 10},
        ],
    }),
    ("deviation_from_ma", {
        "op": "div",
        "children": [
            {"op": "sub", "children": [
                {"feature_id": "close"},
                {"op": "ts_mean", "children": [{"feature_id": "close"}], "window": 20},
            ]},
            {"op": "ts_std", "children": [{"feature_id": "close"}], "window": 20},
        ],
    }),
]

MIN_SPEEDUP_THRESHOLD = 5.0  # Must be > 5x to justify migration


def run_benchmark_gate(
    panel: dict[str, pd.DataFrame] | None = None,
) -> dict[str, Any]:
    """Run the DuckDB migration benchmark gate.

    If DuckDB is not installed or any factor is < 5x faster, returns
    ``{"migrate": False, "reason": ...}``.

    Returns:
        Dict with migrate decision and per-factor speedups.
    """
    try:
        import duckdb  # noqa: F401
    except ImportError:
        return {"migrate": False, "reason": "DuckDB not installed", "speedups": {}}

    if panel is None:
        panel = _make_benchmark_panel()

    speedups: dict[str, float] = {}
    for name, tree_dict in BENCHMARK_FACTORS:
        try:
            tree = ExpressionTree.from_dict(tree_dict)
            pandas_time = _benchmark_pandas(tree, panel)
            duckdb_time = _benchmark_duckdb(tree, panel)
            if duckdb_time > 0:
                speedup = pandas_time / duckdb_time
            else:
                speedup = 0.0
            speedups[name] = round(speedup, 1)

            if speedup < MIN_SPEEDUP_THRESHOLD:
                return {
                    "migrate": False,
                    "reason": f"Factor '{name}' speedup {speedup:.1f}x < {MIN_SPEEDUP_THRESHOLD}x threshold",
                    "speedups": speedups,
                }
        except Exception as exc:
            return {"migrate": False, "reason": f"Factor '{name}' failed: {exc}", "speedups": speedups}

    avg_speedup = float(np.mean(list(speedups.values())))
    return {
        "migrate": True,
        "avg_speedup": round(avg_speedup, 1),
        "speedups": speedups,
    }


def _make_benchmark_panel(n_dates: int = 500, n_stocks: int = 50) -> dict[str, pd.DataFrame]:
    """Create synthetic panel data for benchmarking."""
    rng = np.random.RandomState(42)
    dates = pd.date_range("2024-01-01", periods=n_dates, freq="B")
    codes = [f"S{i:03d}" for i in range(n_stocks)]

    close = pd.DataFrame(rng.randn(n_dates, n_stocks).cumsum(axis=0) + 100,
                         index=dates, columns=codes, dtype=np.float64)
    return {
        "close": close,
        "open": close * (1 + rng.randn(n_dates, n_stocks) * 0.005),
        "high": close * (1 + np.abs(rng.randn(n_dates, n_stocks)) * 0.01),
        "low": close * (1 - np.abs(rng.randn(n_dates, n_stocks)) * 0.01),
        "volume": pd.DataFrame(np.abs(rng.randn(n_dates, n_stocks)) * 1e6,
                               index=dates, columns=codes, dtype=np.float64),
    }


def _benchmark_pandas(tree: ExpressionTree, panel: dict[str, pd.DataFrame], n_runs: int = 5) -> float:
    """Benchmark Pandas evaluation."""
    fn = tree.to_callable()
    # Warmup
    fn(panel)
    times = []
    for _ in range(n_runs):
        t0 = time.perf_counter()
        fn(panel)
        times.append(time.perf_counter() - t0)
    return float(np.median(times))


def _benchmark_duckdb(tree: ExpressionTree, panel: dict[str, pd.DataFrame], n_runs: int = 5) -> float:
    """Benchmark DuckDB evaluation."""
    import duckdb
    conn = duckdb.connect(":memory:")
    for name, df in panel.items():
        conn.register(name, df.reset_index().melt(id_vars="index", var_name="code", value_name=name).rename(columns={"index": "date"}))

    # For now, DuckDB path just tests raw SQL compilation speed
    # Full DuckDB evaluator would compile tree → SQL → execute
    try:
        sql = _tree_to_preview_sql(tree.root)
        times = []
        for _ in range(n_runs):
            t0 = time.perf_counter()
            conn.execute(sql).fetchall()
            times.append(time.perf_counter() - t0)
        return float(np.median(times))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# DuckDB SQL compiler (preview — full implementation needs long-form panel)
# ---------------------------------------------------------------------------

def _tree_to_preview_sql(node: ExpressionNode, alias: str = "close") -> str:
    """Preview: compile a simplified tree to DuckDB SQL.

    Full implementation would pivot the wide panel to long form
    and use DuckDB window functions for ts_* operators.
    """
    if node.is_leaf:
        return f"{node.feature_id or alias}" if node.feature_id else f"{node.value or 0.0:.6g}"

    op = node.op or "?"
    child_sqls = [_tree_to_preview_sql(c, alias) for c in node.children]
    w = node.window or 20

    sql_map = {
        "add": lambda a, b: f"({a} + {b})",
        "sub": lambda a, b: f"({a} - {b})",
        "mul": lambda a, b: f"({a} * {b})",
        "div": lambda a, b: f"({a} / NULLIF({b}, 0))",
        "rank": lambda x: f"PERCENT_RANK() OVER (PARTITION BY date ORDER BY {x})",
        "ts_mean": lambda x: f"AVG({x}) OVER (PARTITION BY code ORDER BY date ROWS BETWEEN {w-1} PRECEDING AND CURRENT ROW)",
        "ts_std": lambda x: f"STDDEV_SAMP({x}) OVER (PARTITION BY code ORDER BY date ROWS BETWEEN {w-1} PRECEDING AND CURRENT ROW)",
        "ts_delta": lambda x: f"({x} - LAG({x}, {w}) OVER (PARTITION BY code ORDER BY date))",
        "ts_pct": lambda x: f"(({x} - LAG({x}, {w}) OVER (PARTITION BY code ORDER BY date)) / NULLIF(LAG({x}, {w}) OVER (PARTITION BY code ORDER BY date), 0))",
        "ts_max": lambda x: f"MAX({x}) OVER (PARTITION BY code ORDER BY date ROWS BETWEEN {w-1} PRECEDING AND CURRENT ROW)",
        "ts_min": lambda x: f"MIN({x}) OVER (PARTITION BY code ORDER BY date ROWS BETWEEN {w-1} PRECEDING AND CURRENT ROW)",
        "ts_sum": lambda x: f"SUM({x}) OVER (PARTITION BY code ORDER BY date ROWS BETWEEN {w-1} PRECEDING AND CURRENT ROW)",
        "abs": lambda x: f"ABS({x})",
        "log": lambda x: f"LN(GREATEST({x}, 1e-12))",
        "sqrt": lambda x: f"SQRT(GREATEST({x}, 0))",
        "sign": lambda x: f"SIGN({x})",
        "neg": lambda x: f"(-{x})",
    }

    sql_gen = sql_map.get(op)
    if sql_gen:
        if op in ("ts_mean", "ts_std", "ts_max", "ts_min", "ts_sum", "ts_delta", "ts_pct", "rank", "abs", "log", "sqrt", "sign", "neg"):
            return sql_gen(child_sqls[0])
        return sql_gen(child_sqls[0], child_sqls[1]) if len(child_sqls) >= 2 else child_sqls[0]

    return child_sqls[0]  # fallback
