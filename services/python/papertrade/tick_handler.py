"""Signal bridge — re-exports SignalAdapter from the unified trading package."""

from src.trading.signal_adapter import OptimizerAdapter, SignalAdapter, TickHandler  # noqa: F401

# Backward-compatible alias
SignalBridge = SignalAdapter
