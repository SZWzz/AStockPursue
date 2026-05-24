"""Market overview tool: global indices, commodities, crypto market data."""

from __future__ import annotations

import json
from typing import Any

from src.agent.tools import BaseTool


class MarketOverviewTool(BaseTool):
    """Fetch global market overview: indices, commodities, and crypto market data."""

    name = "market_overview"
    description = (
        "Fetch a broad market overview across asset classes. "
        "Available views: "
        "global_indices (S&P 500, DJI, NASDAQ, DAX, FTSE, Nikkei, HSI, etc.), "
        "commodities (gold, silver, oil, copper, natural gas, etc.), "
        "crypto (top coins by market cap, trending, global stats), "
        "all (all views combined). "
        "Use this to get a quick snapshot of global market conditions."
    )
    parameters = {
        "type": "object",
        "properties": {
            "view": {
                "type": "string",
                "description": "Which market view to fetch: global_indices, commodities, crypto, or all",
                "enum": ["global_indices", "commodities", "crypto", "all"],
                "default": "all",
            },
            "limit": {
                "type": "integer",
                "description": "Max results for crypto/indices (default 20)",
                "default": 20,
            },
        },
        "required": [],
    }
    repeatable = True
    is_readonly = True

    def execute(self, **kwargs: Any) -> str:
        view = kwargs.get("view", "all")
        limit = min(int(kwargs.get("limit", 20)), 50)

        result: dict[str, Any] = {}

        try:
            if view in ("global_indices", "all"):
                try:
                    from backtest.loaders.global_indices import DataLoader as IndexLoader
                    loader = IndexLoader()
                    result["global_indices"] = loader.fetch_latest()
                except Exception as e:
                    result["global_indices"] = {"error": str(e)}

            if view in ("commodities", "all"):
                try:
                    from backtest.loaders.commodities import DataLoader as CommodityLoader
                    loader = CommodityLoader()
                    result["commodities"] = loader.fetch_latest()
                except Exception as e:
                    result["commodities"] = {"error": str(e)}

            if view in ("crypto", "all"):
                try:
                    from backtest.loaders.coingecko import DataLoader as CryptoLoader
                    loader = CryptoLoader()
                    result["crypto"] = {
                        "top_coins": loader.fetch_top_coins(limit=limit),
                        "trending": loader.fetch_trending(),
                        "global_stats": loader.fetch_global_stats(),
                    }
                except Exception as e:
                    result["crypto"] = {"error": str(e)}

            return json.dumps({"status": "ok", "data": result}, ensure_ascii=False, default=str)
        except Exception as exc:
            return json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False)
