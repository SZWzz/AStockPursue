"""Independent risk manager for paper trading.

Applied as a separate layer between signal generation and trade execution.
Checks existing positions against stop-loss / take-profit / trailing-stop
thresholds and returns forced-exit reasons.  Also enforces per-day loss
limits and per-position size limits.

Key difference from QuantDinger: risk checks are NOT embedded in the signal
execution method.  They live in this single, testable class that takes
(position, price, config) → exit_reason.
"""

from __future__ import annotations

from papertrade.models import RiskConfig


class RiskManager:
    """Composable risk management layer.

    Pipeline order (highest priority first):
      1. stop-loss
      2. trailing-stop
      3. take-profit
    """

    def __init__(self, config: RiskConfig, initial_capital: float) -> None:
        self._stop_loss_pct = -abs(config.stop_loss_pct) / 100.0
        self._take_profit_pct = abs(config.take_profit_pct) / 100.0
        self._trailing_stop_pct = abs(config.trailing_stop_pct) / 100.0 if config.trailing_stop_pct > 0 else 0.0
        self._trailing_enabled = self._trailing_stop_pct > 1e-9
        self._max_daily_loss = initial_capital * abs(config.max_daily_loss_pct) / 100.0
        self._max_position_pct = abs(config.max_position_pct) / 100.0

        # Per-symbol trailing-stop high watermark
        self._trailing_highs: dict[str, float] = {}

        # Daily P&L tracking
        self._daily_pnl: float = 0.0
        self._daily_date: str = ""

    # ── Position checks ─────────────────────────────────────────────

    def check_position(
        self,
        symbol: str,
        direction: int,
        entry_price: float,
        current_price: float,
        current_date: str,
    ) -> str | None:
        """Return an exit reason if the position should be closed, or None.

        Args:
            symbol: Instrument code.
            direction: 1 (long) or -1 (short).
            entry_price: Weighted-average entry price.
            current_price: Last traded price or mark price.
            current_date: ``"YYYY-MM-DD"`` for daily-loss tracking.

        Returns:
            ``"stop_loss"``, ``"trailing_stop"``, ``"take_profit"``, or ``None``.
        """
        if entry_price <= 0:
            return None

        pnl_pct = direction * (current_price - entry_price) / entry_price

        # 1. Stop-loss (highest priority)
        if pnl_pct <= self._stop_loss_pct:
            return "stop_loss"

        # 2. Trailing stop
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

        # 3. Take-profit
        if pnl_pct >= self._take_profit_pct:
            return "take_profit"

        return None

    # ── Daily loss ──────────────────────────────────────────────────

    def check_daily_loss(self) -> bool:
        """Return True if cumulative daily P&L exceeds the configured limit."""
        return self._daily_pnl <= -self._max_daily_loss

    def accumulate_daily(self, pnl: float, date: str) -> None:
        """Add *pnl* to the daily tracker.  Resets on date change."""
        if self._daily_date != date:
            self._daily_date = date
            self._daily_pnl = 0.0
        self._daily_pnl += pnl

    @property
    def daily_pnl(self) -> float:
        return self._daily_pnl

    # ── Position size ───────────────────────────────────────────────

    def check_position_size(self, notional: float, equity: float) -> bool:
        """Return True if *notional* is within the per-position limit."""
        return notional <= equity * self._max_position_pct

    # ── Lifecycle ───────────────────────────────────────────────────

    def on_position_closed(self, symbol: str) -> None:
        """Remove trailing-stop state when the position is closed."""
        self._trailing_highs.pop(symbol, None)
