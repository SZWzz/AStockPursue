"""Tests for broker factory — registration and creation."""

import pytest
from src.trading.brokers.base import BaseBroker, BrokerOrder, BrokerPosition, BrokerBalance
from src.trading.brokers.factory import register_broker, create_broker, list_brokers, _BROKER_REGISTRY


class TestBrokerFactory:
    """Unit tests for broker factory pattern."""

    def setup_method(self):
        """Clean up test registrations."""
        _BROKER_REGISTRY.pop("test_mock", None)

    def test_register_and_create(self):
        @register_broker
        class MockBroker(BaseBroker):
            exchange_id = "test_mock"

            async def place_order(self, symbol, side, order_type, quantity, price=None):
                return BrokerOrder(symbol=symbol, side=side, status="filled")

            async def cancel_order(self, order_id, symbol=""):
                return True

            async def get_order(self, order_id, symbol=""):
                return BrokerOrder(order_id=order_id)

            async def get_open_orders(self, symbol=""):
                return []

            async def get_position(self, symbol):
                return None

            async def get_positions(self):
                return []

            async def get_balance(self):
                return BrokerBalance(total=10000, available=10000, currency="USDT")

            def get_fee_rate(self, symbol=""):
                return {"maker": 0.001, "taker": 0.001}

            async def test_connection(self):
                return True

        assert "test_mock" in list_brokers()
        broker = create_broker("test_mock", {})
        assert broker.exchange_id == "test_mock"

    def test_create_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown exchange"):
            create_broker("nonexistent_exchange", {})

    def test_list_brokers_includes_bundled(self):
        brokers = list_brokers()
        assert "binance" in brokers
        assert "okx" in brokers

    def test_empty_exchange_id_raises(self):
        with pytest.raises(ValueError, match="empty exchange_id"):
            @register_broker
            class BadBroker(BaseBroker):
                exchange_id = ""
                async def place_order(self, *a, **kw): ...
                async def cancel_order(self, *a, **kw): return True
                async def get_order(self, *a, **kw): return None
                async def get_open_orders(self, *a, **kw): return []
                async def get_position(self, *a, **kw): return None
                async def get_positions(self, *a, **kw): return []
                async def get_balance(self, *a, **kw): return BrokerBalance()
                def get_fee_rate(self, *a, **kw): return {}
                async def test_connection(self, *a, **kw): return True
