"""Futu OpenAPI broker adapter — real trading via FutuOpenD.

Requires a running FutuOpenD instance (default: localhost:11111).

Supports:
  - A-share (Shanghai/Shenzhen) via ``TrdMarket.CN``
  - HK stocks via ``TrdMarket.HK``
  - US stocks via ``TrdMarket.US`` (if account permits)

Reference: https://openapi.futunn.com/
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Optional

# TODO(P5): migrate to Go gRPC equivalents:
#   - engines → EngineService (not yet exposed)
#   - risk → RiskService (not yet exposed)
#   - brokers → BrokerService (not yet exposed)

logger = logging.getLogger(__name__)


# ── Symbol helpers ────────────────────────────────────────────────────────────

def _to_futu_symbol(code: str) -> str:
    """Convert project symbol to Futu format: ``600519.SH → SH.600519``."""
    upper = (code or "").strip().upper()
    if upper.endswith(".HK"):
        return f"HK.{upper[:-3].zfill(5)}"
    if upper.endswith(".SZ"):
        return f"SZ.{upper[:-3].zfill(6)}"
    if upper.endswith((".SH", ".SS")):
        return f"SH.{upper[:-3].zfill(6)}"
    if upper.endswith(".BJ"):
        return f"SZ.{upper[:-3].zfill(6)}"  # Futu routes BJ via SZ
    if upper.endswith(".US"):
        return f"US.{upper[:-3]}"
    # Bare digits: guess market
    if upper.isdigit() and len(upper) <= 5:
        return f"HK.{upper.zfill(5)}"
    if upper.isdigit() and len(upper) == 6:
        return f"SH.{upper}" if upper.startswith(("6", "9")) else f"SZ.{upper}"
    return upper


def _futu_market(code: str) -> int:
    """Map symbol to Futu TrdMarket constant."""
    upper = (code or "").strip().upper()
    if ".HK" in upper or (upper.isdigit() and len(upper) <= 5):
        return 1   # HK
    if ".US" in upper:
        return 2   # US
    return 0       # CN (A-share)


# ── Data models ───────────────────────────────────────────────────────────────

@dataclass
class FutuAccountInfo:
    """Account summary from Futu."""
    account_id: str = ""
    total_assets: float = 0.0
    cash: float = 0.0
    market_value: float = 0.0
    frozen_cash: float = 0.0
    available_cash: float = 0.0
    currency: str = "HKD"


@dataclass
class FutuPosition:
    """A single position in the Futu account."""
    symbol: str = ""
    name: str = ""
    qty: float = 0.0
    cost_price: float = 0.0
    current_price: float = 0.0
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    currency: str = ""


@dataclass
class FutuOrderResult:
    """Result of submitting an order."""
    order_id: str = ""
    status: str = ""           # filled / submitted / cancelled / rejected
    filled_qty: float = 0.0
    filled_price: float = 0.0
    reject_reason: str = ""


# ── Broker ────────────────────────────────────────────────────────────────────

class FutuBroker:
    """Real trading via Futu OpenAPI.

    Usage::

        broker = FutuBroker(host="127.0.0.1", port=11111)
        if broker.connect():
            acc = broker.query_account()
            positions = broker.query_positions()
            result = broker.place_order("600519.SH", "BUY", 100, price=1850.0)
            broker.close()
    """

    def __init__(self, host: str = "", port: int = 0):
        self._host = host or os.getenv("FUTU_HOST", "127.0.0.1")
        self._port = port or int(os.getenv("FUTU_PORT", "11111"))
        self._trade_ctx: Any = None
        self._quote_ctx: Any = None
        self._connected = False

    # ── Connection ────────────────────────────────────────────────────────

    def connect(self) -> bool:
        """Connect to FutuOpenD. Returns True on success."""
        try:
            from futu import OpenSecTradeContext, OpenQuoteContext
            self._quote_ctx = OpenQuoteContext(host=self._host, port=self._port)
            self._trade_ctx = OpenSecTradeContext(host=self._host, port=self._port)
            self._connected = True
            logger.info("FutuBroker connected to %s:%d", self._host, self._port)
            return True
        except Exception as exc:
            logger.error("FutuBroker connect failed: %s", exc)
            self._connected = False
            return False

    def close(self) -> None:
        """Close connections."""
        if self._trade_ctx:
            try:
                self._trade_ctx.close()
            except Exception:
                pass
            self._trade_ctx = None
        if self._quote_ctx:
            try:
                self._quote_ctx.close()
            except Exception:
                pass
            self._quote_ctx = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ── Account ───────────────────────────────────────────────────────────

    def query_account(self) -> Optional[FutuAccountInfo]:
        """Query account fund information."""
        if not self._ensure_connected():
            return None
        try:
            from futu import RET_OK
            ret, data = self._trade_ctx.accinfo_query()
            if ret != RET_OK:
                logger.warning("Futu accinfo_query failed: %s", data)
                return None
            row = data.iloc[0] if len(data) > 0 else None
            if row is None:
                return None
            return FutuAccountInfo(
                account_id=str(row.get("acc_id", "")),
                total_assets=float(row.get("total_assets", 0)),
                cash=float(row.get("cash", 0)),
                market_value=float(row.get("market_val", 0)),
                frozen_cash=float(row.get("frozen_cash", 0)),
                available_cash=float(row.get("avl_withdrawal_cash", 0)),
                currency=str(row.get("currency", "HKD")),
            )
        except Exception as exc:
            logger.error("Futu query_account error: %s", exc)
            return None

    # ── Positions ─────────────────────────────────────────────────────────

    def query_positions(self, code: str = "") -> list[FutuPosition]:
        """Query current positions. If *code* is given, filter to that symbol."""
        if not self._ensure_connected():
            return []
        try:
            from futu import RET_OK
            market = _futu_market(code) if code else 0
            ret, data = self._trade_ctx.position_list_query(code=code or "", trd_market=market)
            if ret != RET_OK:
                logger.warning("Futu position_list_query failed: %s", data)
                return []
            positions = []
            for _, row in data.iterrows():
                positions.append(FutuPosition(
                    symbol=str(row.get("code", "")),
                    name=str(row.get("stock_name", "")),
                    qty=float(row.get("qty", 0)),
                    cost_price=float(row.get("cost_price", 0)),
                    current_price=float(row.get("nominal_price", 0)),
                    market_value=float(row.get("market_val", 0)),
                    unrealized_pnl=float(row.get("unrealized_pl", 0)),
                    realized_pnl=float(row.get("realized_pl", 0)),
                    currency=str(row.get("currency", "")),
                ))
            return positions
        except Exception as exc:
            logger.error("Futu query_positions error: %s", exc)
            return []

    # ── Orders ────────────────────────────────────────────────────────────

    def place_order(
        self,
        code: str,
        side: str,           # "BUY" or "SELL"
        qty: float,
        price: Optional[float] = None,
    ) -> Optional[FutuOrderResult]:
        """Place an order.

        Args:
            code: Project symbol (e.g. ``600519.SH``, ``00700.HK``).
            side: ``"BUY"`` or ``"SELL"``.
            qty: Quantity in shares.
            price: Limit price. ``None`` for market order.

        Returns:
            ``FutuOrderResult`` or ``None`` on connection error.
        """
        if not self._ensure_connected():
            return None
        try:
            from futu import RET_OK, TrdSide

            futu_code = _to_futu_symbol(code)
            trd_side = TrdSide.BUY if side.upper() == "BUY" else TrdSide.SELL

            if price is not None:
                ret, data = self._trade_ctx.place_order(
                    price=float(price),
                    qty=int(qty),
                    code=futu_code,
                    trd_side=trd_side,
                    order_type=0,  # 0=normal limit
                    trd_env=0,     # 0=real
                )
            else:
                # Market order — use special order_type for market
                ret, data = self._trade_ctx.place_order(
                    price=0.0,
                    qty=int(qty),
                    code=futu_code,
                    trd_side=trd_side,
                    order_type=0,
                    trd_env=0,
                )

            if ret != RET_OK:
                return FutuOrderResult(status="rejected", reject_reason=str(data))

            row = data.iloc[0] if len(data) > 0 else None
            if row is None:
                return FutuOrderResult(status="rejected", reject_reason="empty response")

            return FutuOrderResult(
                order_id=str(row.get("order_id", "")),
                status=str(row.get("order_status", "submitted")),
            )
        except Exception as exc:
            logger.error("Futu place_order error: %s", exc)
            return FutuOrderResult(status="rejected", reject_reason=str(exc)[:200])

    def cancel_order(self, order_id: str, code: str = "") -> bool:
        """Cancel a pending order by order_id."""
        if not self._ensure_connected():
            return False
        try:
            from futu import RET_OK
            market = _futu_market(code) if code else 0
            futu_code = _to_futu_symbol(code) if code else ""
            ret, data = self._trade_ctx.modify_order(
                modify_order_op=1,  # 1=cancel
                order_id=order_id,
                qty=0,
                price=0.0,
                code=futu_code,
                trd_env=0,
            )
            if ret != RET_OK:
                logger.warning("Futu cancel_order failed: %s", data)
                return False
            return True
        except Exception as exc:
            logger.error("Futu cancel_order error: %s", exc)
            return False

    def query_order(self, order_id: str) -> Optional[dict]:
        """Query a single order's status."""
        if not self._ensure_connected():
            return None
        try:
            from futu import RET_OK

            ret, data = self._trade_ctx.order_list_query(order_id=order_id)
            if ret != RET_OK or data.empty:
                return None
            row = data.iloc[0]
            return {
                "order_id": str(row.get("order_id", "")),
                "status": str(row.get("order_status", "")),
                "filled_qty": float(row.get("dealt_qty", 0)),
                "filled_price": float(row.get("dealt_avg_price", 0)),
                "code": str(row.get("code", "")),
                "side": str(row.get("trd_side", "")),
            }
        except Exception as exc:
            logger.error("Futu query_order error: %s", exc)
            return None

    # ── Internal ──────────────────────────────────────────────────────────

    def _ensure_connected(self) -> bool:
        if not self._connected:
            return self.connect()
        return True
