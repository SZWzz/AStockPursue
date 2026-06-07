"""Cross-asset correlation matrix computation.

Computes pairwise Pearson or Spearman correlation of daily returns
over a configurable lookback window. Used by the /correlation API endpoint.
"""

from __future__ import annotations

from typing import Dict, Literal

import pandas as pd
import numpy as np
from scipy.stats import spearmanr


def normalize_code(code: str) -> str:
    """Normalize a ticker symbol by adding exchange suffix for A-shares.

    - 6-digit codes starting with 6 → .SH (Shanghai)
    - 6-digit codes starting with 0 or 3 → .SZ (Shenzhen)
    - Codes already with exchange suffix → keep as-is
    """
    code = code.strip().upper()
    if "." in code:
        return code
    if len(code) == 6 and code.isdigit():
        if code[0] in ("6", "5"):
            return f"{code}.SH"
        return f"{code}.SZ"
    return code


def infer_market(code: str) -> str:
    """Infer market key from a ticker symbol."""
    code_upper = normalize_code(code).upper()
    crypto_suffixes = ("USDT", "BTC", "ETH", "BNB", "SOL", "ADA", "DOGE")
    if any(code_upper.endswith(s) for s in crypto_suffixes) or "/" in code:
        return "crypto"
    if code_upper.endswith(".HK"):
        return "hk_equity"
    if code_upper.endswith((".SH", ".SZ", ".BJ")):
        return "a_share"
    if code_upper.startswith(("6", "000", "001", "002")):
        return "a_share"
    if code_upper.startswith(("0", "399")):
        return "a_share"
    if code_upper.startswith(("0", "1", "2", "3", "4")):
        return "hk_equity"
    return "us_equity"


def _rolling_correlation_matrix(
    price_series: Dict[str, pd.DataFrame],
    window: int,
    method: Literal["pearson", "spearman"],
) -> tuple[list[str], list[list[float]]]:
    """Compute correlation matrix for multiple price series.

    Delegates pure computation to CorrelationEngine.
    """
    from src.services.correlation_engine import CorrelationEngine

    if not price_series:
        return [], []

    codes = sorted(price_series.keys())

    # Build aligned returns DataFrame
    closes = {}
    for code, df in price_series.items():
        if df.empty:
            raise ValueError(f"Price series for '{code}' is empty")
        if "close" not in df.columns and "close" not in df.index.names:
            raise ValueError(f"No 'close' column in price series for '{code}'")
        if "trade_date" in df.index.names and "trade_date" not in df.columns:
            ts = df["close"]
        else:
            ts = df.set_index("trade_date")["close"]
        closes[code] = ts.sort_index()

    returns_frames = []
    for code in codes:
        rets = closes[code].pct_change().dropna()
        rets.name = code
        returns_frames.append(rets)

    aligned = pd.concat(returns_frames, axis=1).dropna()
    if aligned.empty:
        raise ValueError("No overlapping return data between assets")

    if len(aligned) < 2:
        raise ValueError("Not enough data points to compute correlation")

    engine = CorrelationEngine()
    return engine.compute_from_returns(aligned, method=method, window=window)


def compute_correlation_matrix(
    codes: list[str],
    days: int = 90,
    method: Literal["pearson", "spearman"] = "pearson",
) -> Dict[str, object]:
    """Fetch price data and compute correlation matrix for a list of assets.

    Args:
        codes: List of asset codes (e.g. ["BTC-USDT", "ETH-USDT", "SPY"]).
        days: Lookback window in days (default 90).
        method: Correlation method.

    Returns:
        Dict with keys: labels, matrix, window, method.
    """
    from datetime import datetime, timedelta

    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days + 60)).strftime("%Y-%m-%d")

    # Import here to avoid circular
    from backtest.loaders.registry import resolve_loader

    price_series: Dict[str, pd.DataFrame] = {}

    failed: list[str] = []
    for code in codes:
        normalized = normalize_code(code)
        market = infer_market(normalized)
        try:
            loader = resolve_loader(market)
        except Exception:
            try:
                from backtest.loaders.registry import LOADER_REGISTRY
                if "yfinance" in LOADER_REGISTRY:
                    loader = LOADER_REGISTRY["yfinance"]()
                else:
                    failed.append(f"{code} (no loader for {market})")
                    continue
            except Exception:
                failed.append(f"{code} (no loader for {market})")
                continue

        try:
            result = loader.fetch(
                codes=[normalized],
                start_date=start_date,
                end_date=end_date,
                interval="1D",
                fields=["trade_date", "open", "high", "low", "close", "volume"],
            )
            if normalized in result and not result[normalized].empty:
                price_series[code] = result[normalized]
            else:
                failed.append(f"{code} (fetched 0 rows)")
        except Exception as e:
            failed.append(f"{code} ({e})")
            continue

    if len(price_series) < 2:
        detail = "; ".join(failed[:10]) if failed else "no data"
        tip = ""
        if any(c.endswith((".SH", ".SZ")) for c in codes):
            tip = " | Tip: set TUSHARE_TOKEN in .env for stable A-share data, or try US stocks (AAPL, MSFT)"
        raise ValueError(
            f"Could not fetch data for at least 2 assets. Fetched: {list(price_series.keys())}. Failed: [{detail}].{tip}"
        )

    labels, matrix = _rolling_correlation_matrix(price_series, days, method)
    return {
        "labels": labels,
        "matrix": matrix,
        "window": days,
        "method": method,
    }