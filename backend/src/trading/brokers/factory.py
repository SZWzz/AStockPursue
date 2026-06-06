"""Broker factory — registry-based creation of exchange adapters.

Usage::

    broker = create_broker("binance", {"api_key": "...", "secret_key": "..."})
    positions = await broker.get_positions()
"""

from __future__ import annotations

from typing import Type

from .base import BaseBroker

_BROKER_REGISTRY: dict[str, Type[BaseBroker]] = {}


def register_broker(cls: Type[BaseBroker]) -> Type[BaseBroker]:
    """Decorator: register a broker class by its ``exchange_id``."""
    eid = cls.exchange_id
    if not eid:
        raise ValueError(f"Broker class {cls.__name__} has empty exchange_id")
    _BROKER_REGISTRY[eid] = cls
    return cls


def create_broker(exchange_id: str, config: dict) -> BaseBroker:
    """Create a broker instance from configuration.

    Args:
        exchange_id: Broker identifier (``"binance"``, ``"okx"``, ``"futu"``).
        config: Connection parameters — varies by exchange.

    Returns:
        Configured broker instance.

    Raises:
        ValueError: If *exchange_id* is not registered.
    """
    cls = _BROKER_REGISTRY.get(exchange_id)
    if cls is None:
        raise ValueError(
            f"Unknown exchange: {exchange_id!r}. "
            f"Available: {list(_BROKER_REGISTRY)}"
        )
    return cls(**config)


def list_brokers() -> list[str]:
    """Return the list of registered exchange ids."""
    return list(_BROKER_REGISTRY.keys())
