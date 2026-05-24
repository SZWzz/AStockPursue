"""Indicator Lab: user-facing indicator IDE for rapid strategy prototyping.

Provides sandboxed execution, parameter parsing, code quality analysis,
and a file-based indicator repository — all compatible with the Alpha Zoo.
"""

from src.lab.sandbox import (
    build_safe_builtins,
    safe_exec_code,
    safe_exec_isolated,
    safe_exec_with_validation,
    validate_code_safety,
    SAFE_IMPORT_MODULES,
)
from src.lab.params import IndicatorParamsParser, StrategyConfigParser
from src.lab.quality import analyze_indicator_code_quality
from src.lab.repository import IndicatorRepository
from src.lab.backtest_bridge import (
    LabSignalEngine,
    extract_weight_series,
    fetch_ohlcv,
    run_indicator_backtest,
)

__all__ = [
    # sandbox
    "build_safe_builtins",
    "safe_exec_code",
    "safe_exec_isolated",
    "safe_exec_with_validation",
    "validate_code_safety",
    "SAFE_IMPORT_MODULES",
    # params
    "IndicatorParamsParser",
    "StrategyConfigParser",
    # quality
    "analyze_indicator_code_quality",
    # repository
    "IndicatorRepository",
    # backtest bridge
    "LabSignalEngine",
    "extract_weight_series",
    "fetch_ohlcv",
    "run_indicator_backtest",
]
