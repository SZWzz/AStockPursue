"""Shared utilities for workflow factor and signal nodes."""

from __future__ import annotations

from typing import Any

import pandas as pd


def to_factor_df(value: Any) -> pd.DataFrame:
    """Normalise an input value to a DataFrame (dates × codes).

    Handles:
        - ``None`` → empty DataFrame
        - ``pd.DataFrame`` → passthrough
        - ``dict[str, pd.Series]`` → build panel (e.g. signal dict)
        - anything else → empty DataFrame
    """
    if value is None:
        return pd.DataFrame()
    if isinstance(value, pd.DataFrame):
        return value
    if isinstance(value, dict):
        # May be a {code: Series} dict — try to build a panel
        try:
            df = pd.DataFrame(value)
            return df.ffill() if not df.empty else pd.DataFrame()
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()
