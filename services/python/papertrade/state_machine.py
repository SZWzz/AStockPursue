"""State machine — re-exports FlatStateMachine from the unified trading package."""

from src.trading.state_machine import (  # noqa: F401
    FlatStateMachine,
    InvalidTransitionError,
    StrategyState,
)
