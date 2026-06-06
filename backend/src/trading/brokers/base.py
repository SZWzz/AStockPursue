"""Broker abstract base — common interface for all exchange/broker adapters.

Each concrete implementation handles:
  1. REST API signing and requests
  2. Order creation / cancellation / query
  3. Position / balance queries
  4. Fee rate lookups
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BrokerOrder:
    """Standardised order representation across all brokers."""
    order_id: str = ""
    symbol: str = ""
    side: str = ""             # buy | sell
    order_type: str = ""       # market | limit
    price: float = 0.0
    quantity: float = 0.0
    filled_qty: float = 0.0
    filled_price: float = 0.0
    status: str = "pending"    # pending | submitted | partial | filled | cancelled | rejected
    reject_reason: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class BrokerPosition:
    """Standardised position representation across all brokers."""
    symbol: str = ""
    quantity: float = 0.0
    avg_price: float = 0.0
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    metadata: dict = field(default_factory=dict)


@dataclass
class BrokerBalance:
    """Standardised balance representation across all brokers."""
    total: float = 0.0
    available: float = 0.0
    frozen: float = 0.0
    currency: str = "USDT"


class BaseBroker(ABC):
    """Abstract base for all exchange/broker adapters.

    Subclasses must define ``exchange_id`` and implement all abstract methods.
    """

    exchange_id: str = ""

    @abstractmethod
    async def place_order(
        self, symbol: str, side: str, order_type: str,
        quantity: float, price: float | None = None,
    ) -> BrokerOrder:
        """Place a new order.  Returns the order with exchange-assigned id."""
        ...

    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: str = "") -> bool:
        """Cancel an existing order by id.  Returns True on success."""
        ...

    @abstractmethod
    async def get_order(self, order_id: str, symbol: str = "") -> BrokerOrder | None:
        """Query a single order by id."""
        ...

    @abstractmethod
    async def get_open_orders(self, symbol: str = "") -> list[BrokerOrder]:
        """List all currently open orders."""
        ...

    @abstractmethod
    async def get_position(self, symbol: str) -> BrokerPosition | None:
        """Get current position for a single symbol."""
        ...

    @abstractmethod
    async def get_positions(self) -> list[BrokerPosition]:
        """Get all current open positions."""
        ...

    @abstractmethod
    async def get_balance(self) -> BrokerBalance:
        """Get account balance."""
        ...

    @abstractmethod
    def get_fee_rate(self, symbol: str = "") -> dict[str, float]:
        """Return fee rates: ``{"maker": 0.0002, "taker": 0.0005}``."""
        ...

    @abstractmethod
    async def test_connection(self) -> bool:
        """Verify that the broker connection is healthy."""
        ...
