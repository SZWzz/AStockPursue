"""Paper trading data models – dataclasses, Pydantic schemas, and protocols."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Protocol, runtime_checkable

import pandas as pd
from pydantic import BaseModel, Field


# ── Protocol: TickHandler (optional per-bar strategy upgrade) ────────────


@runtime_checkable
class TickHandler(Protocol):
    """Optional protocol for strategies that support per-bar signal generation.

    A SignalEngine that implements TickHandler supports O(n)-per-bar execution
    with cross-tick state persistence.  Strategies that do NOT implement this
    protocol fall back to batch-mode (``SignalEngine.generate()`` called with
    the full historical data map on each bar).
    """

    def on_init(self, data_map: dict[str, pd.DataFrame]) -> dict[str, Any]:
        """Initialise strategy state from historical warm-up data.

        Args:
            data_map: ``{code: DataFrame(OHLCV)}`` with lookback bars.

        Returns:
            Arbitrary state dict preserved across ``on_bar`` calls.
        """
        ...

    def on_bar(
        self, bar: dict[str, pd.Series], state: dict[str, Any]
    ) -> dict[str, float]:
        """Process one new confirmed bar and return target weights.

        Args:
            bar: ``{code: Series(open, high, low, close, volume, name=timestamp)}``.
            state: Mutable state dict from ``on_init`` / previous ``on_bar``.

        Returns:
            ``{code: weight}`` where weight ∈ [-1.0, 1.0].  Codes not present
            are treated as weight=0 (no position change).
        """
        ...


# ── Enums ────────────────────────────────────────────────────────────────


class StrategyState(str, Enum):
    FLAT = "flat"
    LONG = "long"
    SHORT = "short"


class RunStatus(str, Enum):
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


class ExitReason(str, Enum):
    SIGNAL = "signal"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    TRAILING_STOP = "trailing_stop"
    DAILY_LOSS = "daily_loss"
    MANUAL = "manual"
    END_OF_RUN = "end_of_run"


# ── Engine-internal dataclasses ──────────────────────────────────────────


@dataclass(frozen=True)
class PaperSignal:
    """A signal produced by the strategy for a single bar + symbol."""

    symbol: str
    weight: float
    target_state: StrategyState
    timestamp: pd.Timestamp


@dataclass
class BarResult:
    """Summary of everything that happened on a single bar."""

    timestamp: pd.Timestamp
    equity: float
    capital: float
    unrealized: float
    drawdown: float
    signals: list[PaperSignal] = field(default_factory=list)
    trades: list[Any] = field(default_factory=list)  # TradeRecord from backtest.models
    positions: dict[str, Any] = field(default_factory=dict)


# ── Pydantic API schemas ─────────────────────────────────────────────────


class RiskConfig(BaseModel):
    """Risk management parameters for a paper trading run.

    Field definitions are derived from ``src.trading.risk_pipeline.RiskConfigFields``
    so that the paper-trade and trading configs never diverge.
    """

    stop_loss_pct: float = Field(default_factory=lambda: _risk_fields().stop_loss_pct, ge=0.0, le=100.0,
                                  description="Stop-loss threshold (%)")
    take_profit_pct: float = Field(default_factory=lambda: _risk_fields().take_profit_pct, ge=0.0, le=1000.0,
                                    description="Take-profit threshold (%)")
    trailing_stop_pct: float = Field(default_factory=lambda: _risk_fields().trailing_stop_pct, ge=0.0, le=100.0,
                                      description="Trailing-stop distance (%). 0 = disabled")
    max_daily_loss_pct: float = Field(default_factory=lambda: _risk_fields().max_daily_loss_pct, ge=0.0, le=100.0,
                                       description="Max daily loss as % of initial capital")
    max_position_pct: float = Field(default_factory=lambda: _risk_fields().max_position_pct, ge=0.0, le=100.0,
                                     description="Max single-position notional as % of equity")
    use_intraday_stop: bool = Field(default_factory=lambda: _risk_fields().use_intraday_stop,
                                     description="Check bar high/low, not just close")


def _risk_fields():
    from src.trading.risk_pipeline import RiskConfigFields
    return RiskConfigFields()


class CreateRunRequest(BaseModel):
    run_name: str = Field(..., min_length=1, max_length=200)
    market: str = Field(default="a_share")
    codes: list[str] = Field(..., min_length=1)
    interval: str = Field(default="1D")
    initial_capital: float = Field(default=100_000.0, ge=1_000.0)
    strategy_code: str = Field(..., min_length=1,
                                description="Python source of a SignalEngine class")
    risk_config: RiskConfig = Field(default_factory=RiskConfig)


class UpdateRunRequest(BaseModel):
    run_name: Optional[str] = None
    risk_config: Optional[RiskConfig] = None


class RunSummary(BaseModel):
    id: str
    run_name: str
    market: str
    status: RunStatus
    tick_mode: bool
    state: StrategyState
    current_equity: float
    total_return_pct: float
    trade_count: int
    open_positions: int
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    last_bar_time: Optional[str] = None


class EquityPoint(BaseModel):
    point_time: str
    equity: float
    capital: float
    unrealized: float
    drawdown: float


class PositionOut(BaseModel):
    symbol: str
    direction: int
    entry_price: float
    entry_time: str
    size: float
    leverage: float
    current_price: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    pnl_pct: Optional[float] = None


class TradeOut(BaseModel):
    id: int
    symbol: str
    direction: int
    entry_price: float
    exit_price: float
    entry_time: str
    exit_time: str
    size: float
    leverage: float
    pnl: float
    pnl_pct: float
    exit_reason: str
    holding_bars: int
    commission: float


class RunDetail(BaseModel):
    run: RunSummary
    positions: list[PositionOut] = []
    recent_trades: list[TradeOut] = []
    data_source: str = "unknown"
