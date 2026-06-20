"""Paper trading engine — re-exports the unified TradingEngine.

Backward-compatibility wrapper: ``PaperTradingEngine`` accepts the old
constructor signature and translates it to ``TradingEngine``.
"""

from __future__ import annotations

from typing import Any

from src.trading.engine import BarResult, TradingEngine  # noqa: F401


class PaperTradingEngine(TradingEngine):
    """Backward-compatible alias for TradingEngine.

    Accepts the old ``(config, signal_module, market_engine, risk_manager,
    state_machine)`` signature and translates to ``TradingEngine``.
    """

    def __init__(
        self,
        config: dict,
        signal_module: Any,
        market_engine: Any,
        risk_manager: Any,
        state_machine: Any | None = None,
    ) -> None:
        from src.trading.signal_adapter import SignalAdapter
        signal_adapter = SignalAdapter(signal_module)
        super().__init__(
            config=config,
            signal_adapter=signal_adapter,
            market_engine=market_engine,
            risk_pipeline=risk_manager,
            state_machine=state_machine,
        )
