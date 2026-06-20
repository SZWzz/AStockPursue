"""Independent risk management for live/backtest trading.

Applied as a separate layer between signal generation and trade execution.
Checks existing positions against stop-loss / take-profit / trailing-stop
thresholds and returns forced-exit reasons.  Also enforces per-day loss
limits and per-position size limits.
"""

from __future__ import annotations

from dataclasses import dataclass, fields


@dataclass(frozen=True)
class RiskConfigFields:
    """Canonical field definitions shared between paper-trade and trading.

    When adding/changing a field, update here FIRST — both ``RiskConfig``
    and ``papertrade.models.RiskConfig`` derive from this.
    """

    stop_loss_pct: float = 5.0
    take_profit_pct: float = 10.0
    trailing_stop_pct: float = 0.0
    max_daily_loss_pct: float = 3.0
    max_position_pct: float = 30.0
    use_intraday_stop: bool = True


class RiskConfig:
    """Risk management parameters (populated from ``RiskConfigFields`` defaults)."""

    def __init__(self, **kwargs) -> None:
        defaults = RiskConfigFields()
        for f in fields(RiskConfigFields):
            val = kwargs.get(f.name, getattr(defaults, f.name))
            setattr(self, f.name, val)


class RiskPipeline:
    """Composable risk management layer.

    Pipeline order (highest priority first):
      1. stop-loss
      2. trailing-stop
      3. take-profit

    Optionally integrates with NotifyEngine for inline risk alerts.
    """

    def __init__(
        self,
        config: RiskConfig,
        initial_capital: float,
        notify: object | None = None,
    ) -> None:
        self._stop_loss_pct = -abs(config.stop_loss_pct) / 100.0
        self._take_profit_pct = abs(config.take_profit_pct) / 100.0
        self._trailing_stop_pct = abs(config.trailing_stop_pct) / 100.0 if config.trailing_stop_pct > 0 else 0.0
        self._trailing_enabled = self._trailing_stop_pct > 1e-9
        # [P2-6 fix] Store the percentage so daily loss limit can be recalculated
        # dynamically against current equity, not just initial_capital.
        self._max_daily_loss_pct = abs(config.max_daily_loss_pct) / 100.0
        self._initial_capital = initial_capital
        # Seed with initial capital; check_daily_loss(equity=...) updates it dynamically.
        self._max_daily_loss = initial_capital * self._max_daily_loss_pct
        self._max_position_pct = abs(config.max_position_pct) / 100.0

        self._use_intraday = config.use_intraday_stop
        self._trailing_highs: dict[str, float] = {}
        self._daily_pnl: float = 0.0
        self._daily_date: str = ""
        self._notify = notify  # Optional NotifyEngine for inline alerts

    # ── Position checks ─────────────────────────────────────────────

    def check_position(
        self,
        symbol: str,
        direction: int,
        entry_price: float,
        current_price: float,
        current_date: str,
    ) -> str | None:
        """Return an exit reason if the position should be closed, or None."""
        if entry_price <= 0:
            return None

        pnl_pct = direction * (current_price - entry_price) / entry_price

        if pnl_pct <= self._stop_loss_pct:
            return "stop_loss"

        if self._trailing_enabled:
            if symbol not in self._trailing_highs:
                self._trailing_highs[symbol] = entry_price
            high = self._trailing_highs[symbol]
            if current_price > high:
                self._trailing_highs[symbol] = current_price
                high = current_price
            trail_price = high * (1.0 - direction * self._trailing_stop_pct)
            if direction == 1 and current_price <= trail_price:
                return "trailing_stop"
            if direction == -1 and current_price >= trail_price:
                return "trailing_stop"

        if pnl_pct >= self._take_profit_pct:
            return "take_profit"

        return None

    # ── Intraday checks (bar high/low) ──────────────────────────────

    def check_position_intraday(
        self,
        symbol: str,
        direction: int,
        entry_price: float,
        bar_open: float,
        bar_high: float,
        bar_low: float,
        bar_close: float,
    ) -> tuple[str | None, float | None]:
        """Check if stop/target was hit *within* the bar using high/low.

        Returns ``(exit_reason, execution_price)`` or ``(None, None)``.
        Priority: stop_loss > trailing_stop > take_profit.
        """
        if entry_price <= 0 or bar_open <= 0:
            return None, None

        stop_p = entry_price * (1.0 + direction * self._stop_loss_pct)
        target_p = entry_price * (1.0 + direction * self._take_profit_pct)

        if direction == 1:
            stop_touched = bar_low <= stop_p
            target_touched = bar_high >= target_p
        else:
            stop_touched = bar_high >= stop_p
            target_touched = bar_low <= target_p

        trail_touched = False
        trail_p = 0.0
        if self._trailing_enabled:
            if symbol not in self._trailing_highs:
                self._trailing_highs[symbol] = entry_price
            self._trailing_highs[symbol] = max(self._trailing_highs[symbol], bar_high)
            trail_p = self._trailing_highs[symbol] * (1.0 - direction * self._trailing_stop_pct)
            if direction == 1:
                trail_touched = bar_low <= trail_p
            else:
                trail_touched = bar_high >= trail_p

        # Priority: stop > trail > target (risk-first)
        if stop_touched:
            return "stop_loss", _intraday_exec_price(bar_open, stop_p, direction, is_stop=True)
        if trail_touched:
            return "trailing_stop", _intraday_exec_price(bar_open, trail_p, direction, is_stop=True)
        if target_touched:
            return "take_profit", _intraday_exec_price(bar_open, target_p, direction, is_stop=False)

        return None, None

    # ── Gap detection (bar-to-bar) ──────────────────────────────────

    def check_gap(
        self,
        symbol: str,
        direction: int,
        entry_price: float,
        prev_close: float,
        bar_open: float,
    ) -> tuple[str | None, float | None]:
        """Check whether the overnight gap penetrates stop-loss, trailing-stop,
        or take-profit.

        Called before processing a new bar.  If the gap from ``prev_close``
        to ``bar_open`` crosses the stop, trailing, or target level, return
        the exit reason and execution price (at open).
        Priority: stop > trailing > target.

        Returns ``(reason, exec_price)`` or ``(None, None)``.
        """
        if entry_price <= 0 or prev_close <= 0 or bar_open <= 0:
            return None, None

        stop_p = entry_price * (1.0 + direction * self._stop_loss_pct)
        target_p = entry_price * (1.0 + direction * self._take_profit_pct)

        stop_gapped = (direction == 1 and bar_open <= stop_p) or (direction == -1 and bar_open >= stop_p)
        target_gapped = (direction == 1 and bar_open >= target_p) or (direction == -1 and bar_open <= target_p)

        # [P1-3 fix] Check trailing_stop gap as well, using the trailing high
        # from _trailing_highs (tracked in check_position / check_position_intraday).
        trail_gapped = False
        if self._trailing_enabled and symbol in self._trailing_highs:
            high = self._trailing_highs[symbol]
            trail_p = high * (1.0 - direction * self._trailing_stop_pct)
            trail_gapped = (
                (direction == 1 and bar_open <= trail_p)
                or (direction == -1 and bar_open >= trail_p)
            )
        elif self._trailing_enabled:
            # No trailing high yet — use entry_price as initial high
            trail_p = entry_price * (1.0 - direction * self._trailing_stop_pct)
            trail_gapped = (
                (direction == 1 and bar_open <= trail_p)
                or (direction == -1 and bar_open >= trail_p)
            )

        # Priority: stop > trail > target (risk-first)
        if stop_gapped:
            return "gap_stop", bar_open
        if trail_gapped:
            return "gap_trail", bar_open
        if target_gapped:
            return "gap_target", bar_open

        return None, None

    # ── Daily loss ──────────────────────────────────────────────────

    def check_daily_loss(self, equity: float | None = None) -> bool:
        """Return True if daily realised loss exceeds the circuit-breaker threshold.

        [P2-6 fix] When ``equity`` is provided, the daily loss limit is
        recalculated as a percentage of *current* equity rather than the
        fixed ``initial_capital``.  This prevents the threshold from being
        too tight when the account is in profit, or too loose when it's in
        drawdown.
        """
        if equity is not None and equity > 0:
            self._max_daily_loss = equity * self._max_daily_loss_pct
        return self._daily_pnl <= -self._max_daily_loss

    def accumulate_daily(self, pnl: float, date: str) -> None:
        if self._daily_date != date:
            self._daily_date = date
            self._daily_pnl = 0.0
        self._daily_pnl += pnl

    @property
    def daily_pnl(self) -> float:
        return self._daily_pnl

    # ── Position size ───────────────────────────────────────────────

    def check_position_size(self, notional: float, equity: float) -> bool:
        return notional <= equity * self._max_position_pct

    # ── Lifecycle ───────────────────────────────────────────────────

    def on_position_closed(self, symbol: str) -> None:
        self._trailing_highs.pop(symbol, None)


def _intraday_exec_price(
    open_p: float, trigger_p: float, direction: int, *, is_stop: bool,
) -> float:
    """Execution price when a stop/target is touched within a bar.

    If the market gapped through the trigger (open already beyond it),
    execution happens at open.  Otherwise at the trigger price.
    """
    if is_stop:
        gapped = (direction == 1 and open_p <= trigger_p) or (direction == -1 and open_p >= trigger_p)
    else:
        gapped = (direction == 1 and open_p >= trigger_p) or (direction == -1 and open_p <= trigger_p)
    return open_p if gapped else trigger_p
