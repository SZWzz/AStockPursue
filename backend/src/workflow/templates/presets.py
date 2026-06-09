"""Pre-built workflow pipeline presets — complete DAG templates.

Each preset is a function that returns a WorkflowModel with fully wired nodes
and edges.  These represent end-to-end quant research pipelines that users
can instantiate with one click.

Mapped to actual registered node types:
  stock_universe, ohlcv_loader, alpha_zoo, strategy, backtest, report,
  attribution, correlation, gp_evolution, factor_to_strategy, rank_select,
  signal_weight, rebalance, comparison, consistency_check, walk_forward.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List

from src.workflow.schema import WorkflowEdge, WorkflowModel, WorkflowNodeData


def _uid() -> str:
    return str(uuid.uuid4())


def _node(nid: str, node_type: str, label: str, x: float, y: float,
          config: Dict[str, Any] | None = None) -> WorkflowNodeData:
    return WorkflowNodeData(
        id=nid, node_type=node_type, label=label,
        position={"x": x, "y": y}, config=config or {},
    )


def _edge(src: str, src_port: str, tgt: str, tgt_port: str) -> WorkflowEdge:
    return WorkflowEdge(source=src, source_port=src_port, target=tgt, target_port=tgt_port)


# ── 1. Momentum Strategy ──────────────────────────────────────────────────

def momentum_strategy() -> WorkflowModel:
    """StockUniverse → OHLCVLoader → AlphaZoo(momentum) → Strategy → Backtest → Report.

    A classic momentum strategy: select a stock universe, load price data,
    compute a momentum factor, generate signals via a built-in template,
    backtest, and produce a summary report.
    """
    nodes = [
        _node("universe", "stock_universe", "CSI 300", 0, 200,
              {"preset": "csi300"}),
        _node("loader", "ohlcv_loader", "Load OHLCV", 260, 200,
              {"start_date": "2024-01-01", "end_date": "2025-12-31", "interval": "1D"}),
        _node("alpha", "alpha_zoo", "Momentum (α101)", 520, 200,
              {"zoo": "alpha101", "alpha_id": ""}),
        _node("strategy", "strategy", "Momentum Top 5", 780, 200,
              {"strategy_source": "template", "strategy_template": "momentum_top5", "top_n": 5}),
        _node("backtest", "backtest", "Backtest", 1040, 200,
              {"market": "equity_cn", "interval": "1D", "initial_capital": 1000000}),
        _node("report", "report", "PDF Report", 1300, 200,
              {"title": "Momentum Strategy Report", "format": "markdown"}),
    ]
    edges = [
        _edge("universe", "codes", "loader", "codes"),
        _edge("loader", "ohlcv_data", "alpha", "ohlcv_data"),
        _edge("loader", "ohlcv_data", "strategy", "ohlcv_data"),
        _edge("alpha", "factor", "strategy", "factor_data"),
        _edge("strategy", "signal", "backtest", "signal"),
        _edge("loader", "ohlcv_data", "backtest", "ohlcv_data"),
        _edge("backtest", "backtest_result", "report", "data"),
    ]
    return WorkflowModel(
        id=_uid(), name="Momentum Strategy",
        description="Classic momentum: factor ranking → top-N selection → monthly rebalance",
        nodes=nodes, edges=edges,
    )


# ── 2. Mean Reversion Strategy ────────────────────────────────────────────

def mean_reversion_strategy() -> WorkflowModel:
    """StockUniverse → OHLCVLoader → AlphaZoo(RSI) → Strategy → Backtest → Attribution.

    RSI-based mean reversion: buy oversold, sell overbought, with full
    attribution analysis for performance decomposition.
    """
    nodes = [
        _node("universe", "stock_universe", "CSI 300", 0, 200,
              {"preset": "csi300"}),
        _node("loader", "ohlcv_loader", "Load OHLCV", 260, 200,
              {"start_date": "2024-01-01", "end_date": "2025-12-31", "interval": "1D"}),
        _node("alpha", "alpha_zoo", "RSI Factor", 520, 200,
              {"zoo": "alpha101", "alpha_id": ""}),
        _node("strategy", "strategy", "Mean Reversion", 780, 200,
              {"strategy_source": "template", "strategy_template": "momentum_top5"}),
        _node("backtest", "backtest", "Backtest", 1040, 200,
              {"market": "equity_cn", "interval": "1D", "initial_capital": 1000000}),
        _node("attribution", "attribution", "Attribution Analysis", 1300, 200,
              {"classification": "sw", "methods": "all"}),
        _node("report", "report", "Report", 1560, 200,
              {"title": "Mean Reversion Report", "format": "markdown"}),
    ]
    edges = [
        _edge("universe", "codes", "loader", "codes"),
        _edge("loader", "ohlcv_data", "alpha", "ohlcv_data"),
        _edge("loader", "ohlcv_data", "strategy", "ohlcv_data"),
        _edge("alpha", "factor", "strategy", "factor_data"),
        _edge("strategy", "signal", "backtest", "signal"),
        _edge("loader", "ohlcv_data", "backtest", "ohlcv_data"),
        _edge("backtest", "backtest_result", "attribution", "backtest_result"),
        _edge("backtest", "backtest_result", "report", "data"),
    ]
    return WorkflowModel(
        id=_uid(), name="Mean Reversion Strategy",
        description="RSI oversold/overbought mean reversion with Brinson attribution",
        nodes=nodes, edges=edges,
    )


# ── 3. Multi-Factor Strategy ──────────────────────────────────────────────

def multi_factor_strategy() -> WorkflowModel:
    """StockUniverse → OHLCVLoader → AlphaZoo(multiple) → Strategy → Backtest → Attribution → Report.

    Multi-factor composite: compute momentum + volatility factors,
    z-score standardise, equal-weight combine, rank, and backtest.
    """
    nodes = [
        _node("universe", "stock_universe", "CSI 300", 0, 300,
              {"preset": "csi300"}),
        _node("loader", "ohlcv_loader", "Load OHLCV", 260, 300,
              {"start_date": "2024-01-01", "end_date": "2025-12-31", "interval": "1D"}),
        _node("alpha_mom", "alpha_zoo", "Momentum Factor", 520, 200,
              {"zoo": "alpha101", "alpha_id": ""}),
        _node("alpha_vol", "alpha_zoo", "Volatility Factor", 520, 400,
              {"zoo": "alpha101", "alpha_id": ""}),
        _node("strategy", "strategy", "Multi-Factor Composite", 780, 300,
              {"strategy_source": "template", "strategy_template": "momentum_top5", "top_n": 10}),
        _node("backtest", "backtest", "Backtest", 1040, 300,
              {"market": "equity_cn", "interval": "1D", "initial_capital": 1000000}),
        _node("attribution", "attribution", "Attribution", 1300, 300,
              {"classification": "sw", "methods": "all"}),
        _node("report", "report", "Report", 1560, 300,
              {"title": "Multi-Factor Strategy Report", "format": "markdown"}),
    ]
    edges = [
        _edge("universe", "codes", "loader", "codes"),
        _edge("loader", "ohlcv_data", "alpha_mom", "ohlcv_data"),
        _edge("loader", "ohlcv_data", "alpha_vol", "ohlcv_data"),
        _edge("loader", "ohlcv_data", "strategy", "ohlcv_data"),
        _edge("alpha_mom", "factor", "strategy", "factor_data"),
        _edge("strategy", "signal", "backtest", "signal"),
        _edge("loader", "ohlcv_data", "backtest", "ohlcv_data"),
        _edge("backtest", "backtest_result", "attribution", "backtest_result"),
        _edge("attribution", "attribution_report", "report", "data"),
    ]
    return WorkflowModel(
        id=_uid(), name="Multi-Factor Strategy",
        description="Multi-factor composite: momentum + volatility → z-score → equal weight",
        nodes=nodes, edges=edges,
    )


# ── 4. Pair Trading Strategy ──────────────────────────────────────────────

def pair_trading_strategy() -> WorkflowModel:
    """StockUniverse(2) → OHLCVLoader → Correlation → Strategy → Backtest → Comparison.

    Statistical pair trading: select two co-integrated stocks, compute
    correlation, generate spread-based signals, and compare against
    benchmark.
    """
    nodes = [
        _node("universe", "stock_universe", "2 Stocks", 0, 200,
              {"preset": "custom", "custom_codes": "600519.SH,000858.SZ"}),
        _node("loader", "ohlcv_loader", "Load OHLCV", 260, 200,
              {"start_date": "2024-01-01", "end_date": "2025-12-31", "interval": "1D"}),
        _node("correlation", "correlation", "Correlation Check", 520, 200,
              {"method": "pearson", "lookback_days": 60}),
        _node("strategy", "strategy", "Pairs Strategy", 780, 200,
              {"strategy_source": "template", "strategy_template": "momentum_top5"}),
        _node("backtest", "backtest", "Backtest", 1040, 200,
              {"market": "equity_cn", "interval": "1D", "initial_capital": 1000000}),
        _node("comparison", "comparison", "vs Benchmark", 1300, 200),
        _node("report", "report", "Report", 1560, 200,
              {"title": "Pair Trading Report", "format": "markdown"}),
    ]
    edges = [
        _edge("universe", "codes", "loader", "codes"),
        _edge("loader", "ohlcv_data", "correlation", "ohlcv_data"),
        _edge("loader", "ohlcv_data", "strategy", "ohlcv_data"),
        _edge("strategy", "signal", "backtest", "signal"),
        _edge("loader", "ohlcv_data", "backtest", "ohlcv_data"),
        _edge("backtest", "backtest_result", "comparison", "backtest_result"),
        _edge("backtest", "backtest_result", "report", "data"),
    ]
    return WorkflowModel(
        id=_uid(), name="Pair Trading Strategy",
        description="Statistical pair trading: correlation-based pair selection with spread signals",
        nodes=nodes, edges=edges,
    )


# ── 5. Factor Mining Pipeline ─────────────────────────────────────────────

def factor_mining_pipeline() -> WorkflowModel:
    """StockUniverse → OHLCVLoader → GP Evolution → Attribution → Report.

    Automated factor discovery using Genetic Programming: evolve alpha
    factors via GP, evaluate IC, and produce a report with the best
    discovered factors.
    """
    nodes = [
        _node("universe", "stock_universe", "CSI 300", 0, 200,
              {"preset": "csi300"}),
        _node("loader", "ohlcv_loader", "Load OHLCV", 260, 200,
              {"start_date": "2024-01-01", "end_date": "2025-12-31", "interval": "1D"}),
        _node("evolution", "gp_evolution", "GP Factor Mining", 520, 200,
              {"population_size": 100, "generations": 50, "train_start": "2024-01-01",
               "train_end": "2025-06-30", "test_start": "2025-07-01", "test_end": "2025-12-31"}),
        _node("report", "report", "Mining Report", 780, 200,
              {"title": "GP Factor Mining Report", "format": "markdown"}),
    ]
    edges = [
        _edge("universe", "codes", "loader", "codes"),
        _edge("loader", "ohlcv_data", "evolution", "ohlcv_data"),
        _edge("evolution", "best_factors", "report", "data"),
    ]
    return WorkflowModel(
        id=_uid(), name="Factor Mining Pipeline",
        description="GP-based alpha factor discovery with walk-forward OOS validation",
        nodes=nodes, edges=edges,
    )


# ── Registry ───────────────────────────────────────────────────────────────

PRESET_FACTORIES: Dict[str, Any] = {
    "momentum_strategy": momentum_strategy,
    "mean_reversion_strategy": mean_reversion_strategy,
    "multi_factor_strategy": multi_factor_strategy,
    "pair_trading_strategy": pair_trading_strategy,
    "factor_mining_pipeline": factor_mining_pipeline,
}

PRESET_META: List[Dict[str, str]] = [
    {"id": "momentum_strategy", "name": "Momentum Strategy",
     "description": "Factor ranking → top-N selection → monthly rebalance → backtest + report"},
    {"id": "mean_reversion_strategy", "name": "Mean Reversion Strategy",
     "description": "RSI oversold/overbought with full attribution analysis"},
    {"id": "multi_factor_strategy", "name": "Multi-Factor Strategy",
     "description": "Momentum + volatility composite with z-score standardisation"},
    {"id": "pair_trading_strategy", "name": "Pair Trading Strategy",
     "description": "Correlation-based pairs with spread signals and benchmark comparison"},
    {"id": "factor_mining_pipeline", "name": "Factor Mining Pipeline",
     "description": "GP evolution for automated alpha factor discovery"},
]


def list_presets() -> List[Dict[str, str]]:
    """Return metadata for all available pipeline presets."""
    return PRESET_META


def load_preset(preset_id: str) -> WorkflowModel | None:
    """Build a WorkflowModel from a preset ID. Returns None if unknown."""
    factory = PRESET_FACTORIES.get(preset_id)
    if factory:
        return factory()
    return None
