"""Explicit state machine for trading strategies.

Enforces legal state transitions: flat ↔ long, flat ↔ short.
No direct long ↔ short transitions — must close first.
"""

from __future__ import annotations

from enum import Enum


class StrategyState(str, Enum):
    FLAT = "flat"
    LONG = "long"
    SHORT = "short"


class InvalidTransitionError(ValueError):
    """Raised when a state transition is not allowed."""


class FlatStateMachine:
    """State machine that only allows flat ↔ long and flat ↔ short."""

    _ALLOWED: dict[StrategyState, set[StrategyState]] = {
        StrategyState.FLAT:  {StrategyState.LONG, StrategyState.SHORT},
        StrategyState.LONG:  {StrategyState.FLAT},
        StrategyState.SHORT: {StrategyState.FLAT},
    }

    def __init__(self, initial: StrategyState = StrategyState.FLAT) -> None:
        self._state = initial

    @property
    def state(self) -> StrategyState:
        return self._state

    def can_transition(self, target: StrategyState) -> bool:
        return target in self._ALLOWED[self._state]

    def transition(self, target: StrategyState) -> None:
        if not self.can_transition(target):
            raise InvalidTransitionError(
                f"Invalid state transition: {self._state.value} → {target.value}"
            )
        self._state = target

    def force(self, target: StrategyState) -> None:
        self._state = target
