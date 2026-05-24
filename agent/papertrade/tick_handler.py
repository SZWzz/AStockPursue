"""Signal bridge – auto-detect strategy capability and route to optimal path.

Strategies that implement ``TickHandler`` run in tick mode (O(n) per bar).
Strategies that only implement ``SignalEngine.generate()`` run in batch
fallback mode (O(history) per bar), which is backward-compatible with
every existing strategy.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from papertrade.models import TickHandler

logger = logging.getLogger(__name__)

# Signal too close to zero to act on
_EPSILON = 1e-9


class SignalBridge:
    """Detect strategy capability and dispatch to the optimal execution path."""

    def __init__(self, signal_module: Any) -> None:
        """Instantiate the strategy's SignalEngine and probe for TickHandler.

        Args:
            signal_module: A Python module containing a ``SignalEngine`` class.
        """
        self._engine: Any = signal_module.SignalEngine()
        self._module = signal_module

        if isinstance(self._engine, TickHandler):
            self._mode = "tick"
            logger.info("SignalBridge: strategy supports TickHandler → tick mode")
        else:
            self._mode = "batch"
            logger.info("SignalBridge: strategy uses generate() only → batch mode")

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def engine(self) -> Any:
        return self._engine

    # ── Tick-mode path ──────────────────────────────────────────────

    def init_tick(self, data_map: dict[str, pd.DataFrame]) -> dict[str, Any]:
        """Warmup for tick mode: call ``on_init`` with historical bars."""
        if self._mode != "tick":
            raise RuntimeError("init_tick called but strategy is not a TickHandler")
        return self._engine.on_init(data_map)

    def on_bar_tick(
        self, bar: dict[str, pd.Series], state: dict[str, Any]
    ) -> dict[str, float]:
        """Process one bar via TickHandler.on_bar."""
        raw = self._engine.on_bar(bar, state)
        return {k: float(v) for k, v in raw.items() if abs(float(v)) > _EPSILON}

    # ── Batch-mode path ─────────────────────────────────────────────

    def init_batch(self, data_map: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
        """Store initial data_map for batch mode."""
        # Deep-copy DataFrames so the engine owns its copy
        return {k: v.copy() for k, v in data_map.items()}

    def on_bar_batch(
        self,
        bar: dict[str, pd.Series],
        data_map: dict[str, pd.DataFrame],
    ) -> dict[str, float]:
        """Batch fallback: append new bar, call generate(), extract last confirmed signal.

        Returns the signal from the **second-to-last** bar (confirmed bar),
        matching the ``_align()`` shift(1) semantics in the backtest engine.
        """
        # 1. Append new bar to each code's DataFrame
        for code, row in bar.items():
            if code in data_map:
                df = data_map[code]
                new_row = pd.DataFrame([row])
                new_row.index = [row.name] if hasattr(row, "name") else [pd.Timestamp.now()]
                data_map[code] = pd.concat([df, new_row])

        # 2. Call generate() with full history
        signal_map = self._engine.generate(data_map)

        # 3. Extract last confirmed signal (index -2) per code
        result: dict[str, float] = {}
        for code, series in signal_map.items():
            if len(series) < 2:
                continue
            val = series.iloc[-2]
            if pd.isna(val) or abs(float(val)) <= _EPSILON:
                continue
            result[code] = float(val)

        return result
