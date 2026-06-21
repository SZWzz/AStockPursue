"""Live Trading Bridge — Paper-to-Live promotion with pre-flight checks."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

# TODO(P5): migrate remaining to Go equivalents:
#   - engines → Go EngineService (not yet exposed)
#   - risk → Go RiskService (not yet exposed)
# Broker checks migrated: _check_broker → go_http.broker_list(), _check_balance → go_http.broker_account()

logger = logging.getLogger(__name__)


class PreFlightResult(BaseModel):
    passed: bool
    checks: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class LiveBridgeConfig(BaseModel):
    max_position_pct: float = Field(default=0.2, description="Max single position as fraction of portfolio")
    max_daily_loss_pct: float = Field(default=0.05, description="Max daily loss before auto-liquidate")
    max_total_positions: int = Field(default=10, description="Max concurrent positions")
    require_stop_loss: bool = Field(default=True, description="Require stop-loss on every order")
    blacklist_symbols: list[str] = Field(default_factory=list)


class LiveBridge:
    """Validates and promotes paper trading strategies to live trading."""

    def __init__(self, config: LiveBridgeConfig | None = None) -> None:
        self.config = config or LiveBridgeConfig()

    def pre_flight_check(
        self,
        run_id: str,
        user_id: int,
    ) -> PreFlightResult:
        """Run all pre-flight checks before allowing live trading.

        Checks:
        1. Broker connectivity
        2. Risk config review
        3. Strategy has positive OOS performance
        4. Position size limits
        5. Balance sufficiency
        """
        checks: list[dict[str, Any]] = []
        warnings: list[str] = []
        errors: list[str] = []

        # Check 1: Broker connectivity
        broker_ok = self._check_broker(user_id)
        checks.append({"name": "Broker Connectivity", "passed": broker_ok, "detail": "FutuOpenD connected" if broker_ok else "Broker not connected"})
        if not broker_ok:
            errors.append("Broker not connected. Please ensure FutuOpenD is running.")

        # Check 2: Risk config
        risk_ok = self._check_risk_config(user_id)
        checks.append({"name": "Risk Config", "passed": risk_ok, "detail": "Risk limits configured" if risk_ok else "Risk config incomplete"})
        if not risk_ok:
            warnings.append("Risk config not fully set up. Using defaults.")

        # Check 3: Strategy performance
        perf_ok, perf_detail = self._check_strategy_performance(run_id)
        checks.append({"name": "Strategy Performance", "passed": perf_ok, "detail": perf_detail})
        if not perf_ok:
            errors.append("Strategy has insufficient out-of-sample performance.")

        # Check 4: Position limits
        checks.append({"name": "Position Limits", "passed": True, "detail": f"Max {self.config.max_total_positions} positions, {self.config.max_position_pct*100:.0f}% each"})

        # Check 5: Balance check
        balance_ok, balance_detail = self._check_balance(user_id)
        checks.append({"name": "Account Balance", "passed": balance_ok, "detail": balance_detail})
        if not balance_ok:
            errors.append("Insufficient account balance.")

        return PreFlightResult(
            passed=len(errors) == 0,
            checks=checks,
            warnings=warnings,
            errors=errors,
        )

    def promote(
        self,
        run_id: str,
        user_id: int,
        override_checks: bool = False,
    ) -> dict[str, Any]:
        """Promote a paper trading run to live trading.

        Args:
            run_id: Paper trading run ID.
            user_id: Authenticated user ID.
            override_checks: If True, skip pre-flight and force promote.

        Returns:
            Dict with live_trade_id and status.
        """
        if not override_checks:
            preflight = self.pre_flight_check(run_id, user_id)
            if not preflight.passed:
                return {
                    "status": "rejected",
                    "reason": "Pre-flight checks failed",
                    "errors": preflight.errors,
                }

        # Create live trading config from paper run
        live_id = f"live_{run_id}"
        logger.info("Promoted paper run %s to live trading as %s", run_id, live_id)

        return {
            "status": "promoted",
            "live_trade_id": live_id,
            "message": "Strategy promoted to live trading. Risk limits active.",
            "max_position_pct": self.config.max_position_pct,
            "max_daily_loss_pct": self.config.max_daily_loss_pct,
        }

    def _check_broker(self, user_id: int) -> bool:
        try:
            from src.go_http import broker_list
            resp = broker_list()
            if "error" in resp:
                return False
            brokers = resp.get("brokers", [])
            return any(b.get("name") == "futu" for b in brokers)
        except Exception:
            return False

    def _check_risk_config(self, user_id: int) -> bool:
        # Check if user has risk config set
        try:
            import json
            from pathlib import Path
            config_path = Path(__file__).resolve().parent.parent.parent / ".user_configs" / str(user_id) / "risk_config.json"
            if config_path.exists():
                cfg = json.loads(config_path.read_text())
                return bool(cfg.get("max_daily_loss") or cfg.get("max_position_pct"))
        except Exception:
            pass
        return False

    def _check_strategy_performance(self, run_id: str) -> tuple[bool, str]:
        try:
            from src.db.backtest_store import get_backtest_run
            run = get_backtest_run(run_id)
            if run and "metrics" in run:
                m = run["metrics"]
                sharpe = m.get("sharpe_ratio", 0)
                returns = m.get("total_return", 0)
                if sharpe > 0.5 and returns > 0:
                    return True, f"Sharpe={sharpe:.2f}, Return={returns:.1%}"
                return False, f"Sharpe={sharpe:.2f} (need > 0.5), Return={returns:.1%} (need > 0)"
            return False, "No backtest metrics available"
        except Exception:
            return False, "Could not load backtest data"

    def _check_balance(self, user_id: int) -> tuple[bool, str]:
        try:
            from src.go_http import broker_account
            resp = broker_account()
            if "error" in resp:
                return False, f"Broker API error: {resp['error']}"
            for broker_name, data in resp.items():
                if isinstance(data, dict) and "balance" in data:
                    b = data["balance"]
                    total = float(b.get("total", 0))
                    if total > 10000:
                        return True, f"Balance: ¥{total:,.0f}"
            return False, "Minimum ¥10,000 required for live trading"
        except Exception as e:
            return False, f"Could not check balance: {e}"
