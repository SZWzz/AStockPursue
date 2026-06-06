"""Trading execution nodes — Broker connection, order placement, fundamentals."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import pandas as pd

from src.workflow.node_base import BaseNode
from src.workflow.node_registry import register_node
from src.workflow.schema import NodePort, PortType

logger = logging.getLogger(__name__)


@register_node
class BrokerNode(BaseNode):
    """Broker connection node — manages exchange connections and account queries.

    Distinct from OrderNode:
      - BrokerNode: manages connections, queries positions/balance
      - OrderNode:  sends specific trading instructions

    Input ports:
      - codes/STOCK_LIST (optional): Symbols to query positions for

    Output ports:
      - positions/PARAMS: Position list
      - balance/PARAMS:   Account balance
      - status/PARAMS:     Connection status
    """
    node_type = "broker"
    category = "deploy"
    label = "Broker Connect"
    description = "Connect to exchange/broker, query positions and balance"
    icon = "Plug"
    resource_profile = "io_bound"

    inputs = [
        BaseNode.in_port("codes", PortType.STOCK_LIST, required=False,
                         description="Symbols to query positions for"),
    ]
    outputs = [
        BaseNode.out_port("positions", PortType.PARAMS,
                          description="Position list with P&L"),
        BaseNode.out_port("balance", PortType.PARAMS,
                          description="Account balance"),
        BaseNode.out_port("status", PortType.PARAMS,
                          description="Connection status"),
    ]
    config_schema = {
        "exchange": {
            "title": "Exchange",
            "type": "string",
            "enum": ["futu", "binance", "okx"],
            "default": "binance",
        },
        "testnet": {
            "title": "Testnet",
            "type": "boolean",
            "default": True,
        },
        "action": {
            "title": "Action",
            "type": "string",
            "enum": ["positions", "balance", "connect_test"],
            "default": "positions",
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        exchange = config.get("exchange", "binance")
        action = config.get("action", "positions")
        testnet = config.get("testnet", True)

        try:
            from src.trading.brokers import create_broker
            broker = create_broker(exchange, {"testnet": testnet})
        except ValueError as e:
            return {
                "positions": {"error": str(e)},
                "balance": {"error": str(e)},
                "status": {"connected": False, "error": str(e)},
            }

        positions_result = {}
        balance_result = {}
        status_result = {"exchange": exchange, "testnet": testnet}

        # Connection test
        try:
            connected = await broker.test_connection()
            status_result["connected"] = connected
        except Exception as e:
            status_result["connected"] = False
            status_result["error"] = str(e)

        if action in ("positions",):
            try:
                codes = inputs.get("codes", [])
                if isinstance(codes, pd.DataFrame):
                    codes = list(codes.columns) if len(codes.columns) < 100 else list(codes.index)
                if isinstance(codes, list) and len(codes) == 1:
                    pos = await broker.get_position(str(codes[0]))
                    positions_result = {"positions": [pos.__dict__] if pos else []}
                elif isinstance(codes, list) and len(codes) > 1:
                    all_positions = await broker.get_positions()
                    code_set = set(str(c) for c in codes)
                    positions_result = {
                        "positions": [p.__dict__ for p in all_positions if p.symbol in code_set],
                    }
                else:
                    all_positions = await broker.get_positions()
                    positions_result = {"positions": [p.__dict__ for p in all_positions]}
            except Exception as e:
                positions_result = {"error": str(e)}

        if action in ("balance",):
            try:
                bal = await broker.get_balance()
                balance_result = {
                    "total": bal.total,
                    "available": bal.available,
                    "frozen": bal.frozen,
                    "currency": bal.currency,
                }
            except Exception as e:
                balance_result = {"error": str(e)}

        # Clean up broker resources
        if hasattr(broker, "close"):
            try:
                await broker.close()
            except Exception:
                pass

        return {
            "positions": positions_result,
            "balance": balance_result,
            "status": status_result,
        }


@register_node


@register_node
class OrderNode(BaseNode):
    node_type = "order"; category = "deploy"; label = "Place Order"
    description = (
        "Submit, cancel, or list trading orders. "
        "Connects to the live/papr trading OrderManager."
    )
    icon = "Send"
    resource_profile = "io_bound"
    inputs = [
        BaseNode.in_port("signal", PortType.SIGNAL,
                         description="Trading signal: dict[code, weight]"),
        BaseNode.in_port("codes", PortType.STOCK_LIST,
                         description="Stock codes to trade"),
    ]
    outputs = [
        BaseNode.out_port("order_result", PortType.PARAMS,
                          description="Order execution result"),
    ]
    config_schema = {
        "action": {
            "title": "Action", "type": "string",
            "enum": ["submit", "cancel_all", "list"], "default": "submit",
        },
        "side": {
            "title": "Side", "type": "string",
            "enum": ["buy", "sell"], "default": "buy",
        },
        "order_type": {
            "title": "Order Type", "type": "string",
            "enum": ["market", "limit"], "default": "market",
        },
        "quantity_pct": {
            "title": "Quantity %", "type": "number", "default": 0.1,
            "minimum": 0.01, "maximum": 1.0,
            "description": "Fraction of available capital per order",
        },
        "limit_price_offset_pct": {
            "title": "Limit Price Offset %", "type": "number", "default": 0.0,
            "minimum": -0.1, "maximum": 0.1,
            "description": "Offset from last price for limit orders (e.g. -0.01 = 1% below)",
        },
        "capital": {
            "title": "Capital", "type": "number", "default": 1000000,
            "description": "Total capital for position sizing",
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        action = config.get("action", "submit")
        signal = inputs.get("signal", {})
        codes = inputs.get("codes", [])

        if isinstance(codes, pd.DataFrame):
            codes = list(codes.columns) if len(codes.columns) < 100 else list(codes.index)

        # ── List orders ───────────────────────────────────────────────────────
        if action == "list":
            try:
                from src.trading.oms import OrderManager
                orders = OrderManager.list_orders()
                return {"order_result": {"action": "list", "orders": orders, "count": len(orders)}}
            except ImportError:
                return {"order_result": {"action": "list", "orders": [], "note": "OMS not available"}}

        # ── Cancel all ────────────────────────────────────────────────────────
        if action == "cancel_all":
            try:
                from src.trading.oms import OrderManager
                cancelled = OrderManager.cancel_all()
                return {"order_result": {"action": "cancel_all", "cancelled": cancelled}}
            except ImportError:
                return {"order_result": {"action": "cancel_all", "cancelled": 0, "note": "OMS not available"}}

        # ── Submit orders ─────────────────────────────────────────────────────
        side = config.get("side", "buy")
        order_type = config.get("order_type", "market")
        qty_pct = float(config.get("quantity_pct", 0.1))
        limit_offset = float(config.get("limit_price_offset_pct", 0.0))
        capital = float(config.get("capital", 1_000_000))

        if not codes:
            # Extract from signal
            if isinstance(signal, dict):
                codes = list(signal.keys())
        if not codes:
            return {"order_result": {"error": "No codes to trade"}}

        # Resolve weights from signal
        weights: Dict[str, float] = {}
        if isinstance(signal, dict):
            for code, w in signal.items():
                if isinstance(w, pd.Series):
                    weights[code] = float(w.iloc[-1]) if len(w) > 0 else 0.0
                else:
                    weights[code] = float(w) if w is not None else 0.0

        submitted = []
        rejected = []
        try:
            from src.trading.oms import OrderManager, Order, OrderSide

            for code in codes:
                weight = weights.get(code, 1.0 / len(codes) if codes else 0)
                if abs(weight) < 1e-6:
                    continue

                order_side = OrderSide.BUY if (side == "buy" and weight > 0) or (side == "sell" and weight < 0) else OrderSide.SELL
                quantity = int(capital * qty_pct * abs(weight) / 100) * 100  # round to lots of 100

                if quantity <= 0:
                    rejected.append({"code": code, "reason": "Zero quantity"})
                    continue

                order = OrderManager.submit_order(
                    code=code,
                    side=order_side,
                    order_type=order_type,
                    quantity=quantity,
                    limit_offset=limit_offset,
                )
                if order:
                    submitted.append({"code": code, "order_id": getattr(order, "order_id", ""), "quantity": quantity, "side": order_side.value})
                else:
                    rejected.append({"code": code, "reason": "Submission failed"})

        except ImportError:
            # Dry-run mode: simulate
            for code in codes[:5]:
                weight = weights.get(code, 0)
                if abs(weight) < 1e-6:
                    continue
                quantity = int(capital * qty_pct * abs(weight) / 100) * 100
                submitted.append({"code": code, "quantity": quantity, "side": side, "mode": "dry_run"})

        logger.info("Order: %d submitted, %d rejected", len(submitted), len(rejected))
        return {"order_result": {
            "action": "submit",
            "submitted": submitted,
            "rejected": rejected,
            "total_orders": len(submitted),
        }}


@register_node
class FundamentalsNode(BaseNode):
    node_type = "fundamentals"; category = "data"; label = "Fundamentals"
    description = (
        "Fetch fundamental data for stocks: financial snapshot, "
        "valuation metrics, F10 company info, or full financial statements."
    )
    icon = "FileText"
    resource_profile = "io_bound"
    inputs = [
        BaseNode.in_port("codes", PortType.STOCK_LIST,
                         description="Stock codes to fetch fundamentals for"),
    ]
    outputs = [
        BaseNode.out_port("fundamentals", PortType.PARAMS,
                          description="Fundamental data keyed by stock code"),
    ]
    config_schema = {
        "data_type": {
            "title": "Data Type", "type": "string",
            "enum": ["snapshot", "financials", "valuation", "f10"], "default": "snapshot",
            "description": "snapshot=key metrics, financials=3 statements, valuation=PE/PB/PS, f10=company info",
        },
        "max_stocks": {
            "title": "Max Stocks", "type": "integer", "default": 10,
            "minimum": 1, "maximum": 50,
            "description": "Maximum number of stocks to fetch (to avoid rate limits)",
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        codes = inputs.get("codes", [])
        if isinstance(codes, pd.DataFrame):
            codes = list(codes.columns) if len(codes.columns) < 100 else list(codes.index)
        if not codes:
            return {"fundamentals": {"error": "No stock codes provided"}}

        data_type = config.get("data_type", "snapshot")
        max_stocks = int(config.get("max_stocks", 10))
        codes = list(codes)[:max_stocks]

        result: Dict[str, Any] = {}
        try:
            # Try importing the API-level data fetchers
            from backtest.loaders.fundamentals_enhanced import EnhancedFundamentalsLoader
            loader = EnhancedFundamentalsLoader()

            for code in codes:
                try:
                    if data_type == "snapshot":
                        result[code] = loader.get_snapshot(code)
                    elif data_type == "financials":
                        result[code] = loader.get_financials(code)
                    elif data_type == "valuation":
                        result[code] = loader.get_valuation(code)
                    elif data_type == "f10":
                        result[code] = loader.get_f10(code)
                except Exception as e:
                    result[code] = {"error": str(e)}

        except ImportError:
            # Fallback: use DataStore directly
            try:
                from backtest.data_store import get_data_store
                store = get_data_store()
                for code in codes:
                    try:
                        result[code] = {
                            "code": code,
                            "note": "DataStore fundamentals placeholder",
                        }
                    except Exception as e:
                        result[code] = {"error": str(e)}
            except ImportError as e:
                result["_error"] = f"Fundamentals loader not available: {e}"

        n_ok = sum(1 for v in result.values() if isinstance(v, dict) and "error" not in v)
        logger.info("Fundamentals: %d/%d stocks fetched (type=%s)", n_ok, len(codes), data_type)
        return {"fundamentals": result}
