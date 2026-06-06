"""Broker integrations — real trading execution adapters."""

from .base import BaseBroker, BrokerOrder, BrokerPosition, BrokerBalance
from .factory import create_broker, register_broker, list_brokers

# Auto-register bundled brokers on import
from . import binance  # noqa: F401
from . import okx      # noqa: F401

__all__ = [
    "BaseBroker", "BrokerOrder", "BrokerPosition", "BrokerBalance",
    "create_broker", "register_broker", "list_brokers",
]
