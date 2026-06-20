"""OKX perpetual futures broker adapter.

Uses ccxt (already a project dependency) as the REST client.
Supports both live and demo trading modes.

Requires config:
    api_key: OKX API key
    secret_key: OKX secret key
    passphrase: OKX passphrase
    demo: bool (default True)
"""

from __future__ import annotations

import logging
from typing import Optional

from .base import BaseBroker, BrokerBalance, BrokerOrder, BrokerPosition
from .factory import register_broker

logger = logging.getLogger(__name__)


@register_broker
class OKXBroker(BaseBroker):
    """OKX perpetual futures via ccxt."""

    exchange_id = "okx"

    def __init__(
        self, api_key: str = "", secret_key: str = "",
        passphrase: str = "", demo: bool = True, **kwargs,
    ) -> None:
        import ccxt.asyncio_support as ccxt_async

        config = {
            "apiKey": api_key,
            "secret": secret_key,
            "password": passphrase,
            "options": {"defaultType": "swap"},
        }
        if demo:
            config["options"]["demo"] = True
        self._exchange = ccxt_async.okx(config)
        self._demo = demo

    # ── Order management ───────────────────────────────────────────────────

    async def place_order(
        self, symbol: str, side: str, order_type: str,
        quantity: float, price: float | None = None,
    ) -> BrokerOrder:
        try:
            params = {}
            if order_type == "limit" and price is not None:
                params["price"] = price

            raw = await self._exchange.create_order(
                symbol.upper(), order_type, side.lower(),
                quantity, price, params,
            )
            return BrokerOrder(
                order_id=str(raw.get("id", "")),
                symbol=symbol.upper(),
                side=side,
                order_type=order_type,
                price=float(raw.get("price", 0) or 0),
                quantity=float(raw.get("amount", 0) or 0),
                filled_qty=float(raw.get("filled", 0) or 0),
                filled_price=float(raw.get("average", 0) or 0),
                status=raw.get("status", "pending"),
            )
        except Exception as exc:
            logger.error("OKX place_order failed: %s", exc)
            return BrokerOrder(
                symbol=symbol, side=side, order_type=order_type,
                status="rejected", reject_reason=str(exc)[:200],
            )

    async def cancel_order(self, order_id: str, symbol: str = "") -> bool:
        try:
            await self._exchange.cancel_order(order_id, symbol.upper() if symbol else None)
            return True
        except Exception as exc:
            logger.error("OKX cancel_order failed: %s", exc)
            return False

    async def get_order(self, order_id: str, symbol: str = "") -> BrokerOrder | None:
        try:
            raw = await self._exchange.fetch_order(
                order_id, symbol.upper() if symbol else None,
            )
            return BrokerOrder(
                order_id=str(raw.get("id", "")),
                symbol=raw.get("symbol", ""),
                side=raw.get("side", ""),
                order_type=raw.get("type", ""),
                price=float(raw.get("price", 0) or 0),
                quantity=float(raw.get("amount", 0) or 0),
                filled_qty=float(raw.get("filled", 0) or 0),
                status=raw.get("status", "pending"),
            )
        except Exception as exc:
            logger.error("OKX get_order failed: %s", exc)
            return None

    async def get_open_orders(self, symbol: str = "") -> list[BrokerOrder]:
        try:
            raw_orders = await self._exchange.fetch_open_orders(
                symbol.upper() if symbol else None,
            )
            orders = []
            for raw in raw_orders:
                orders.append(BrokerOrder(
                    order_id=str(raw.get("id", "")),
                    symbol=raw.get("symbol", ""),
                    side=raw.get("side", ""),
                    order_type=raw.get("type", ""),
                    price=float(raw.get("price", 0) or 0),
                    quantity=float(raw.get("amount", 0) or 0),
                    filled_qty=float(raw.get("filled", 0) or 0),
                    status=raw.get("status", "pending"),
                ))
            return orders
        except Exception as exc:
            logger.error("OKX get_open_orders failed: %s", exc)
            return []

    # ── Position / balance ─────────────────────────────────────────────────

    async def get_position(self, symbol: str) -> BrokerPosition | None:
        try:
            positions = await self._exchange.fetch_positions([symbol.upper()])
            for raw in positions:
                qty = float(raw.get("contracts", 0) or 0)
                if abs(qty) < 1e-9:
                    continue
                return BrokerPosition(
                    symbol=symbol.upper(),
                    quantity=qty,
                    avg_price=float(raw.get("entryPrice", 0) or 0),
                    current_price=float(raw.get("markPrice", 0) or 0),
                    unrealized_pnl=float(raw.get("unrealizedPnl", 0) or 0),
                )
            return None
        except Exception as exc:
            logger.error("OKX get_position failed: %s", exc)
            return None

    async def get_positions(self) -> list[BrokerPosition]:
        try:
            raw_positions = await self._exchange.fetch_positions()
            positions = []
            for raw in raw_positions:
                qty = float(raw.get("contracts", 0) or 0)
                if abs(qty) < 1e-9:
                    continue
                positions.append(BrokerPosition(
                    symbol=raw.get("symbol", ""),
                    quantity=qty,
                    avg_price=float(raw.get("entryPrice", 0) or 0),
                    current_price=float(raw.get("markPrice", 0) or 0),
                    unrealized_pnl=float(raw.get("unrealizedPnl", 0) or 0),
                ))
            return positions
        except Exception as exc:
            logger.error("OKX get_positions failed: %s", exc)
            return []

    async def get_balance(self) -> BrokerBalance:
        try:
            raw = await self._exchange.fetch_balance()
            total = float(raw.get("total", {}).get("USDT", 0) or 0)
            free = float(raw.get("free", {}).get("USDT", 0) or 0)
            used = float(raw.get("used", {}).get("USDT", 0) or 0)
            return BrokerBalance(
                total=max(total, 0),
                available=max(free, 0),
                frozen=max(used, 0),
                currency="USDT",
            )
        except Exception as exc:
            logger.error("OKX get_balance failed: %s", exc)
            return BrokerBalance()

    # ── Fee / connection ───────────────────────────────────────────────────

    def get_fee_rate(self, symbol: str = "") -> dict[str, float]:
        # OKX perpetual default: 0.02% maker / 0.05% taker
        return {"maker": 0.0002, "taker": 0.0005}

    async def test_connection(self) -> bool:
        try:
            await self._exchange.fetch_time()
            return True
        except Exception as exc:
            logger.warning("OKX test_connection failed: %s", exc)
            return False

    async def close(self) -> None:
        """Release ccxt resources."""
        try:
            await self._exchange.close()
        except Exception:
            pass
