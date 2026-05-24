"""Paper trading engine – real-time bar-by-bar execution.

Reuses existing ``BaseEngine`` subclasses (ChinaAEngine, CryptoEngine, etc.)
for market-rule enforcement while processing bars one at a time (as opposed
to the backtest engine's full-history loop).

Architecture::

    on_bar(bar, ts)
      ├─ SignalBridge → raw_weights
      ├─ RiskManager.check_position → forced exits
      ├─ StateMachine → target state per symbol
      ├─ Market engine rules (can_execute / round_size / commission / slippage)
      ├─ Execute trades
      └─ Return BarResult
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import pandas as pd

from backtest.engines.base import BaseEngine
from papertrade.models import (
    BarResult,
    ExitReason,
    PaperSignal,
    RiskConfig,
    StrategyState,
)
from papertrade.risk_manager import RiskManager
from papertrade.state_machine import FlatStateMachine
from papertrade.tick_handler import SignalBridge

logger = logging.getLogger(__name__)


class PaperTradingEngine:
    """Real-time paper trading engine for a single strategy run.

    Reuses a market-specific ``BaseEngine`` subclass for:
      - ``can_execute()``  — T+1, price limits, short-sale restrictions
      - ``round_size()``   — lot-size rounding
      - ``calc_commission()`` — fee structure
      - ``apply_slippage()``  — slippage model

    The engine processes one bar at a time via :meth:`on_bar` and maintains
    live portfolio state in memory.  The caller is responsible for persisting
    state via the repository layer.
    """

    def __init__(
        self,
        config: dict,
        signal_module: Any,
        market_engine: BaseEngine,
        risk_manager: RiskManager,
        state_machine: FlatStateMachine | None = None,
    ) -> None:
        self.config = config
        self.codes: list[str] = config.get("codes", [])
        self.initial_capital: float = float(config.get("initial_capital", 100_000.0))

        # Market-engine instance (already constructed by caller with config)
        self._market = market_engine

        # Signal bridge
        self._bridge = SignalBridge(signal_module)
        self._tick_state: dict[str, Any] | None = None
        self._data_map: dict[str, pd.DataFrame] = {}

        # Risk
        self._risk = risk_manager

        # State machine
        self._state_machine = state_machine or FlatStateMachine()

        # Live state
        self.capital: float = float(market_engine.capital)
        self.positions: dict = {}  # symbol → Position
        self.trades: list = []    # TradeRecord list
        self.equity_history: list = []  # EquitySnapshot list
        self._bar_idx: int = 0
        self._last_bar_time: pd.Timestamp | None = None
        self._peak_equity: float = self.initial_capital

    # ── Properties ──────────────────────────────────────────────────

    @property
    def last_bar_time(self) -> pd.Timestamp | None:
        return self._last_bar_time

    @property
    def state(self) -> StrategyState:
        return self._state_machine.state

    @property
    def tick_mode(self) -> bool:
        return self._bridge.mode == "tick"

    # ── Initialization ──────────────────────────────────────────────

    def initialize(self, data_map: dict[str, pd.DataFrame]) -> None:
        """Seed with historical data for strategy warmup.

        - Tick mode: calls ``TickHandler.on_init(data_map)``
        - Batch mode: stores data_map for future ``generate()`` calls
        """
        if self._bridge.mode == "tick":
            self._tick_state = self._bridge.init_tick(data_map)
        else:
            self._data_map = self._bridge.init_batch(data_map)

        # Set last_bar_time from history so we only process NEW bars
        if data_map:
            last_ts = None
            for df in data_map.values():
                if len(df) > 0:
                    ts = df.index[-1]
                    if last_ts is None or ts > last_ts:
                        last_ts = ts
            self._last_bar_time = last_ts
            self._bar_idx = sum(len(df) for df in data_map.values()) // max(len(data_map), 1)

        logger.info(
            "Engine initialised: mode=%s, codes=%s, last_bar=%s",
            self._bridge.mode,
            self.codes,
            self._last_bar_time,
        )

    # ── Main entry: process one bar ─────────────────────────────────

    def on_bar(
        self, bar: dict[str, pd.Series], timestamp: pd.Timestamp
    ) -> BarResult:
        """Process one new confirmed bar through the full pipeline.

        Pipeline:
        1. Generate signals (TickHandler or batch fallback)
        2. Risk-scan existing positions → forced exits
        3. State machine → target state per symbol
        4. Execute transitions (close / open) via market engine
        5. Record equity snapshot

        Args:
            bar: ``{code: Series(open, high, low, close, volume, name=ts)}``.
            timestamp: Bar timestamp (used for trade entry/exit times).

        Returns:
            ``BarResult`` summarising everything that happened.
        """
        self._bar_idx += 1
        self._last_bar_time = timestamp
        today_str = timestamp.strftime("%Y-%m-%d") if hasattr(timestamp, "strftime") else str(timestamp)[:10]

        # 1. Generate signals
        weights = self._generate_signals(bar)

        # 2. Risk-scan existing positions (forced exits)
        forced_trades = self._check_risk_exits(bar, timestamp, today_str)

        # 3. Check daily-loss circuit breaker
        if self._risk.check_daily_loss():
            logger.warning("Daily loss limit hit — blocking new entries")
            # Already-closed positions from step 2 are recorded.
            # New entries are blocked but existing positions remain
            # (they were already handled in step 2).

        # 4. Process new signals (only if circuit breaker not tripped)
        signal_trades = []
        if not self._risk.check_daily_loss():
            signal_trades = self._process_signals(weights, bar, timestamp)

        all_trades = forced_trades + signal_trades
        signals = self._weights_to_signals(weights, timestamp)

        # 5. Sync engine state back to market engine
        self._market.capital = self.capital
        self._market.positions = dict(self.positions)

        # 6. Record equity snapshot
        equity, unrealized = self._calc_equity_and_unrealized(bar)
        dd = 0.0
        if equity > self._peak_equity:
            self._peak_equity = equity
        if self._peak_equity > 0:
            dd = (equity - self._peak_equity) / self._peak_equity

        return BarResult(
            timestamp=timestamp,
            equity=equity,
            capital=self.capital,
            unrealized=unrealized,
            drawdown=dd,
            signals=signals,
            trades=all_trades,
            positions={s: p for s, p in self.positions.items()},
        )

    # ── Force-close all ─────────────────────────────────────────────

    def force_close_all(self, reason: str = ExitReason.END_OF_RUN) -> list:
        """Close all open positions at the last known bar prices.

        Used when stopping a run or on server shutdown.
        """
        closed = []
        for symbol in list(self.positions.keys()):
            pos = self.positions[symbol]
            price = pos.entry_price  # fallback
            if symbol in self._last_bar_prices:
                price = self._last_bar_prices[symbol]
            trade = self._close_position(
                symbol, price, self._last_bar_time or pd.Timestamp.now(), reason
            )
            if trade:
                closed.append(trade)
        self._state_machine.force(StrategyState.FLAT)
        return closed

    # ── Internal: signal generation ─────────────────────────────────

    def _generate_signals(
        self, bar: dict[str, pd.Series]
    ) -> dict[str, float]:
        if self._bridge.mode == "tick":
            return self._bridge.on_bar_tick(bar, self._tick_state)
        else:
            return self._bridge.on_bar_batch(bar, self._data_map)

    # ── Internal: risk exits ────────────────────────────────────────

    _last_bar_prices: dict[str, float] = {}

    def _check_risk_exits(
        self, bar: dict[str, pd.Series], timestamp: pd.Timestamp, today: str
    ) -> list:
        trades = []
        for symbol, pos in list(self.positions.items()):
            price = float(bar[symbol].get("close", 0)) if symbol in bar else pos.entry_price
            self._last_bar_prices[symbol] = price

            reason_str = self._risk.check_position(
                symbol, pos.direction, pos.entry_price, price, today
            )
            if reason_str:
                trade = self._close_position(symbol, price, timestamp, reason_str)
                if trade:
                    trades.append(trade)
                    self._risk.on_position_closed(symbol)
                    self._risk.accumulate_daily(trade.pnl, today)

                    # State machine tracks aggregate state
                    if not self.positions:
                        self._state_machine.force(StrategyState.FLAT)
        return trades

    # ── Internal: process new signals ───────────────────────────────

    def _process_signals(
        self,
        weights: dict[str, float],
        bar: dict[str, pd.Series],
        timestamp: pd.Timestamp,
    ) -> list:
        trades = []
        today = timestamp.strftime("%Y-%m-%d") if hasattr(timestamp, "strftime") else str(timestamp)[:10]

        for symbol in self.codes:
            if symbol not in bar:
                continue

            weight = weights.get(symbol, 0.0)
            target = self._weight_to_target(weight)
            price = float(bar[symbol].get("close", 0))
            if price <= 0:
                continue

            current_pos = self.positions.get(symbol)
            current_dir = current_pos.direction if current_pos else 0

            # No change
            if target == StrategyState.FLAT and current_pos is None:
                continue
            if current_pos is not None:
                if (target == StrategyState.LONG and current_dir == 1) or \
                   (target == StrategyState.SHORT and current_dir == -1):
                    continue  # already in target state

            # Close existing position if direction differs
            if current_pos is not None:
                if target == StrategyState.FLAT or target.value != (
                    "long" if current_dir == 1 else "short"
                ):
                    trade = self._close_position(
                        symbol, price, timestamp, ExitReason.SIGNAL
                    )
                    if trade:
                        trades.append(trade)
                        self._risk.on_position_closed(symbol)
                        self._risk.accumulate_daily(trade.pnl, today)
                    if not self.positions:
                        self._state_machine.force(StrategyState.FLAT)

            # Open new position
            if target != StrategyState.FLAT:
                if not self._state_machine.can_transition(target):
                    logger.debug(
                        "State transition blocked: %s → %s",
                        self._state_machine.state, target,
                    )
                    continue

                if not self._market.can_execute(symbol, 1 if target == StrategyState.LONG else -1, bar[symbol]):
                    continue

                trade = self._open_position(symbol, target, price, weight, timestamp)
                if trade:
                    self._state_machine.transition(target)

        return trades

    # ── Internal: position management ───────────────────────────────

    def _open_position(
        self,
        symbol: str,
        target: StrategyState,
        price: float,
        weight: float,
        timestamp: pd.Timestamp,
    ):
        """Open a position using the market engine's sizing rules."""
        direction = 1 if target == StrategyState.LONG else -1
        leverage = getattr(self._market, "default_leverage", 1.0)

        # Calculate equity
        equity = self._calc_equity()
        target_notional = abs(weight) * equity * leverage

        # Check position size limit
        if not self._risk.check_position_size(target_notional, equity):
            logger.debug("Position size limit exceeded for %s", symbol)
            return None

        # Apply slippage
        slipped = self._market.apply_slippage(price, direction)
        if slipped <= 0:
            return None

        # Size
        raw_size = target_notional / slipped
        size = self._market.round_size(raw_size, slipped)
        if size <= 0:
            return None

        commission = self._market.calc_commission(size, slipped, direction, is_open=True)
        margin = slipped * size / leverage

        # Capital check
        if margin + commission > self.capital:
            available = self.capital - commission
            if available <= 0:
                return None
            size = self._market.round_size(available * leverage / slipped, slipped)
            if size <= 0:
                return None
            margin = slipped * size / leverage
            commission = self._market.calc_commission(size, slipped, direction, is_open=True)

        self.capital -= (margin + commission)

        from backtest.models import Position
        pos = Position(
            symbol=symbol,
            direction=direction,
            entry_price=slipped,
            entry_time=timestamp,
            size=size,
            leverage=leverage,
            entry_bar_idx=self._bar_idx,
            entry_commission=commission,
        )
        self.positions[symbol] = pos
        logger.info("OPEN  %s dir=%d size=%.2f price=%.4f", symbol, direction, size, slipped)
        return pos

    def _close_position(
        self,
        symbol: str,
        price: float,
        timestamp: pd.Timestamp,
        reason: str,
    ):
        """Close a position, record trade, return capital + P&L."""
        pos = self.positions.pop(symbol, None)
        if pos is None:
            return None

        # Slippage on close
        exit_price = self._market.apply_slippage(price, -pos.direction)

        # P&L (reuse market engine calc)
        pnl = self._market._calc_pnl(symbol, pos.direction, pos.size, pos.entry_price, exit_price)
        margin = self._market._calc_margin(symbol, pos.size, pos.entry_price, pos.leverage)
        pnl_pct = (pnl / margin * 100.0) if margin > 1e-9 else 0.0
        commission = self._market.calc_commission(pos.size, exit_price, pos.direction, is_open=False)

        self.capital += margin + pnl - commission
        holding_bars = max(self._bar_idx - pos.entry_bar_idx, 0)

        from backtest.models import TradeRecord
        trade = TradeRecord(
            symbol=symbol,
            direction=pos.direction,
            entry_price=pos.entry_price,
            exit_price=exit_price,
            entry_time=pos.entry_time,
            exit_time=timestamp,
            size=pos.size,
            leverage=pos.leverage,
            pnl=pnl,
            pnl_pct=pnl_pct,
            exit_reason=reason,
            holding_bars=holding_bars,
            commission=pos.entry_commission + commission,
        )
        self.trades.append(trade)
        logger.info("CLOSE %s pnl=%.2f reason=%s", symbol, pnl, reason)
        return trade

    # ── Internal: helpers ───────────────────────────────────────────

    @staticmethod
    def _weight_to_target(weight: float) -> StrategyState:
        if weight > 1e-9:
            return StrategyState.LONG
        elif weight < -1e-9:
            return StrategyState.SHORT
        return StrategyState.FLAT

    def _weights_to_signals(
        self, weights: dict[str, float], timestamp: pd.Timestamp
    ) -> list[PaperSignal]:
        return [
            PaperSignal(
                symbol=symbol,
                weight=w,
                target_state=self._weight_to_target(w),
                timestamp=timestamp,
            )
            for symbol, w in weights.items()
        ]

    def _calc_equity(self) -> float:
        """Total equity = free cash + sum(margin + unrealised) per position."""
        eq = self.capital
        for sym, pos in self.positions.items():
            margin = self._market._calc_margin(sym, pos.size, pos.entry_price, pos.leverage)
            price = self._last_bar_prices.get(sym, pos.entry_price)
            unrealized = self._market._calc_pnl(sym, pos.direction, pos.size, pos.entry_price, price)
            eq += margin + unrealized
        return eq

    def _calc_equity_and_unrealized(
        self, bar: dict[str, pd.Series]
    ) -> tuple[float, float]:
        eq = self.capital
        total_unrealized = 0.0
        for sym, pos in self.positions.items():
            margin = self._market._calc_margin(sym, pos.size, pos.entry_price, pos.leverage)
            price = float(bar.get(sym, {}).get("close", pos.entry_price)) if sym in bar else pos.entry_price
            unrealized = self._market._calc_pnl(sym, pos.direction, pos.size, pos.entry_price, price)
            self._last_bar_prices[sym] = price
            total_unrealized += unrealized
            eq += margin + unrealized
        return eq, total_unrealized

    # ── Summary ─────────────────────────────────────────────────────

    def get_summary(self) -> dict:
        equity, unrealized = self._calc_equity_and_unrealized(
            {s: pd.Series({"close": self._last_bar_prices.get(s, 0)})
             for s in self.positions}
        )
        total_return = (equity - self.initial_capital) / self.initial_capital * 100 if self.initial_capital > 0 else 0.0
        return {
            "equity": round(equity, 2),
            "capital": round(self.capital, 2),
            "unrealized": round(sum(
                self._market._calc_pnl(
                    p.symbol, p.direction, p.size, p.entry_price,
                    self._last_bar_prices.get(p.symbol, p.entry_price)
                )
                for p in self.positions.values()
            ), 2),
            "total_return_pct": round(total_return, 2),
            "trade_count": len(self.trades),
            "open_positions": len(self.positions),
            "state": self._state_machine.state.value,
            "last_bar_time": self._last_bar_time.isoformat() if self._last_bar_time else None,
            "initial_capital": self.initial_capital,
        }
