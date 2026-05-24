"""Explicit state machine for paper trading strategies.

Enforces legal state transitions at the API level so that impossible
transitions (e.g. long → short without closing first) are rejected
before any trade execution logic runs.

This is the key differentiator from QuantDinger, which uses implicit
position truthiness checks scattered across ``_execute_signal()``.
"""

from __future__ import annotations

from papertrade.models import StrategyState


class InvalidTransitionError(ValueError):
    """Raised when a state transition is not allowed."""


class FlatStateMachine:
    """State machine that only allows flat ↔ long and flat ↔ short.

    No direct long ↔ short transitions — the caller must transition
    through ``FLAT`` first (i.e. close the existing position before
    opening one in the opposite direction).
    """

    _ALLOWED: dict[StrategyState, set[StrategyState]] = {
        StrategyState.FLAT:  {StrategyState.LONG, StrategyState.SHORT},
        StrategyState.LONG:  {StrategyState.FLAT},
        StrategyState.SHORT: {StrategyState.FLAT},
    }

    def __init__(self, initial: StrategyState = StrategyState.FLAT) -> None:
        self._state = initial

    # ── Public API ──────────────────────────────────────────────────

    @property
    def state(self) -> StrategyState:
        return self._state

    def can_transition(self, target: StrategyState) -> bool:
        """Return True if transitioning from current state to *target* is legal."""
        return target in self._ALLOWED[self._state]

    def transition(self, target: StrategyState) -> None:
        """Execute the transition.

        Raises:
            InvalidTransitionError: If the transition is not allowed.
        """
        if not self.can_transition(target):
            raise InvalidTransitionError(
                f"Invalid state transition: {self._state.value} → {target.value}"
            )
        self._state = target

    def force(self, target: StrategyState) -> None:
        """Force-set state (bypasses validation).

        Only intended for administrative actions (manual close, full liquidation).
        """
        self._state = target
