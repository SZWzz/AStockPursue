"""Base backtest engine with shared bar-by-bar execution loop.

All market engines inherit from BaseEngine and override market-rule methods.
The shared run_backtest() handles: data loading → signal generation →
pre-compute target weights (with optimizer) → bar-by-bar execution with
market rule enforcement → metrics → artifacts.
"""

from __future__ import annotations

import importlib
import json
import logging
import re as _re
import sys
from abc import ABC, abstractmethod
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import pandas as pd

from backtest.loaders.tushare_fundamentals import (
    TushareFundamentalProvider,
    enrich_price_frames_with_fundamentals,
)
from backtest.metrics import (
    by_exit_reason_stats,
    by_symbol_stats,
    calc_metrics,
)
from backtest.models import Position, TradeRecord

logger = logging.getLogger(__name__)


def _run_card_data_sources(config: Dict[str, Any], loader: Any) -> List[str]:
    """Return source names for run-card evidence."""
    configured = config.get("_run_card_effective_sources")
    if isinstance(configured, list):
        return [str(source) for source in configured if str(source).strip()]
    if isinstance(configured, str) and configured.strip():
        return [configured.strip()]

    loader_name = getattr(loader, "name", None)
    if loader_name:
        return [str(loader_name)]

    source = config.get("source")
    return [str(source)] if source else []


# ─── Market detection (lightweight, for signal alignment only) ───

_CRYPTO_RE = _re.compile(r"^[A-Z]+-USDT$|^[A-Z]+/USDT$", _re.I)
_FOREX_RE = _re.compile(r"^[A-Z]{3}/[A-Z]{3}$|^[A-Z]{6}\.FX$")


def _detect_market_for_align(code: str) -> str:
    """Lightweight market detection for ffill_limit calculation."""
    if _CRYPTO_RE.match(code):
        return "crypto"
    if _FOREX_RE.match(code):
        return "forex"
    return "equity"


# ─── Signal alignment (reused from daily_portfolio logic) ───


def _align(
    data_map: Dict[str, pd.DataFrame],
    signal_map: Dict[str, pd.Series],
    codes: List[str],
    optimizer: Optional[Callable] = None,
) -> tuple:
    """Build aligned date index, close matrix, target-position matrix, return matrix.

    Signal is shifted by 1 bar (next-bar-open semantics) then normalised so
    ``sum(abs(weights)) <= 1.0``.

    Args:
        data_map: code -> OHLCV DataFrame.
        signal_map: code -> signal Series.
        codes: Valid instrument codes.
        optimizer: Optional weight optimiser ``(ret, pos, dates) -> pos``.

    Returns:
        (dates, close_df, positions_df, returns_df)
    """
    all_dates: set = set()
    for c in codes:
        all_dates.update(data_map[c].index)
    dates = pd.DatetimeIndex(sorted(all_dates))

    close = pd.DataFrame(index=dates, columns=codes, dtype=float)
    for c in codes:
        close[c] = data_map[c]["close"].reindex(dates)

    # ffill with limit to avoid masking long suspensions (e.g. 3-week halt)
    # Cross-market needs larger limit (Chinese New Year can be 9-10 bars)
    ffill_limit = 10 if len({_detect_market_for_align(c) for c in codes}) > 1 else 5
    close = close.ffill(limit=ffill_limit)

    # Drop symbols that are entirely NaN (no data overlap with date range)
    all_nan_cols = [c for c in codes if close[c].isna().all()]
    if all_nan_cols:
        logger.warning("Symbols dropped (no usable price data): %s", all_nan_cols)
        codes = [c for c in codes if c not in all_nan_cols]
        if not codes:
            raise ValueError("All symbols have no data in the requested date range")
        close = close[codes]

    # Track skipped bars for audit log
    skipped_bars: int = 0

    pos = pd.DataFrame(0.0, index=dates, columns=codes)
    for c in codes:
        # Shift on each symbol's OWN trading calendar, then reindex to unified.
        # NO ffill on positions — a non-trading day means we hold zero position
        # (cannot enter/exit a suspended stock).  This prevents survivorship-bias
        # leakage where a strategy "holds" through a multi-week suspension.
        own_dates = data_map[c].index
        raw = signal_map[c].reindex(own_dates).fillna(0.0).clip(-1.0, 1.0)
        shifted = raw.shift(1).fillna(0.0)
        reindexed = shifted.reindex(dates)
        nan_count = int(reindexed.isna().sum())
        if nan_count > 0:
            skipped_bars += nan_count
            logger.debug("Symbol %s: %d non-trading bars zeroed", c, nan_count)
        pos[c] = reindexed.fillna(0.0)

    if skipped_bars > 0:
        logger.info("Position alignment: %d non-trading bar(s) zeroed across all symbols", skipped_bars)

    ret = close.pct_change().fillna(0.0)

    if optimizer is not None:
        pos = optimizer(ret, pos, dates)

    scale = pos.abs().sum(axis=1).clip(lower=1.0)
    pos = pos.div(scale, axis=0)

    return dates, close, pos, ret


def _load_optimizer(config: Dict[str, Any]) -> Optional[Callable]:
    """Dynamically load an optimizer function from config.

    Args:
        config: Backtest configuration.

    Returns:
        Optimizer callable, or None.
    """
    opt_name = config.get("optimizer")
    if not opt_name:
        return None
    opt_params = config.get("optimizer_params") or {}
    try:
        mod = importlib.import_module(f"backtest.optimizers.{opt_name}")
        return lambda ret, pos, dates: mod.optimize(ret, pos, dates, **opt_params)
    except (ImportError, AttributeError) as e:
        logger.warning("Failed to load optimizer '%s': %s, falling back to equal weight", opt_name, e)
        return None


def _normalise_fundamental_fields(config: Dict[str, Any]) -> dict[str, list[str]]:
    """Read the optional statement-table field map from backtest config."""
    raw_fields = config.get("fundamental_fields")
    if raw_fields in (None, {}):
        return {}
    if not isinstance(raw_fields, dict):
        raise ValueError("fundamental_fields must map table names to field-name lists")

    normalized: dict[str, list[str]] = {}
    for table, fields in raw_fields.items():
        if not isinstance(table, str) or not table.strip():
            raise ValueError("fundamental_fields table names must be non-empty strings")
        if fields is None:
            continue
        if isinstance(fields, str) or not isinstance(fields, Iterable):
            raise ValueError(f"fundamental_fields[{table!r}] must be a list of field names")

        field_list = list(fields)
        if not field_list:
            continue
        invalid = [field for field in field_list if not isinstance(field, str) or not field.strip()]
        if invalid:
            raise ValueError(f"fundamental_fields[{table!r}] contains invalid field names")
        normalized[table.strip()] = field_list
    return normalized


def _maybe_enrich_fundamentals(
    data_map: Dict[str, pd.DataFrame],
    config: Dict[str, Any],
) -> Dict[str, pd.DataFrame]:
    """Attach configured Tushare statement fields before signal generation."""
    fields_by_table = _normalise_fundamental_fields(config)
    if not fields_by_table:
        return data_map

    try:
        provider = TushareFundamentalProvider()
        return enrich_price_frames_with_fundamentals(
            data_map,
            provider,
            fields_by_table,
            as_of=config.get("end_date", ""),
            periods=config.get("fundamental_periods"),
        )
    except Exception as exc:
        raise RuntimeError(
            f"fundamental_fields requested but Tushare enrichment failed: {exc}"
        ) from exc


# ─── Base Engine ───


class BaseEngine(ABC):
    """Abstract base for all market engines.

    Subclasses override market-rule methods:
      - can_execute: whether a trade is allowed by market rules
      - round_size: lot-size rounding
      - calc_commission: fee structure
      - apply_slippage: slippage model
      - on_bar: per-bar hooks (funding fees, liquidation, etc.)
    """

    def __init__(self, config: dict):
        self.config = config
        self.initial_capital: float = config.get("initial_cash", 1_000_000)
        self.default_leverage: float = config.get("leverage", 1.0)
        self.capital: float = self.initial_capital
        self.positions: Dict[str, Position] = {}
        self.trades: List[TradeRecord] = []
        self.equity_snapshots: List[EquitySnapshot] = []
        self._bar_idx: int = 0
        self._active_symbol: str = ""  # set by _rebalance/_close_position for subclass use

    # ── Market rule interface (subclass must implement) ──

    @abstractmethod
    def can_execute(self, symbol: str, direction: int, bar: pd.Series) -> bool:
        """Whether market rules allow this trade.

        Args:
            symbol: Instrument identifier.
            direction: 1 (long), -1 (short), 0 (close).
            bar: Current bar data (OHLCV + extras).

        Returns:
            True if allowed.
        """

    @abstractmethod
    def round_size(self, raw_size: float, price: float) -> float:
        """Round position size per market lot rules.

        Args:
            raw_size: Desired size.
            price: Current price.

        Returns:
            Rounded size.
        """

    @abstractmethod
    def calc_commission(self, size: float, price: float, direction: int, is_open: bool) -> float:
        """Calculate commission for a trade.

        Args:
            size: Trade size.
            price: Execution price.
            direction: 1 or -1.
            is_open: True for opening, False for closing.

        Returns:
            Commission amount.
        """

    @abstractmethod
    def apply_slippage(self, price: float, direction: int) -> float:
        """Apply slippage to execution price.

        Args:
            price: Raw price.
            direction: 1 (buying / covering short) or -1 (selling / shorting).

        Returns:
            Slipped price.
        """

    def on_bar(self, symbol: str, bar: pd.Series, timestamp: pd.Timestamp) -> None:
        """Per-bar market-rule hook (funding fees, liquidation, etc.).

        Default: no-op. Override in subclass as needed.
        """

    # ── PnL / margin calculation hooks ──
    # Override in FuturesBaseEngine to inject contract multiplier.

    def _calc_pnl(
        self, symbol: str, direction: int, size: float,
        entry_price: float, exit_price: float,
    ) -> float:
        """Realised PnL for a closed position."""
        return direction * size * (exit_price - entry_price)

    def _calc_margin(
        self, symbol: str, size: float, price: float, leverage: float,
    ) -> float:
        """Margin (collateral) required for a position."""
        return size * price / leverage

    def _calc_raw_size(
        self, symbol: str, target_notional: float, price: float,
    ) -> float:
        """Convert target notional exposure to number of units/contracts."""
        return target_notional / price

    # ── Main entry ──

    def run_backtest(
        self,
        config: Dict[str, Any],
        loader: Any,
        signal_engine: Any,
        run_dir: Path,
        bars_per_year: int = 252,
    ) -> Dict[str, Any]:
        """Full backtest pipeline — delegates to BacktestDriver (TradingEngine).

        This method is kept for backward compatibility.  New code should use
        ``BacktestDriver().run()`` directly.
        """
        from src.trading.backtest_driver import BacktestDriver
        driver = BacktestDriver()
        return driver.run(config, loader, signal_engine, run_dir, self, bars_per_year)

    # ── Position management (used by subclass liquidation hooks) ──

    def _close_position(
        self,
        symbol: str,
        exit_price: float,
        exit_time: pd.Timestamp,
        reason: str,
    ) -> None:
        """Close position, record trade, return capital."""
        self._active_symbol = symbol
        pos = self.positions.pop(symbol, None)
        if pos is None:
            return

        pnl = self._calc_pnl(symbol, pos.direction, pos.size, pos.entry_price, exit_price)
        margin = self._calc_margin(symbol, pos.size, pos.entry_price, pos.leverage)
        pnl_pct = pnl / margin * 100 if margin > 1e-9 else 0.0

        # Pass entry_time for 平今仓 detection
        if hasattr(self, "_active_entry_time"):
            self._active_entry_time = pos.entry_time
        if hasattr(self, "_active_bar_date"):
            try:
                self._active_bar_date = exit_time.date() if hasattr(exit_time, "date") else str(exit_time)[:10]
            except Exception:
                pass
        exit_comm = self.calc_commission(pos.size, exit_price, pos.direction, is_open=False)

        self.capital += margin + pnl - exit_comm

        holding_bars = max(self._bar_idx - pos.entry_bar_idx, 0)

        self.trades.append(TradeRecord(
            symbol=symbol,
            direction=pos.direction,
            entry_price=pos.entry_price,
            exit_price=exit_price,
            entry_time=pos.entry_time,
            exit_time=exit_time,
            size=pos.size,
            leverage=pos.leverage,
            pnl=pnl,
            pnl_pct=pnl_pct,
            exit_reason=reason,
            holding_bars=holding_bars,
            commission=pos.entry_commission + exit_comm,
        ))

    # ── Helpers ──

    @staticmethod
    def _safe_price(
        close_df: pd.DataFrame,
        ts: pd.Timestamp,
        symbol: str,
        fallback: float,
    ) -> float:
        """Get close price with fallback."""
        if ts in close_df.index and symbol in close_df.columns:
            val = close_df.at[ts, symbol]
            if pd.notna(val):
                return float(val)
        return fallback
