"""Unified trading execution — one on_bar() pipeline for backtest and live."""

# TODO(P6): TradingEngine and RiskPipeline migrated to Go — remove Python copies once all consumers updated
from src.trading.engine import TradingEngine  # noqa: F401
from src.trading.signal_adapter import SignalAdapter
from src.trading.backtest_driver import BacktestDriver
from src.trading.live_driver import LiveDriver
from src.trading.risk_pipeline import RiskPipeline  # noqa: F401
from src.trading.state_machine import FlatStateMachine

__all__ = [
    "TradingEngine",
    "SignalAdapter",
    "BacktestDriver",
    "LiveDriver",
    "RiskPipeline",
    "FlatStateMachine",
]
