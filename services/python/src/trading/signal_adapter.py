"""Signal adapter – auto-detect strategy capability and route to optimal path.

Strategies that implement ``TickHandler`` run in tick mode (O(n) per bar).
Strategies that only implement ``SignalEngine.generate()`` run in batch
fallback mode, which is backward-compatible with every existing strategy.

Also provides ``OptimizerAdapter`` for online portfolio optimization (Phase 2).
"""

from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

from src.trading.config import MAX_HISTORY as _MAX_HISTORY, EPSILON as _EPSILON


@runtime_checkable
class TickHandler(Protocol):
    """Optional protocol for strategies that support per-bar signal generation."""

    def on_init(self, data_map: dict[str, pd.DataFrame]) -> dict[str, Any]: ...
    def on_bar(self, bar: dict[str, pd.Series], state: dict[str, Any]) -> dict[str, float]: ...


class SignalAdapter:
    """Detect strategy capability and dispatch to the optimal execution path.

    Accepts either a **module** (with ``SignalEngine`` class) or a
    pre-instantiated **engine** instance via keyword argument.
    """

    def __init__(self, signal_module: Any = None, *, engine: Any = None) -> None:
        if engine is not None:
            self._engine = engine
        elif signal_module is not None:
            self._engine = signal_module.SignalEngine()
        else:
            raise ValueError("Either signal_module or engine must be provided")

        if isinstance(self._engine, TickHandler):
            self._mode = "tick"
            logger.info("SignalAdapter: strategy supports TickHandler → tick mode")
        else:
            self._mode = "batch"
            logger.info("SignalAdapter: strategy uses generate() only → batch mode")

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def engine(self) -> Any:
        return self._engine

    # ── Tick-mode path ──────────────────────────────────────────────

    def init_tick(self, data_map: dict[str, pd.DataFrame]) -> dict[str, Any]:
        if self._mode != "tick":
            raise RuntimeError("init_tick called but strategy is not a TickHandler")
        return self._engine.on_init(data_map)

    def on_bar_tick(
        self, bar: dict[str, pd.Series], state: dict[str, Any]
    ) -> dict[str, float]:
        raw = self._engine.on_bar(bar, state)
        return {k: float(v) for k, v in raw.items() if abs(float(v)) > _EPSILON}

    # ── Batch-mode path ─────────────────────────────────────────────

    def init_batch(self, data_map: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
        return {k: v.copy() for k, v in data_map.items()}

    def on_bar_batch(
        self,
        bar: dict[str, pd.Series],
        data_map: dict[str, pd.DataFrame],
        *,
        skip_append: bool = False,
    ) -> dict[str, float]:
        """Generate signal from *existing* data, then optionally append the new bar.

        The strategy never sees the current bar — it only has access to data
        up to the previous bar.  This prevents look-ahead bias by construction:
        the signal that drives execution at bar T is computed from data[0..T-1].

        When ``skip_append=True`` (used by TradingEngine._record_bars), bar
        appending is deferred to the caller, avoiding double-append when the
        engine handles recording separately.
        """
        # 1. Generate signals using only existing data (strategy cannot see new bar)
        signal_map = self._engine.generate(data_map)

        result: dict[str, float] = {}
        for code, series in signal_map.items():
            if len(series) < 1:
                continue
            val = float(series.iloc[-1])
            if pd.isna(val) or abs(val) <= _EPSILON:
                continue
            result[code] = val

        # 2. Append the new bar for future calls (unless caller handles it)
        if not skip_append:
            for code, row in bar.items():
                if code in data_map:
                    df = data_map[code]
                    if hasattr(row, "name") and row.name is not None:
                        ts = row.name
                    elif len(df) > 0:
                        freq = pd.infer_freq(df.index[-5:]) if len(df) >= 3 else None
                        if freq is not None:
                            ts = df.index[-1] + pd.tseries.frequencies.to_offset(freq)
                        else:
                            ts = df.index[-1] + pd.Timedelta(days=1)
                    else:
                        ts = pd.Timestamp.now()
                    new_row = pd.DataFrame([row], index=[ts])
                    data_map[code] = pd.concat([df, new_row])
                    if len(data_map[code]) > _MAX_HISTORY:
                        data_map[code] = data_map[code].iloc[-_MAX_HISTORY:]
                        logger.warning(
                            "Data history for %s truncated to %d bars — "
                            "long-window factors may be affected",
                            code, _MAX_HISTORY,
                        )

        return result

    # ── Unified entry ───────────────────────────────────────────────

    def get_weights(
        self,
        bar: dict[str, pd.Series],
        data_map: dict[str, pd.DataFrame] | None = None,
        tick_state: dict[str, Any] | None = None,
    ) -> dict[str, float]:
        """Get target weights for the current bar.

        In tick mode, uses ``tick_state``. In batch mode, uses ``data_map``.
        """
        if self._mode == "tick":
            return self.on_bar_tick(bar, tick_state or {})
        else:
            if data_map is None:
                return {}
            return self.on_bar_batch(bar, data_map)


# ── Phase 2: Online optimizer adapter ────────────────────────────────────


class OptimizerAdapter:
    """Wrap a portfolio optimizer for online (rolling-window) use.

    Maintains a rolling return history per symbol and applies the optimizer
    to current target weights on each bar.
    """

    def __init__(self, optimizer_name: str, lookback: int = 60, **params: Any) -> None:
        self._lookback = lookback
        self._opt_name = optimizer_name
        self._opt_params = params
        self._prices: dict[str, list[float]] = {}
        self._returns: dict[str, list[float]] = {}

        # Lazy-import the optimizer module
        import importlib
        self._opt_module = importlib.import_module(f"backtest.optimizers.{optimizer_name}")

    def apply(
        self,
        weights: dict[str, float],
        bar: dict[str, pd.Series],
    ) -> dict[str, float]:
        """Update return history and apply optimizer to current weights.

        Args:
            weights: Current raw weights {code: weight}.
            bar: Current bar data {code: Series(open, high, low, close, ...)}.

        Returns:
            Adjusted weights preserving signal signs.
        """
        active = [c for c in weights if abs(weights[c]) > _EPSILON and c in bar]
        if len(active) <= 1:
            return weights

        # Update price/return history
        for code in active:
            price = float(bar[code].get("close", 0))
            if price <= 0:
                continue
            if code not in self._prices:
                self._prices[code] = []
                self._returns[code] = []
            prices = self._prices[code]
            if prices:
                prev = prices[-1]
                if prev > 0:
                    self._returns[code].append(price / prev - 1.0)
            prices.append(price)
            # Trim to lookback
            if len(prices) > self._lookback + 1:
                prices.pop(0)
            if len(self._returns[code]) > self._lookback:
                self._returns[code].pop(0)

        # Build return DataFrame for active symbols
        ret_data: dict[str, list[float]] = {}
        min_len = min((len(self._returns[c]) for c in active if c in self._returns), default=0)
        if min_len < max(self._lookback // 2, 5):
            return weights  # not enough history

        for code in active:
            if code in self._returns and len(self._returns[code]) >= min_len:
                ret_data[code] = self._returns[code][-min_len:]

        if len(ret_data) < 2:
            return weights

        ret_df = pd.DataFrame(ret_data)

        # Build position series for active symbols
        pos_data = {c: [abs(weights[c])] * len(ret_df) for c in active if c in ret_df}
        pos_df = pd.DataFrame(pos_data, index=ret_df.index)

        try:
            dates = pd.DatetimeIndex([pd.Timestamp.now()] * len(ret_df))
            adjusted = self._opt_module.optimize(ret_df, pos_df, dates, **self._opt_params)
            if adjusted is not None and not adjusted.empty:
                last_row = adjusted.iloc[-1]
                result = dict(weights)  # keep inactive symbols unchanged
                for code in active:
                    if code in last_row.index:
                        sign = 1.0 if weights[code] > 0 else -1.0
                        result[code] = sign * abs(float(last_row[code]))
                return result
        except Exception:
            logger.debug("OptimizerAdapter: optimization failed, returning raw weights", exc_info=True)

        return weights
