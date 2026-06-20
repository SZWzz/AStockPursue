"""Order Management System (OMS) — order lifecycle for live & paper trading.

Provides:
  - Order / OrderSide / OrderType / OrderStatus enums & models
  - OrderManager: submit → track → fill → persist lifecycle
  - PostgreSQL persistence for audit trail
  - Callback hooks for broker integration

Backtest fast mode bypasses OMS (direct execution); live & paper trading
route through OrderManager to get a realistic order lifecycle.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ── Enums ────────────────────────────────────────────────────────────────────

class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


class OrderStatus(str, Enum):
    PENDING = "pending"        # Created, not yet sent to broker
    SUBMITTED = "submitted"    # Sent to broker, awaiting ack
    PARTIAL = "partial"        # Partially filled
    FILLED = "filled"          # Fully filled
    CANCELLED = "cancelled"    # Cancelled by user or system
    REJECTED = "rejected"      # Rejected by broker


# Valid status transitions
_STATUS_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.PENDING:   {OrderStatus.SUBMITTED, OrderStatus.CANCELLED},
    OrderStatus.SUBMITTED: {OrderStatus.PARTIAL, OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED},
    OrderStatus.PARTIAL:   {OrderStatus.FILLED, OrderStatus.CANCELLED},
    OrderStatus.FILLED:    set(),   # terminal
    OrderStatus.CANCELLED: set(),   # terminal
    OrderStatus.REJECTED:  set(),   # terminal
}


# ── Models ────────────────────────────────────────────────────────────────────

class Order(BaseModel):
    """A single order in the OMS."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    run_id: str = ""
    symbol: str
    side: OrderSide
    order_type: OrderType = OrderType.MARKET
    quantity: float                     # Target quantity (shares / contracts)
    price: Optional[float] = None       # Limit price (None for market orders)
    status: OrderStatus = OrderStatus.PENDING
    filled_qty: float = 0.0
    avg_fill_price: float = 0.0
    commission: float = 0.0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    submitted_at: Optional[str] = None
    filled_at: Optional[str] = None
    cancelled_at: Optional[str] = None
    reject_reason: str = ""
    notes: str = ""

    @property
    def is_terminal(self) -> bool:
        return self.status in (OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED)

    @property
    def is_active(self) -> bool:
        return not self.is_terminal

    @property
    def remaining_qty(self) -> float:
        return max(0.0, self.quantity - self.filled_qty)


# ── Callback types ───────────────────────────────────────────────────────────

OnOrderUpdate = Callable[[Order], None]
"""Called when an order changes status."""


# ── OrderManager ──────────────────────────────────────────────────────────────

class OrderManager:
    """Manages the full lifecycle of orders.

    Usage::

        oms = OrderManager(run_id="run-123")
        order = oms.submit("600519.SH", OrderSide.BUY, 100, OrderType.LIMIT, 1850.0)
        oms.acknowledge(order.id)           # broker accepted
        oms.fill(order.id, 100, 1850.0, 5.0) # fully filled
        print(order.status)                  # 'filled'
    """

    def __init__(self, run_id: str = "") -> None:
        self.run_id = run_id
        self._orders: dict[str, Order] = {}
        self._callbacks: list[OnOrderUpdate] = []

    # ── Callbacks ─────────────────────────────────────────────────────────

    def on_update(self, cb: OnOrderUpdate) -> None:
        """Register a callback invoked on every status change."""
        self._callbacks.append(cb)

    def _emit(self, order: Order) -> None:
        for cb in self._callbacks:
            try:
                cb(order)
            except Exception:
                logger.debug("OMS callback failed", exc_info=True)

    # ── Order CRUD ────────────────────────────────────────────────────────

    def submit(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        price: Optional[float] = None,
        notes: str = "",
    ) -> Order:
        """Create and submit a new order."""
        order = Order(
            run_id=self.run_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            notes=notes,
        )
        self._orders[order.id] = order
        logger.info("OMS order created: %s %s %s qty=%s", order.id, side.value, symbol, quantity)
        self._emit(order)
        return order

    def acknowledge(self, order_id: str) -> Order:
        """Broker accepted the order → SUBMITTED."""
        order = self._get(order_id)
        order.status = OrderStatus.SUBMITTED
        order.submitted_at = datetime.now(timezone.utc).isoformat()
        order.updated_at = datetime.now(timezone.utc).isoformat()
        logger.info("OMS order %s → submitted", order_id)
        self._emit(order)
        return order

    def fill(
        self,
        order_id: str,
        filled_qty: float,
        fill_price: float,
        commission: float = 0.0,
    ) -> Order:
        """Report a fill (partial or full)."""
        order = self._get(order_id)
        order.filled_qty += filled_qty
        order.commission += commission
        # Weighted average fill price
        if order.avg_fill_price == 0:
            order.avg_fill_price = fill_price
        else:
            total_value = (order.avg_fill_price * (order.filled_qty - filled_qty)) + (fill_price * filled_qty)
            order.avg_fill_price = total_value / order.filled_qty if order.filled_qty > 0 else 0

        if order.filled_qty >= order.quantity:
            order.status = OrderStatus.FILLED
            order.filled_at = datetime.now(timezone.utc).isoformat()
        else:
            order.status = OrderStatus.PARTIAL

        order.updated_at = datetime.now(timezone.utc).isoformat()
        logger.info("OMS order %s fill: %s/%s @ %s", order_id, order.filled_qty, order.quantity, fill_price)
        self._emit(order)
        return order

    def cancel(self, order_id: str, reason: str = "") -> Order:
        """Cancel an active order."""
        order = self._get(order_id)
        if order.is_terminal:
            logger.warning("Cannot cancel terminal order %s (%s)", order_id, order.status.value)
            return order
        order.status = OrderStatus.CANCELLED
        order.cancelled_at = datetime.now(timezone.utc).isoformat()
        order.updated_at = datetime.now(timezone.utc).isoformat()
        order.reject_reason = reason
        logger.info("OMS order %s cancelled: %s", order_id, reason)
        self._emit(order)
        return order

    def reject(self, order_id: str, reason: str = "") -> Order:
        """Mark an order as rejected."""
        order = self._get(order_id)
        if order.is_terminal:
            return order
        order.status = OrderStatus.REJECTED
        order.reject_reason = reason
        order.updated_at = datetime.now(timezone.utc).isoformat()
        logger.warning("OMS order %s rejected: %s", order_id, reason)
        self._emit(order)
        return order

    # ── Query ─────────────────────────────────────────────────────────────

    def get(self, order_id: str) -> Optional[Order]:
        return self._orders.get(order_id)

    def _get(self, order_id: str) -> Order:
        order = self._orders.get(order_id)
        if order is None:
            raise KeyError(f"Order not found: {order_id}")
        return order

    def get_active(self, symbol: Optional[str] = None) -> list[Order]:
        """Return all active (non-terminal) orders, optionally filtered by symbol."""
        orders = [o for o in self._orders.values() if o.is_active]
        if symbol:
            orders = [o for o in orders if o.symbol == symbol]
        return orders

    def get_all(self, symbol: Optional[str] = None) -> list[Order]:
        """Return all orders, optionally filtered by symbol."""
        if symbol:
            return [o for o in self._orders.values() if o.symbol == symbol]
        return list(self._orders.values())

    def get_active_symbols(self) -> set[str]:
        """Symbols with pending/active orders."""
        return {o.symbol for o in self._orders.values() if o.is_active}

    def cancel_all_active(self, reason: str = "") -> list[Order]:
        """Cancel all active orders."""
        cancelled = []
        for o in list(self._orders.values()):
            if o.is_active:
                self.cancel(o.id, reason)
                cancelled.append(o)
        return cancelled

    def __len__(self) -> int:
        return len(self._orders)


# ── Persistence ───────────────────────────────────────────────────────────────

_OMS_DDL = """
CREATE TABLE IF NOT EXISTS vt_orders (
    id            VARCHAR(16) PRIMARY KEY,
    run_id        VARCHAR(64) NOT NULL,
    symbol        VARCHAR(32) NOT NULL,
    side          VARCHAR(8)  NOT NULL,
    order_type    VARCHAR(8)  NOT NULL DEFAULT 'market',
    quantity      DOUBLE PRECISION NOT NULL,
    price         DOUBLE PRECISION,
    status        VARCHAR(16) NOT NULL DEFAULT 'pending',
    filled_qty    DOUBLE PRECISION NOT NULL DEFAULT 0,
    avg_fill_price DOUBLE PRECISION NOT NULL DEFAULT 0,
    commission    DOUBLE PRECISION NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    submitted_at  TEXT,
    filled_at     TEXT,
    cancelled_at  TEXT,
    reject_reason TEXT NOT NULL DEFAULT '',
    notes         TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_vt_orders_run_id ON vt_orders(run_id);
CREATE INDEX IF NOT EXISTS idx_vt_orders_status ON vt_orders(status);
"""


def init_oms_table() -> None:
    """Create vt_orders table (idempotent)."""
    try:
        from src.db.pool import init_pool, get_connection
        init_pool()
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(_OMS_DDL)
        logger.info("vt_orders table ready")
    except Exception:
        logger.warning("Failed to initialise vt_orders table", exc_info=True)


def save_order_to_db(order: Order) -> None:
    """Persist a single order to PostgreSQL."""
    try:
        from src.db.pool import get_connection
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO vt_orders (id, run_id, symbol, side, order_type,
                        quantity, price, status, filled_qty, avg_fill_price,
                        commission, created_at, updated_at, submitted_at,
                        filled_at, cancelled_at, reject_reason, notes)
                    VALUES (%s,%s,%s,%s,%s, %s,%s,%s,%s,%s, %s,%s,%s,%s, %s,%s,%s,%s)
                    ON CONFLICT (id) DO UPDATE SET
                        status = EXCLUDED.status,
                        filled_qty = EXCLUDED.filled_qty,
                        avg_fill_price = EXCLUDED.avg_fill_price,
                        commission = EXCLUDED.commission,
                        updated_at = EXCLUDED.updated_at,
                        submitted_at = EXCLUDED.submitted_at,
                        filled_at = EXCLUDED.filled_at,
                        cancelled_at = EXCLUDED.cancelled_at,
                        reject_reason = EXCLUDED.reject_reason
                    """,
                    (
                        order.id, order.run_id, order.symbol, order.side.value,
                        order.order_type.value, order.quantity, order.price,
                        order.status.value, order.filled_qty, order.avg_fill_price,
                        order.commission, order.created_at, order.updated_at,
                        order.submitted_at, order.filled_at, order.cancelled_at,
                        order.reject_reason, order.notes,
                    ),
                )
    except Exception:
        logger.debug("Failed to persist order %s", order.id, exc_info=True)
