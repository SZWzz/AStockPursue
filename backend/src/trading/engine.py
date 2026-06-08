"""TradingEngine – unified bar-by-bar execution for backtest and live trading.

Wraps a market-specific ``BaseEngine`` subclass (ChinaAEngine, CryptoEngine, etc.)
and adds optional middleware layers (risk, state machine, optimizer).  Both
backtest and live trading feed bars into the same ``on_bar()`` pipeline::

    on_bar(bar, ts)
      ├─ Market hooks (funding fees, liquidation) — delegated to BaseEngine
      ├─ SignalAdapter → raw weights (unless precomputed)
      ├─ OptimizerAdapter → adjusted weights (optional)
      ├─ RiskPipeline → forced exits + daily-loss circuit breaker (optional)
      ├─ StateMachine → transition validation (optional)
      ├─ Market rules (can_execute / round_size / commission / slippage)
      ├─ Execute trades via BaseEngine._rebalance / _close_position
      └─ Return BarResult

State (capital, positions, trades, equity_snapshots) lives on the market
engine itself — TradingEngine does NOT duplicate it.  This ensures subclass
``on_bar()`` hooks (e.g. CryptoEngine liquidation) see consistent state.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from backtest.models import EquitySnapshot, Position, TradeRecord

logger = logging.getLogger(__name__)


def _weight_to_direction(weight: float) -> int:
    if weight > 1e-9:
        return 1
    elif weight < -1e-9:
        return -1
    return 0


@dataclass
class BarResult:
    """Summary of everything that happened on a single bar."""

    timestamp: pd.Timestamp
    equity: float
    capital: float
    unrealized: float
    drawdown: float
    signals: list[dict] = field(default_factory=list)
    trades: list[Any] = field(default_factory=list)
    positions: dict[str, Any] = field(default_factory=dict)
    bars: dict[str, dict] = field(default_factory=dict)  # {code: {o,h,l,c,v}}


class TradingEngine:
    """Unified trading engine wrapping a market-specific BaseEngine.

    State lives on ``self._market`` (capital, positions, trades, snapshots).
    Middleware (risk, state machine, optimizer) is optional and defaults to off.
    """

    def __init__(
        self,
        config: dict,
        signal_adapter: Any,
        market_engine: Any,  # BaseEngine subclass — owns ALL state
        risk_pipeline: Any | None = None,
        state_machine: Any | None = None,
        optimizer_adapter: Any | None = None,
    ) -> None:
        self.config = config
        self.codes: list[str] = config.get("codes", [])
        self.initial_capital: float = float(config.get("initial_capital", 100_000.0))

        self._signal = signal_adapter
        self._market = market_engine
        self._risk = risk_pipeline
        self._sm = state_machine
        self._optimizer = optimizer_adapter

        # Tracking (not state — state is on self._market)
        self._bar_idx: int = 0
        self._last_bar_time: pd.Timestamp | None = None
        self._peak_equity: float = self.initial_capital
        self._last_bar_prices: dict[str, float] = {}

        # Batch-mode data accumulation (for incremental generate())
        self._data_map: dict[str, pd.DataFrame] = {}

        # Suspension detection
        self._suspended: dict[str, bool] = {}       # code → currently suspended
        self._consecutive_flat: dict[str, int] = {}  # code → consecutive flat bars

        # Tick-mode state
        self._tick_state: dict[str, Any] | None = None

        # Ensure market engine starts with configured capital
        self._market.capital = self.initial_capital

    # ── State proxies (read/write through to market engine) ──────────

    @property
    def capital(self) -> float:
        return self._market.capital

    @capital.setter
    def capital(self, value: float) -> None:
        self._market.capital = value

    @property
    def positions(self) -> dict[str, Position]:
        return self._market.positions

    @property
    def trades(self) -> list[TradeRecord]:
        return self._market.trades

    @property
    def equity_snapshots(self) -> list[EquitySnapshot]:
        return self._market.equity_snapshots

    # ── Properties ──────────────────────────────────────────────────

    @property
    def last_bar_time(self) -> pd.Timestamp | None:
        return self._last_bar_time

    @property
    def tick_mode(self) -> bool:
        return self._signal.mode == "tick"

    # ── Bar data access ─────────────────────────────────────────────

    def get_bars(
        self, codes: list[str] | None = None, limit: int = 500
    ) -> dict[str, list[dict]]:
        """Return OHLCV history from ``_data_map`` as a JSON-safe dict.

        Args:
            codes: Symbols to return (all if None).
            limit: Max bars per symbol, newest first.

        Returns:
            ``{code: [{time, open, high, low, close, volume}, ...]}``
        """
        target = codes or list(self._data_map.keys())
        result: dict[str, list[dict]] = {}
        for code in target:
            df = self._data_map.get(code)
            if df is None or len(df) == 0:
                continue
            rows = []
            for ts, row in df.sort_index().tail(limit).iterrows():
                rows.append({
                    "time": str(ts),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row.get("volume", 0.0)),
                })
            result[code] = rows
        return result

    # ── Initialization ──────────────────────────────────────────────

    def initialize(self, data_map: dict[str, pd.DataFrame]) -> None:
        """Seed with historical data for strategy warmup.

        - Tick mode: calls ``TickHandler.on_init(data_map)``
        - Batch mode: stores data_map for future ``generate()`` calls
        """
        if self._signal.mode == "tick":
            self._tick_state = self._signal.init_tick(data_map)
        else:
            self._data_map = self._signal.init_batch(data_map)

        if data_map:
            last_ts = None
            for df in data_map.values():
                if len(df) > 0:
                    ts = df.index[-1]
                    if last_ts is None or ts > last_ts:
                        last_ts = ts
            self._last_bar_time = last_ts
            self._bar_idx = sum(len(df) for df in data_map.values()) // max(len(data_map), 1)

        # [P1-1 fix] Seed _last_bar_prices from historical data so gap/suspension
        # detection works correctly on the very first live bar.
        for code, df in data_map.items():
            if len(df) > 0:
                self._last_bar_prices[code] = float(df["close"].iloc[-1])

        logger.info(
            "TradingEngine initialised: mode=%s, codes=%s, last_bar=%s",
            self._signal.mode,
            self.codes,
            self._last_bar_time,
        )

    # ── Main entry: process one bar ─────────────────────────────────

    def on_bar(
        self,
        bar: dict[str, pd.Series],
        timestamp: pd.Timestamp,
        precomputed_weights: dict[str, float] | None = None,
    ) -> BarResult:
        """Process one new confirmed bar through the full pipeline.

        Args:
            bar: ``{code: Series(open, high, low, close, volume, name=ts)}``.
            timestamp: Bar timestamp.
            precomputed_weights: If provided (backtest fast mode), skip signal
                generation and use these weights directly.

        Returns:
            ``BarResult`` summarising everything that happened.
        """
        self._bar_idx += 1
        self._last_bar_time = timestamp
        today_str = (
            timestamp.strftime("%Y-%m-%d")
            if hasattr(timestamp, "strftime")
            else str(timestamp)[:10]
        )

        # 0. Gap + suspension detection
        suspension_trades: list[Any] = []
        gap_trades: list[Any] = []

        # 0a. Gap detection: check each open position for overnight gaps
        if self._risk is not None:
            for sym, pos in list(self._market.positions.items()):
                if sym not in bar:
                    continue
                row = bar[sym]
                bar_open = float(row.get("open", 0))
                prev_close = self._last_bar_prices.get(sym, bar_open)
                reason, exec_price = self._risk.check_gap(
                    sym, pos.direction, pos.entry_price, prev_close, bar_open,
                )
                if reason:
                    trade = self._close_position(sym, exec_price, self._last_bar_time, reason=reason)
                    if trade:
                        gap_trades.append(trade)
                        logger.info("Gap exit: %s %s at %.2f (prev_close=%.2f, open=%.2f)",
                                    sym, reason, exec_price, prev_close, bar_open)

        # 0b. Suspension detection
        for c in self.codes:
            if c not in bar:
                continue
            row = bar[c]
            close_val = float(row.get("close", 0))
            vol_val = float(row.get("volume", 0))

            # Detect suspension: close unchanged AND zero volume for ≥2 bars
            prev_close = self._last_bar_prices.get(c)
            is_flat = (prev_close is not None and abs(close_val - prev_close) < 1e-9 and vol_val < 1e-6)
            if is_flat:
                self._consecutive_flat[c] = self._consecutive_flat.get(c, 0) + 1
            else:
                self._consecutive_flat[c] = 0

            if self._consecutive_flat.get(c, 0) >= 2 and not self._suspended.get(c):
                self._suspended[c] = True
                logger.warning("Symbol %s appears suspended (flat close + zero vol ×%d bars) — force-closing",
                               c, self._consecutive_flat[c])
                pos = self._market.positions.get(c)
                if pos is not None:
                    exit_price = float(row.get("open", close_val))
                    trade = self._close_position(c, exit_price, timestamp, reason="suspended")
                    if trade:
                        suspension_trades.append(trade)

            # Resume from suspension
            if not is_flat and self._suspended.get(c):
                self._suspended[c] = False
                self._consecutive_flat[c] = 0
                # [P1-2 fix] Update _last_bar_prices on resume so gap detection
                # doesn't see a stale pre-suspension close and misidentify the
                # resume jump as an overnight gap.
                self._last_bar_prices[c] = close_val
                logger.info("Symbol %s resumed from suspension", c)

        # 0.5 Run per-bar market hooks (funding fees, liquidation checks, etc.)
        #    These operate directly on self._market.positions / self._market.capital.
        for c in self.codes:
            if c in bar:
                self._market.on_bar(c, bar[c], timestamp)

        # 1. Generate signals (or use precomputed).  Suspended symbols are filtered
        #    so the strategy never sees them and cannot generate trades on halted stock.
        active_bar = {c: s for c, s in bar.items() if not self._suspended.get(c)}
        active_codes = [c for c in self.codes if c in active_bar]
        if precomputed_weights is not None:
            weights = {c: w for c, w in precomputed_weights.items() if c in active_codes}
        else:
            weights = self._generate_signals(active_bar) if active_bar else {}

        # [P1-2 fix] Record ALL bars for data continuity — even suspended stocks.
        # MUST come AFTER _generate_signals to prevent look-ahead bias: the strategy
        # must never see the current bar's data when generating signals.
        self._record_bars(bar)

        # 1.5 Online optimizer (Phase 2)
        if self._optimizer is not None and weights:
            weights = self._optimizer.apply(weights, bar)

        # [P0-1 fix] Cache equity BEFORE risk exits update _last_bar_prices with
        # today's close.  This ensures position sizing in _process_signals uses
        # yesterday's close prices, not today's — eliminating look-ahead bias
        # where today's unrealised PnL influenced trade sizes at today's open.
        equity_for_sizing = self._calc_equity()

        # 2. Risk-scan existing positions (forced exits)
        #    NOTE: _check_risk_exits updates _last_bar_prices[symbol] = close
        #    for each position it checks.  This is correct for risk management
        #    (trailing stops need the latest price) but we must not use these
        #    updated prices for position sizing — see P0-1 fix above.
        forced_trades: list[Any] = []
        if self._risk is not None:
            forced_trades = self._check_risk_exits(bar, timestamp, today_str)

        # 3. Process new signals (blocked if daily-loss circuit breaker tripped)
        signal_trades: list[Any] = []
        daily_loss_blocked = self._risk is not None and self._risk.check_daily_loss(equity_for_sizing)
        if daily_loss_blocked:
            logger.warning("Daily loss limit hit — blocking new entries")
        else:
            signal_trades = self._process_signals(weights, bar, timestamp, equity_for_sizing)

        all_trades = suspension_trades + gap_trades + forced_trades + signal_trades
        signals = self._weights_to_signal_dicts(weights, timestamp)

        # 4. Record equity snapshot
        equity, unrealized = self._calc_equity_and_unrealized(bar)
        dd = 0.0
        if equity > self._peak_equity:
            self._peak_equity = equity
        if self._peak_equity > 0:
            dd = (equity - self._peak_equity) / self._peak_equity

        self._market.equity_snapshots.append(EquitySnapshot(
            timestamp=timestamp,
            capital=self._market.capital,
            unrealized=unrealized,
            equity=equity,
            positions=len(self._market.positions),
        ))

        bar_ohlcv: dict[str, dict] = {}
        for code, series in bar.items():
            bar_ohlcv[code] = {
                "open": float(series.get("open", 0)),
                "high": float(series.get("high", 0)),
                "low": float(series.get("low", 0)),
                "close": float(series.get("close", 0)),
                "volume": float(series.get("volume", 0)),
            }

        return BarResult(
            timestamp=timestamp,
            equity=equity,
            capital=self._market.capital,
            unrealized=unrealized,
            drawdown=dd,
            signals=signals,
            trades=all_trades,
            positions={s: p for s, p in self._market.positions.items()},
            bars=bar_ohlcv,
        )

    # ── Force-close all ─────────────────────────────────────────────

    def force_close_symbol(self, symbol: str, reason: str = "manual") -> TradeRecord | None:
        """Close a single position at the last known price."""
        pos = self._market.positions.get(symbol)
        if pos is None:
            return None
        price = self._last_bar_prices.get(symbol, pos.entry_price)
        return self._close_position(symbol, price, self._last_bar_time or pd.Timestamp.now(), reason)

    def force_close_all(self, reason: str = "end_of_run") -> list[TradeRecord]:
        """Close all open positions at the last known bar prices."""
        closed: list[TradeRecord] = []
        for symbol in list(self._market.positions.keys()):
            trade = self.force_close_symbol(symbol, reason)
            if trade:
                closed.append(trade)
        if self._sm:
            self._sm.force(self._get_sm_flat_state())
        return closed

    # ── Internal: signal generation ─────────────────────────────────

    def _generate_signals(self, bar: dict[str, pd.Series]) -> dict[str, float]:
        """Generate target weights from the signal adapter for the current bar.

        Dispatches to the tick-mode or batch-mode handler depending on
        the adapter's configured mode.  In batch mode, ``skip_append=True``
        prevents the adapter from recording the current bar — bar
        recording is handled separately by ``_record_bars()`` to ensure
        all bars (including suspended stocks) are appended for data
        continuity.

        Args:
            bar: ``{code: Series}`` for the current timestamp.  Only
                non-suspended codes are passed through.

        Returns:
            ``{code: target_weight}`` where weight is typically in
            ``[-1.0, 1.0]``.
        """
        if self._signal.mode == "tick":
            return self._signal.on_bar_tick(bar, self._tick_state)
        else:
            # skip_append=True: bar recording is handled by _record_bars()
            # which records ALL bars (including suspended) for data continuity.
            return self._signal.on_bar_batch(bar, self._data_map, skip_append=True)

    # ── Internal: bar recording (data continuity) ────────────────────

    def _record_bars(self, bar: dict[str, pd.Series]) -> None:
        """Append all bars to _data_map regardless of suspension status.

        [P1-2 fix] Previously only active (non-suspended) bars were appended,
        creating data gaps that broke rolling-window calculations when a
        suspended stock resumed trading.
        """
        if self._signal.mode != "batch":
            return
        # Use the same bound as SignalAdapter to stay consistent
        from src.trading.config import MAX_HISTORY as _MAX_HISTORY
        for code, row in bar.items():
            if code not in self._data_map:
                continue
            df = self._data_map[code]
            if hasattr(row, "name") and row.name is not None:
                ts = row.name
            elif len(df) > 0:
                # [P1-01 fix] Infer frequency from existing index instead of
                # assuming daily bars.  For intraday data, df.index[-1] + 1day
                # would corrupt the timeline.
                freq = pd.infer_freq(df.index[-5:]) if len(df) >= 3 else None
                if freq is not None:
                    ts = df.index[-1] + pd.tseries.frequencies.to_offset(freq)
                else:
                    ts = df.index[-1] + pd.Timedelta(days=1)
            else:
                ts = pd.Timestamp.now()
            new_row = pd.DataFrame([row], index=[ts])
            self._data_map[code] = pd.concat([df, new_row])
            if len(self._data_map[code]) > _MAX_HISTORY:
                self._data_map[code] = self._data_map[code].iloc[-_MAX_HISTORY:]
                logger.warning(
                    "Data history for %s truncated to %d bars — "
                    "long-window factors may be affected",
                    code, _MAX_HISTORY,
                )

    # ── Internal: risk exits ────────────────────────────────────────

    def _check_risk_exits(
        self, bar: dict[str, pd.Series], timestamp: pd.Timestamp, today: str
    ) -> list[TradeRecord]:
        trades: list[TradeRecord] = []
        for symbol, pos in list(self._market.positions.items()):
            if symbol not in bar:
                continue
            row = bar[symbol]
            close = float(row.get("close", 0))
            self._last_bar_prices[symbol] = close

            # Intraday check first (bar high/low — more accurate)
            if getattr(self._risk, "_use_intraday", False):
                reason, exec_price = self._risk.check_position_intraday(
                    symbol, pos.direction, pos.entry_price,
                    float(row.get("open", close)),
                    float(row.get("high", close)),
                    float(row.get("low", close)),
                    close,
                )
                if reason:
                    trade = self._close_position(symbol, exec_price, timestamp, reason)
                    if trade:
                        trades.append(trade)
                        self._risk.on_position_closed(symbol)
                        self._risk.accumulate_daily(trade.pnl, today)
                        if not self._market.positions and self._sm:
                            self._sm.force(self._get_sm_flat_state())
                    continue  # already closed, skip close-based check

            # Fallback: close-based check (existing behaviour)
            reason_str = self._risk.check_position(
                symbol, pos.direction, pos.entry_price, close, today
            )
            if reason_str:
                trade = self._close_position(symbol, close, timestamp, reason_str)
                if trade:
                    trades.append(trade)
                    self._risk.on_position_closed(symbol)
                    self._risk.accumulate_daily(trade.pnl, today)

                    if not self._market.positions and self._sm:
                        self._sm.force(self._get_sm_flat_state())
        return trades

    # ── Internal: process new signals ───────────────────────────────

    def _process_signals(
        self,
        weights: dict[str, float],
        bar: dict[str, pd.Series],
        timestamp: pd.Timestamp,
        equity: float | None = None,
    ) -> list[TradeRecord]:
        trades: list[TradeRecord] = []
        today = (
            timestamp.strftime("%Y-%m-%d")
            if hasattr(timestamp, "strftime")
            else str(timestamp)[:10]
        )

        for symbol in self.codes:
            if symbol not in bar:
                continue
            try:
                weight = weights.get(symbol, 0.0)
                target_dir = _weight_to_direction(weight)
                # Use open price for execution (next-bar-open semantics).
                # This matches _align() shift(1) + old BaseEngine._rebalance() behaviour.
                price = float(bar[symbol].get("open", bar[symbol].get("close", 0)))
                if price <= 0:
                    continue

                current_pos = self._market.positions.get(symbol)
                current_dir = current_pos.direction if current_pos else 0

                # No change
                if target_dir == 0 and current_pos is None:
                    continue
                if current_pos is not None and target_dir == current_dir:
                    continue

                # Close existing position if direction differs
                if current_pos is not None and target_dir != current_dir:
                    trade = self._close_position(symbol, price, timestamp, "signal")
                    if trade:
                        trades.append(trade)
                        if self._risk:
                            self._risk.on_position_closed(symbol)
                            self._risk.accumulate_daily(trade.pnl, today)
                    if not self._market.positions and self._sm:
                        self._sm.force(self._get_sm_flat_state())

                # Open new position
                if target_dir != 0 and symbol not in self._market.positions:
                    from src.trading.state_machine import StrategyState
                    target_state = StrategyState.LONG if target_dir == 1 else StrategyState.SHORT
                    if self._sm and not self._sm.can_transition(target_state):
                        logger.debug(
                            "State transition blocked: %s → %s",
                            self._sm.state, target_state,
                        )
                        continue

                    if not self._market.can_execute(symbol, target_dir, bar[symbol]):
                        continue

                    trade = self._open_position(symbol, target_dir, price, weight, timestamp, equity)
                    if trade:
                        trades.append(trade)
                        if self._sm:
                            self._sm.transition(target_state)
            except (ValueError, KeyError, TypeError, AttributeError, IndexError, RuntimeError) as e:
                # [P1-6 fix] Catch specific exception types instead of bare Exception.
                # RuntimeError included: can_execute / market rule checks may raise it.
                # KeyboardInterrupt and SystemExit are intentionally NOT caught.
                # Log at ERROR level with full traceback so signal-processing
                # failures are visible and debuggable.  We still don't re-raise —
                # one bad symbol shouldn't kill the entire bar.
                logger.error(
                    "Signal processing failed for %s at %s (bar data: %s)",
                    symbol, timestamp,
                    {k: float(bar[symbol].get(k, 0)) for k in ("open", "close", "volume")},
                    exc_info=True,
                )

        return trades

    # ── Internal: position management (delegates to market engine) ──

    def _open_position(
        self,
        symbol: str,
        direction: int,
        price: float,
        weight: float,
        timestamp: pd.Timestamp,
        equity: float | None = None,
    ) -> Position | None:
        """Open a position using the market engine's sizing rules.

        [P0-1 fix] ``equity`` should be pre-computed from *yesterday's* close
        prices (cached before _check_risk_exits updated _last_bar_prices).
        This prevents today's unrealised PnL from influencing trade sizes.
        """
        self._market._active_symbol = symbol
        leverage = getattr(self._market, "default_leverage", 1.0)
        if equity is None:
            equity = self._calc_equity()
        target_notional = abs(weight) * equity * leverage

        if self._risk and not self._risk.check_position_size(target_notional, equity):
            logger.debug("Position size limit exceeded for %s", symbol)
            return None

        slipped = self._market.apply_slippage(price, direction)
        if slipped <= 0:
            return None

        raw_size = target_notional / slipped
        size = self._market.round_size(raw_size, slipped)
        if size <= 0:
            return None

        commission = self._market.calc_commission(size, slipped, direction, is_open=True)
        margin = self._market._calc_margin(symbol, size, slipped, leverage)

        if margin + commission > self._market.capital:
            available = self._market.capital - commission
            if available <= 0:
                return None
            size = self._market.round_size(
                self._market._calc_raw_size(symbol, available * leverage, slipped), slipped,
            )
            if size <= 0:
                return None
            margin = self._market._calc_margin(symbol, size, slipped, leverage)
            commission = self._market.calc_commission(size, slipped, direction, is_open=True)

        self._market.capital -= (margin + commission)

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
        self._market.positions[symbol] = pos
        logger.info("OPEN  %s dir=%d size=%.2f price=%.4f", symbol, direction, size, slipped)
        return pos

    def _close_position(
        self,
        symbol: str,
        price: float,
        timestamp: pd.Timestamp,
        reason: str,
    ) -> TradeRecord | None:
        """Close a position, record trade, return capital + P&L."""
        self._market._active_symbol = symbol
        pos = self._market.positions.pop(symbol, None)
        if pos is None:
            return None

        exit_price = self._market.apply_slippage(price, -pos.direction)
        pnl = self._market._calc_pnl(symbol, pos.direction, pos.size, pos.entry_price, exit_price)
        margin = self._market._calc_margin(symbol, pos.size, pos.entry_price, pos.leverage)
        pnl_pct = (pnl / margin * 100.0) if margin > 1e-9 else 0.0

        # Pass entry_time for 平今仓 (close-today) detection in futures engines
        if hasattr(self._market, "_active_entry_time"):
            self._market._active_entry_time = pos.entry_time
        if hasattr(self._market, "_active_bar_date"):
            try:
                self._market._active_bar_date = timestamp.date() if hasattr(timestamp, "date") else str(timestamp)[:10]
            except (AttributeError, ValueError, TypeError):
                pass
        commission = self._market.calc_commission(pos.size, exit_price, pos.direction, is_open=False)

        self._market.capital += margin + pnl - commission
        holding_bars = max(self._bar_idx - pos.entry_bar_idx, 0)

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
        self._market.trades.append(trade)
        logger.info("CLOSE %s pnl=%.2f reason=%s", symbol, pnl, reason)
        return trade

    # ── Internal: equity calculation ─────────────────────────────────

    def _equity_from_prices(self, prices: dict[str, float]) -> tuple[float, float]:
        """Calculate total equity + unrealised PnL from a price snapshot."""
        eq = self._market.capital
        total_unrealized = 0.0
        for sym, pos in self._market.positions.items():
            margin = self._market._calc_margin(sym, pos.size, pos.entry_price, pos.leverage)
            price = prices.get(sym, pos.entry_price)
            unrealized = self._market._calc_pnl(sym, pos.direction, pos.size, pos.entry_price, price)
            total_unrealized += unrealized
            eq += margin + unrealized
        return eq, total_unrealized

    def _calc_equity(self) -> float:
        """Calculate total equity from the last known bar prices.

        Returns:
            Total equity = capital + sum(margin + unrealized PnL across
            all open positions), using ``_last_bar_prices`` for valuation.
        """
        eq, _ = self._equity_from_prices(self._last_bar_prices)
        return eq

    def _calc_equity_and_unrealized(
        self, bar: dict[str, pd.Series]
    ) -> tuple[float, float]:
        """Calculate total equity and unrealised PnL from the current bar.

        Updates ``_last_bar_prices`` for all open positions using the
        close price from the current bar, then delegates to
        ``_equity_from_prices``.

        Args:
            bar: ``{code: Series}`` for the current timestamp.

        Returns:
            ``(total_equity, total_unrealized_pnl)`` tuple.
        """
        # Update last_bar_prices from current bar, then calculate
        for sym in self._market.positions:
            if sym in bar:
                self._last_bar_prices[sym] = float(bar[sym].get("close", self._last_bar_prices.get(sym, 0)))
        return self._equity_from_prices(self._last_bar_prices)

    # ── Internal: helpers ───────────────────────────────────────────

    @staticmethod
    def _get_sm_flat_state():
        """Return the FLAT state enum value for the state machine.

        Used to force the state machine back to flat when all positions
        are closed (risk exits, manual closes, etc.).

        Returns:
            ``StrategyState.FLAT``.
        """
        from src.trading.state_machine import StrategyState
        return StrategyState.FLAT

    def _weights_to_signal_dicts(
        self, weights: dict[str, float], timestamp: pd.Timestamp
    ) -> list[dict]:
        """Convert a weight map to a list of signal dicts for the BarResult.

        Args:
            weights: ``{code: target_weight}`` map.
            timestamp: Current bar timestamp.

        Returns:
            List of dicts with keys ``symbol``, ``weight``, ``direction``,
            and ``timestamp``.
        """
        return [
            {
                "symbol": symbol,
                "weight": w,
                "direction": _weight_to_direction(w),
                "timestamp": timestamp,
            }
            for symbol, w in weights.items()
        ]

    # ── Summary ─────────────────────────────────────────────────────

    def get_summary(self) -> dict:
        equity, unrealized = self._equity_from_prices(self._last_bar_prices)
        total_return = (
            (equity - self.initial_capital) / self.initial_capital * 100
            if self.initial_capital > 0
            else 0.0
        )
        return {
            "equity": round(equity, 2),
            "capital": round(self._market.capital, 2),
            "unrealized": round(unrealized, 2),
            "total_return_pct": round(total_return, 2),
            "trade_count": len(self._market.trades),
            "open_positions": len(self._market.positions),
            "state": self._sm.state.value if self._sm else "flat",
            "last_bar_time": self._last_bar_time.isoformat() if self._last_bar_time else None,
            "initial_capital": self.initial_capital,
        }
