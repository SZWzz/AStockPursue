"""Restricted pandas proxy for LLM formula sandbox evaluation.

Only whitelisted pandas/numpy functions and methods are accessible.
All I/O operations (read_csv, to_csv, read_parquet, etc.) are blocked.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


class SandboxError(RuntimeError):
    """Raised when sandbox-restricted operations are attempted."""
    pass


_PD_WHITELIST = frozenset({
    # Data structures
    "DataFrame", "Series",
    # Reshaping/combining
    "concat",
    # Rolling/window operations
    "rolling", "shift", "rank", "pct_change", "diff",
    "ewm",
    # Statistics
    "corr", "cov",
    # Cumulative
    "cumsum", "cumprod", "cummin", "cummax",
})


_NP_WHITELIST = frozenset({
    "abs", "sqrt", "log", "exp", "sign", "clip", "where",
    "maximum", "minimum",
    "nan_to_num", "isnan", "isinf", "isfinite",
    "mean", "std", "sum", "min", "max", "median",
    "corrcoef", "percentile",
})


class SandboxPandas:
    """Whitelist-only pandas proxy.

    Only explicitly whitelisted functions are accessible.
    I/O methods (read_csv, to_csv, read_parquet, etc.) are blocked.
    """

    def __init__(self) -> None:
        object.__setattr__(self, "_pd", pd)

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise SandboxError(f"Access to pandas.{name} is not allowed in sandbox")
        if name in ("read_csv", "read_parquet", "read_excel", "read_json",
                     "read_sql", "read_html", "read_clipboard", "read_pickle",
                     "read_feather", "read_hdf", "read_stata", "read_sas",
                     "read_spss", "read_table", "read_fwf", "DataFrame.to_csv",
                     "DataFrame.to_parquet", "DataFrame.to_excel", "DataFrame.to_json",
                     "DataFrame.to_sql", "DataFrame.to_pickle", "DataFrame.to_feather"):
            raise SandboxError(f"pandas I/O method '{name}' is blocked in sandbox")
        if name not in _PD_WHITELIST:
            raise SandboxError(f"pandas.{name} is not allowed in formula sandbox")
        return getattr(self._pd, name)


class SandboxNumpy:
    """Whitelist-only numpy proxy for formula evaluation."""

    def __init__(self) -> None:
        object.__setattr__(self, "_np", np)

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise SandboxError(f"Access to numpy.{name} is not allowed in sandbox")
        if name not in _NP_WHITELIST:
            raise SandboxError(f"numpy.{name} is not allowed in formula sandbox")
        return getattr(self._np, name)

