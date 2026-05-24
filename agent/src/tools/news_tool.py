"""Financial news tool: search market news, sector news, and economic calendar."""

from __future__ import annotations

import json
from typing import Any

from src.agent.tools import BaseTool


class FinancialNewsTool(BaseTool):
    """Search financial news and economic calendar events."""

    name = "financial_news"
    description = (
        "Search financial news and get economic calendar events. "
        "Topics: market (general market news), sector (industry-specific), "
        "stock (symbol-specific news), calendar (upcoming economic events), "
        "custom (free-text search). "
        "Use this to stay updated on market-moving news and events."
    )
    parameters = {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": "News topic: market, sector, stock, calendar, or custom",
                "enum": ["market", "sector", "stock", "calendar", "custom"],
                "default": "market",
            },
            "query": {
                "type": "string",
                "description": "Search query (required for sector/stock/custom topics). For sector: sector name. For stock: symbol code.",
            },
            "max_results": {
                "type": "integer",
                "description": "Max results (default 5, max 15)",
                "default": 5,
            },
        },
        "required": [],
    }
    repeatable = True
    is_readonly = True

    @classmethod
    def check_available(cls) -> bool:
        try:
            try:
                import ddgs  # noqa: F401
            except ImportError:
                import duckduckgo_search  # noqa: F401
            return True
        except ImportError:
            return False

    def execute(self, **kwargs: Any) -> str:
        topic = kwargs.get("topic", "market")
        query = kwargs.get("query", "")
        max_results = min(int(kwargs.get("max_results", 5)), 15)

        try:
            from backtest.loaders.news import NewsFetcher
            fetcher = NewsFetcher()

            if topic == "market":
                news = fetcher.fetch_market_news(max_results=max_results)
            elif topic == "sector":
                if not query:
                    return json.dumps({"status": "error", "error": "query is required for sector news"}, ensure_ascii=False)
                news = fetcher.fetch_sector_news(query, max_results=max_results)
            elif topic == "stock":
                if not query:
                    return json.dumps({"status": "error", "error": "query (symbol) is required for stock news"}, ensure_ascii=False)
                news = fetcher.fetch_stock_news(query, max_results=max_results)
            elif topic == "calendar":
                days = max_results  # reuse max_results as days for calendar
                calendar = fetcher.get_economic_calendar(days=min(days, 14))
                return json.dumps({"status": "ok", "data": {"calendar": calendar}}, ensure_ascii=False, default=str)
            elif topic == "custom":
                if not query:
                    return json.dumps({"status": "error", "error": "query is required for custom search"}, ensure_ascii=False)
                news = fetcher.search_news(query, max_results=max_results)
            else:
                news = []

            return json.dumps({"status": "ok", "data": {"news": news}}, ensure_ascii=False, default=str)
        except Exception as exc:
            return json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False)
