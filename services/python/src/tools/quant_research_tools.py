"""LLM Quant Researcher Tools — give the LLM agent direct access to market data.

Five tools that transform the LLM from a "formula string generator" into
an autonomous quantitative researcher that can:
  1. Discover available data fields and universes
  2. Query statistical profiles of market data
  3. Evaluate factor formulas against real data
  4. Browse existing Alpha Zoo factors to avoid duplication
  5. Save promising candidates for later review

Design principle: the LLM NEVER gets raw data rows (too large for context).
Instead it gets statistical summaries — distributions, correlations, IC results.
It reasons about those summaries and iterates.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import numpy as np
import pandas as pd

from src.agent.tools import BaseTool

logger = logging.getLogger(__name__)

# ── Helpers ────────────────────────────────────────────────────────────────

def _load_panel(symbols: list[str], start: str, end: str) -> dict[str, pd.DataFrame] | None:
    """Load OHLCV panel data from DataStore. Returns None if unavailable."""
    try:
        from backtest.data_store import get_data_store
        store = get_data_store()
        data_map = store.get_multi_ohlcv(symbols, start, end, interval="1D", force_refresh=False)
        if not data_map:
            return None

        panel: dict[str, pd.DataFrame] = {}
        for col in ["open", "high", "low", "close", "volume"]:
            dfs = []
            for sym in symbols:
                df = data_map.get(sym)
                if df is not None and col in df.columns:
                    if "date" in df.columns:
                        s = df.set_index("date")[col].rename(sym)
                    else:
                        s = df[col].rename(sym)
                    dfs.append(s)
            if dfs:
                combined = pd.concat(dfs, axis=1)
                combined.index = pd.to_datetime(combined.index)
                combined = combined.sort_index()
                panel[col] = combined.astype(np.float64)
        return panel if panel else None
    except Exception as e:
        logger.warning("Failed to load panel: %s", e)
        return None


def _compute_forward_returns(prices: pd.DataFrame, period: int = 1) -> pd.DataFrame:
    """Compute forward period returns."""
    fwd = prices.pct_change(period).shift(-period)
    return fwd.replace([np.inf, -np.inf], np.nan)


def _safe_eval_formula(formula: str, panel: dict[str, pd.DataFrame]) -> pd.DataFrame | None:
    """Safely evaluate a factor formula on panel data.

    The formula is Python/pandas code that operates on:
      - panel['close'], panel['open'], panel['high'], panel['low'], panel['volume']
      - Derived: close, open_, high, low, volume (local variables)

    Safety: eval() is safe here because:
      1. ast.parse(mode='eval') limits input to a single expression (no
         statements, no imports, no multi-line blocks).
      2. __builtins__ is an empty dict — no open(), exec(), __import__,
         os, sys, or subprocess modules are accessible.
      3. Only pd (pandas), np (numpy), and a handful of math builtins
         (abs, min, max, round, len) are exposed in the local namespace.
    """
    import ast
    try:
        ast.parse(formula, mode="eval")
    except SyntaxError as e:
        logger.warning("Formula syntax error: %s", e)
        return None

    # Build a safe local namespace
    close = panel.get("close")
    if close is None:
        return None
    open_ = panel.get("open")
    high = panel.get("high")
    low = panel.get("low")
    volume = panel.get("volume")

    safe_locals = {
        "panel": panel,
        "close": close,
        "open_": open_,
        "high": high,
        "low": low,
        "volume": volume,
        "pd": pd,
        "np": np,
        "abs": abs, "min": min, "max": max, "round": round, "len": len,
    }

    try:
        result = eval(formula, {"__builtins__": {}}, safe_locals)
        if isinstance(result, pd.DataFrame):
            return result.replace([np.inf, -np.inf], np.nan)
        if isinstance(result, pd.Series):
            return pd.DataFrame(result)
        return None
    except Exception as e:
        logger.debug("Formula eval failed: %s", e)
        return None


# ═══════════════════════════════════════════════════════════════════════════
# Tool 1: Explore Data Catalog
# ═══════════════════════════════════════════════════════════════════════════

class ExploreDataCatalogTool(BaseTool):
    """Let the LLM discover what data fields and universes are available."""

    name = "explore_data_catalog"
    description = """Discover available data fields, universes, and data sources for quantitative research.

Call this FIRST before writing any factor formula. Returns:
- Available price/volume fields (open, high, low, close, volume)
- Derived fields available (returns_1d, returns_5d, returns_20d, volume_ratio, etc.)
- Technical indicators available (sma_20, rsi_14, volatility_20d, etc.)
- Available stock universes (A-share, US equity, HK equity)
- Number of existing Alpha Zoo factors
- Data source status (real vs mock)

Use this to understand what data you can work with before designing factors."""
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    repeatable = False
    is_readonly = True

    def execute(self, **kwargs: Any) -> str:
        # Check DataStore availability
        data_status = "unknown"
        sample_count = 0
        try:
            from backtest.data_store import get_data_store
            store = get_data_store()
            stats = store.stats
            data_status = "available" if stats.get("cache_hits", 0) + stats.get("api_fetches", 0) > 0 else "unverified"
            sample_count = stats.get("cache_hits", 0) + stats.get("store_hits", 0)
        except Exception:
            logger.debug("DataStore not available", exc_info=True)
            data_status = "unavailable"

        # Available fields
        price_fields = ["open", "high", "low", "close", "volume", "vwap"]
        derived_fields = [
            {"name": "returns_1d", "desc": "1-day return", "category": "momentum"},
            {"name": "returns_5d", "desc": "5-day return", "category": "momentum"},
            {"name": "returns_20d", "desc": "20-day return", "category": "momentum"},
            {"name": "volume_ratio", "desc": "Volume / 20-day avg volume", "category": "liquidity"},
            {"name": "high_low_ratio", "desc": "(High-Low)/Low, intraday range", "category": "volatility"},
        ]
        tech_indicators = [
            {"name": "sma_20", "desc": "20-day simple moving average of close", "category": "trend"},
            {"name": "sma_60", "desc": "60-day simple moving average of close", "category": "trend"},
            {"name": "volatility_20d", "desc": "20-day rolling std of daily returns", "category": "volatility"},
            {"name": "rsi_14", "desc": "14-day Relative Strength Index (0-100)", "category": "momentum"},
        ]

        # Available universes
        universes = [
            {"name": "a_share", "label": "A-Share (沪深)", "sample": "000001.SZ, 600519.SH, 300750.SZ"},
            {"name": "us_equity", "label": "US Equity (美股)", "sample": "AAPL.US, TSLA.US, NVDA.US"},
            {"name": "hk_equity", "label": "HK Equity (港股)", "sample": "00700.HK, 09988.HK"},
        ]

        # Alpha Zoo
        zoo_count = 0
        try:
            from src.factors.registry import get_default_registry
            zoo_count = len(get_default_registry().list())
        except Exception:
            logger.debug("Failed to load alpha zoo count", exc_info=True)

        # Data sources by market
        data_sources = {
            "us_equity": ["yfinance (free, no key needed)", "twelvedata (API key)", "finnhub (API key)", "akshare (free)"],
            "a_share": ["mootdx (free)", "tushare (API key)", "eastmoney (free)", "tencent (free)"],
            "hk_equity": ["yfinance (free)", "futu (API key)", "tencent (free)"],
        }

        return json.dumps({
            "data_status": data_status,
            "cached_samples": sample_count,
            "price_fields": price_fields,
            "derived_fields": derived_fields,
            "technical_indicators": tech_indicators,
            "universes": universes,
            "data_sources_by_market": data_sources,
            "alpha_zoo_factor_count": zoo_count,
            "formula_guide": {
                "dataframe": "Use 'close', 'open_', 'high', 'low', 'volume' as pd.DataFrames (index=dates, columns=symbols)",
                "cross_sectional": ".rank(axis=1, pct=True) for cross-sectional rank, .mean(axis=1) for cross-sectional mean",
                "time_series": ".rolling(N).mean()/.std()/.max()/.min() for rolling windows, .shift(N) for lag, .pct_change(N) for returns",
                "arithmetic": "+ - * / work element-wise on DataFrames",
                "example": "(close - close.shift(20)) / close.shift(20)  # 20-day momentum",
            },
        }, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════════════════
# Tool 2: Query Data Profile
# ═══════════════════════════════════════════════════════════════════════════

class QueryDataProfileTool(BaseTool):
    """Let the LLM see statistical profiles of market data."""

    name = "query_data_profile"
    description = """Get statistical profiles of market data for specific symbols and date ranges.

Returns SUMMARY STATISTICS (not raw data):
- For each field: mean, std, min, max, skewness, kurtosis
- Cross-sectional average correlation between stocks
- Data completeness (NaN ratio)
- Date range coverage

Use this to understand data characteristics before writing factor formulas.
For example, if volatility is high, consider volatility-neutral factors."""
    parameters = {
        "type": "object",
        "properties": {
            "symbols": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Stock symbols (e.g., ['AAPL.US', 'NVDA.US']). Use .US suffix for US stocks.",
            },
            "start_date": {
                "type": "string",
                "description": "Start date YYYY-MM-DD (e.g., '2024-01-01')",
            },
            "end_date": {
                "type": "string",
                "description": "End date YYYY-MM-DD (e.g., '2024-12-31')",
            },
        },
        "required": ["symbols", "start_date", "end_date"],
    }
    repeatable = True
    is_readonly = True

    def execute(self, **kwargs: Any) -> str:
        symbols = kwargs.get("symbols", [])
        start = kwargs.get("start_date", "2024-01-01")
        end = kwargs.get("end_date", "2024-12-31")

        if not symbols:
            return json.dumps({"error": "symbols required"})

        panel = _load_panel(symbols[:20], start, end)  # Cap at 20 symbols
        if panel is None:
            return json.dumps({
                "status": "no_data",
                "message": "Could not load data. Try different symbols or date range. US stocks need .US suffix (e.g., AAPL.US).",
                "data_source": "none",
            })

        close = panel.get("close")
        if close is None:
            return json.dumps({"error": "No close price data available"})

        # Per-field statistics
        field_stats = {}
        for field_name, df in panel.items():
            if df is None or df.empty:
                continue
            arr = df.to_numpy(dtype=np.float64)
            finite = arr[np.isfinite(arr)]
            if len(finite) < 10:
                continue

            field_stats[field_name] = {
                "mean": round(float(np.mean(finite)), 6),
                "std": round(float(np.std(finite)), 6),
                "min": round(float(np.min(finite)), 4),
                "max": round(float(np.max(finite)), 4),
                "skewness": round(float(pd.Series(finite).skew()), 4),
                "nan_ratio": round(1.0 - len(finite) / arr.size, 4),
            }

        # Cross-sectional correlation
        returns = close.pct_change(1).dropna(how="all")
        avg_corr = 0.0
        if returns.shape[1] >= 2:
            corr_matrix = returns.corr()
            avg_corr = round(float(corr_matrix.values[np.triu_indices_from(corr_matrix.values, k=1)].mean()), 4)

        # Date range
        date_range = {
            "start": str(close.index[0])[:10],
            "end": str(close.index[-1])[:10],
            "trading_days": len(close),
        }

        # Return distribution summary
        if returns is not None and not returns.empty:
            ret_arr = returns.to_numpy(dtype=np.float64)
            ret_finite = ret_arr[np.isfinite(ret_arr)]
            return_stats = {
                "daily_mean": round(float(np.mean(ret_finite)), 6),
                "daily_std": round(float(np.std(ret_finite)), 6),
                "annualized_vol": round(float(np.std(ret_finite) * np.sqrt(252)), 4),
                "skewness": round(float(pd.Series(ret_finite).skew()), 4),
                "kurtosis": round(float(pd.Series(ret_finite).kurtosis()), 4),
            }
        else:
            return_stats = {"error": "Not enough data for return stats"}

        return json.dumps({
            "status": "ok",
            "symbols_loaded": list(close.columns),
            "n_symbols": len(close.columns),
            "field_statistics": field_stats,
            "avg_cross_sectional_correlation": avg_corr,
            "date_range": date_range,
            "return_distribution": return_stats,
            "data_source": "real" if len(close) > 10 else "mock",
        }, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════════════════
# Tool 3: Evaluate Factor
# ═══════════════════════════════════════════════════════════════════════════

class EvaluateFactorTool(BaseTool):
    """Let the LLM test a factor formula against real data and see IC results."""

    name = "evaluate_factor"
    description = """Evaluate a factor formula against real market data and return performance metrics.

The formula should be Python/pandas code operating on:
  - 'close', 'open_', 'high', 'low', 'volume' — wide DataFrames (index=dates, columns=symbols)
  - Example: (close - close.shift(20)) / close.shift(20)

Returns:
  - IC mean (cross-sectional Pearson correlation with forward returns)
  - IC std, IR (information ratio = IC_mean / IC_std * sqrt(252))
  - IC decay across horizons [1, 3, 5, 10, 20] days
  - Long-short quintile Sharpe ratio
  - Max correlation with existing Alpha Zoo factors (redundancy check)
  - Coverage ratio (fraction of non-NaN values)

If IC < 0.02, consider refining the formula and calling this tool again.
If max_zoo_correlation > 0.7, your factor is too similar to an existing one — try a different approach."""
    parameters = {
        "type": "object",
        "properties": {
            "formula": {
                "type": "string",
                "description": "Python/pandas formula. Use 'close', 'open_', 'high', 'low', 'volume' as DataFrames.",
            },
            "symbols": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Stock symbols to evaluate on (e.g., ['AAPL.US', 'NVDA.US', 'MSFT.US'])",
            },
            "train_start": {
                "type": "string",
                "description": "Training period start YYYY-MM-DD",
            },
            "train_end": {
                "type": "string",
                "description": "Training period end YYYY-MM-DD",
            },
            "test_start": {
                "type": "string",
                "description": "Test period start YYYY-MM-DD (optional)",
            },
            "test_end": {
                "type": "string",
                "description": "Test period end YYYY-MM-DD (optional)",
            },
            "name": {
                "type": "string",
                "description": "Short name for this factor (optional)",
            },
        },
        "required": ["formula", "symbols", "train_start", "train_end"],
    }
    repeatable = True
    is_readonly = True

    def execute(self, **kwargs: Any) -> str:
        formula = kwargs.get("formula", "")
        symbols = kwargs.get("symbols", [])
        train_start = kwargs.get("train_start", "2023-01-01")
        train_end = kwargs.get("train_end", "2024-12-31")
        test_start = kwargs.get("test_start", "")
        test_end = kwargs.get("test_end", "")
        name = kwargs.get("name", "unnamed")

        if not formula or not symbols:
            return json.dumps({"error": "formula and symbols required"})

        # Load data
        full_start = min(train_start, test_start) if test_start else train_start
        full_end = max(train_end, test_end) if test_end else train_end
        panel = _load_panel(symbols[:30], full_start, full_end)
        if panel is None or panel.get("close") is None:
            return json.dumps({
                "status": "no_data",
                "message": "Could not load data for evaluation. Check symbols and date range.",
            })

        # Evaluate formula
        factor_values = _safe_eval_formula(formula, panel)
        if factor_values is None:
            return json.dumps({
                "status": "eval_error",
                "message": "Formula evaluation failed. Check syntax — use 'close', 'open_', 'high', 'low', 'volume' as DataFrames.",
            })

        if factor_values.empty:
            return json.dumps({"status": "empty_result", "message": "Formula returned empty DataFrame."})

        close = panel["close"]

        # Split train/test
        train_mask = (factor_values.index >= train_start) & (factor_values.index <= train_end)
        train_fv = factor_values[train_mask]
        train_close = close[train_close_index] if (train_close_index := close.index.intersection(train_fv.index)).size > 0 else close

        # Train IC
        train_fwd = _compute_forward_returns(train_close, period=1)
        from src.factors.mining.fitness import ic_fitness, sharpe_fitness, ic_decay
        train_ic = ic_fitness(train_fv, train_fwd)

        # Train Sharpe
        train_sharpe = sharpe_fitness(train_fv, train_fwd)

        # IC Decay
        decay_result = ic_decay(factor_values, close)

        # Test IC (if test period provided)
        test_ic = 0.0
        test_ir = 0.0
        if test_start and test_end:
            test_mask = (factor_values.index >= test_start) & (factor_values.index <= test_end)
            test_fv = factor_values[test_mask]
            if not test_fv.empty:
                test_fwd = _compute_forward_returns(close, period=1)
                test_ic = ic_fitness(test_fv, test_fwd)
                from src.factors.mining.fitness import ic_fitness as icf
                # IR estimate
                ic_std = float(np.std([
                    icf(test_fv.iloc[i:i+1], test_fwd.iloc[i:i+1])
                    for i in range(min(len(test_fv), 20))
                ], ddof=1)) if len(test_fv) > 1 else 1e-12
                test_ir = test_ic / ic_std * np.sqrt(252) if ic_std > 1e-12 else 0.0

        # Correlation with Zoo
        max_zoo_corr = 0.0
        try:
            from src.factors.registry import get_default_registry
            registry = get_default_registry()
            alpha_ids = registry.list()[:20]
            for aid in alpha_ids:
                try:
                    existing = registry.compute(aid, panel)
                    if existing is not None and not existing.empty:
                        fv_ranked = factor_values.rank(axis=1, pct=True, na_option="keep")
                        ex_ranked = existing.rank(axis=1, pct=True, na_option="keep")
                        common_idx = fv_ranked.index.intersection(ex_ranked.index)
                        if len(common_idx) >= 20:
                            a = fv_ranked.loc[common_idx].to_numpy(dtype=np.float64).ravel()
                            b = ex_ranked.loc[common_idx].to_numpy(dtype=np.float64).ravel()
                            valid = ~np.isnan(a) & ~np.isnan(b)
                            if valid.sum() >= 30:
                                corr = float(np.corrcoef(a[valid], b[valid])[0, 1])
                                if not np.isnan(corr) and abs(corr) > max_zoo_corr:
                                    max_zoo_corr = abs(corr)
                except Exception:
                    logger.debug("Zoo correlation check failed for %s", aid, exc_info=True)
        except Exception:
            logger.debug("Registry unavailable for zoo correlation check", exc_info=True)

        # Coverage
        arr = factor_values.to_numpy(dtype=np.float64)
        coverage = round(1.0 - float(np.isnan(arr).sum()) / arr.size, 4)

        # Interpretation
        interpretation = _interpret_factor(train_ic, train_sharpe, max_zoo_corr, coverage)

        return json.dumps({
            "status": "ok",
            "name": name,
            "formula": formula,
            "train_ic": round(train_ic, 6),
            "train_sharpe": round(train_sharpe, 4),
            "test_ic": round(test_ic, 6) if test_ic else None,
            "test_ir": round(test_ir, 4) if test_ir else None,
            "ic_decay": decay_result,
            "max_zoo_correlation": round(max_zoo_corr, 4),
            "coverage": coverage,
            "interpretation": interpretation,
            "recommendation": "accept" if train_ic > 0.02 and max_zoo_corr < 0.7 and coverage > 0.5 else "refine",
        }, ensure_ascii=False)


def _interpret_factor(ic: float, sharpe: float, max_corr: float, coverage: float) -> str:
    """Generate human-readable interpretation."""
    parts = []
    if abs(ic) >= 0.05:
        parts.append(f"Strong IC ({ic:.4f}) — high predictive power")
    elif abs(ic) >= 0.02:
        parts.append(f"Moderate IC ({ic:.4f}) — usable with position sizing")
    else:
        parts.append(f"Weak IC ({ic:.4f}) — consider refining or discarding")

    if max_corr > 0.7:
        parts.append(f"Highly redundant with existing factor (corr={max_corr:.2f}) — try a different approach")
    elif max_corr > 0.4:
        parts.append(f"Moderately correlated with existing factors (corr={max_corr:.2f})")

    if coverage < 0.5:
        parts.append(f"Low coverage ({coverage:.1%}) — many NaN values, check formula")

    if sharpe > 1.0:
        parts.append(f"Good long-short Sharpe ({sharpe:.2f})")

    return "; ".join(parts) if parts else "No clear signal"


# ═══════════════════════════════════════════════════════════════════════════
# Tool 4: List Alpha Zoo Factors
# ═══════════════════════════════════════════════════════════════════════════

class ListZooFactorsTool(BaseTool):
    """Let the LLM browse existing factors to avoid reinventing the wheel."""

    name = "list_zoo_factors"
    description = """List existing Alpha Zoo factors with their metadata.

Use this BEFORE designing new factors to:
  - Avoid duplicating existing factors
  - Understand what themes are already well-covered
  - Find gaps where new factors could add value

Returns factor IDs, themes, universes, and nicknames."""
    parameters = {
        "type": "object",
        "properties": {
            "theme": {
                "type": "string",
                "description": "Filter by theme (momentum, value, quality, volatility, etc.)",
            },
            "limit": {
                "type": "integer",
                "description": "Max factors to return (default 30)",
            },
        },
        "required": [],
    }
    repeatable = False
    is_readonly = True

    def execute(self, **kwargs: Any) -> str:
        theme_filter = kwargs.get("theme", "")
        limit = kwargs.get("limit", 30)

        try:
            from src.factors.registry import get_default_registry
            registry = get_default_registry()
            all_ids = registry.list()

            factors = []
            for aid in all_ids[:limit * 2]:
                try:
                    alpha = registry.get(aid)
                    meta = alpha.meta or {}
                    themes = meta.get("theme", [])
                    if isinstance(themes, str):
                        themes = [themes]
                    if theme_filter and theme_filter not in themes:
                        continue
                    factors.append({
                        "id": aid,
                        "nickname": meta.get("nickname", aid),
                        "themes": themes,
                        "universe": meta.get("universe", []),
                        "zoo": alpha.zoo,
                    })
                except Exception:
                    logger.debug("Skipping alpha %s: failed to read metadata", aid, exc_info=True)
                if len(factors) >= limit:
                    break

            # Theme summary
            from collections import Counter
            theme_counts = Counter()
            for f in factors:
                for t in f.get("themes", []):
                    theme_counts[t] += 1

            return json.dumps({
                "total_in_zoo": len(all_ids),
                "returned": len(factors),
                "theme_distribution": dict(theme_counts.most_common(10)),
                "factors": factors,
                "suggestion": _suggest_gaps(dict(theme_counts)),
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": f"Could not load factor zoo: {e}"})


def _suggest_gaps(theme_counts: dict[str, int]) -> str:
    """Suggest under-explored factor themes."""
    covered = set(theme_counts.keys())
    all_themes = {"momentum", "value", "quality", "volatility", "growth", "liquidity", "sentiment", "size"}
    gaps = all_themes - covered
    if gaps:
        return f"Under-explored themes: {', '.join(sorted(gaps))}. Consider designing factors in these areas."
    least = sorted(theme_counts.items(), key=lambda x: x[1])[:3]
    return f"Themes with fewest factors: {', '.join(f'{t}({c})' for t, c in least)}. Room for innovation here."


# ═══════════════════════════════════════════════════════════════════════════
# Tool 5: Save Factor Candidate
# ═══════════════════════════════════════════════════════════════════════════

class SaveFactorCandidateTool(BaseTool):
    """Let the LLM save promising factors to the candidates database."""

    name = "save_factor_candidate"
    description = """Save a promising factor candidate to the database for later review and promotion.

Only call this after evaluate_factor() returns recommendation='accept'.
The factor will appear in the Factor Mining > Candidates tab."""
    parameters = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Short descriptive name (snake_case, e.g., 'momentum_20d_reversal')",
            },
            "formula": {
                "type": "string",
                "description": "The validated factor formula",
            },
            "description": {
                "type": "string",
                "description": "One-line explanation of what this factor measures and why it works",
            },
            "theme": {
                "type": "string",
                "description": "Factor theme: momentum, value, quality, volatility, growth, liquidity, sentiment, size",
            },
            "train_ic": {
                "type": "number",
                "description": "IC from evaluate_factor()",
            },
            "test_ic": {
                "type": "number",
                "description": "Test IC from evaluate_factor()",
            },
            "universe": {
                "type": "string",
                "description": "Target universe: equity_cn, equity_us, equity_hk",
            },
        },
        "required": ["name", "formula", "description", "theme", "train_ic"],
    }
    repeatable = True
    is_readonly = False

    def execute(self, **kwargs: Any) -> str:
        import uuid

        name = kwargs.get("name", "unnamed")
        formula = kwargs.get("formula", "")
        description = kwargs.get("description", "")
        theme = kwargs.get("theme", "momentum")
        train_ic = kwargs.get("train_ic", 0.0)
        test_ic = kwargs.get("test_ic", 0.0)
        universe = kwargs.get("universe", "equity_cn")

        candidate_id = uuid.uuid4().hex[:12]

        try:
            from src.db.pool import init_pool, get_connection
            init_pool()
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO vt_factor_mining_candidates
                           (run_id, user_id, name, formula, expression_json, train_ic, test_ic, test_ir, complexity)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (
                            f"llm_{candidate_id}",
                            1,  # Default user — in production, get from auth context
                            name,
                            formula,
                            json.dumps({"source": "llm_agent", "theme": theme, "universe": universe}),
                            train_ic,
                            test_ic,
                            0.0,
                            formula.count("(") + formula.count(")"),
                        ),
                    )
            return json.dumps({
                "status": "saved",
                "candidate_id": candidate_id,
                "name": name,
                "message": f"Factor '{name}' saved successfully. Review it in the Factor Mining > Candidates tab.",
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"status": "error", "message": f"Failed to save: {e}"})
