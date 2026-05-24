"""Market sentiment tool: fetch VIX, DXY, Fear & Greed, Yield Curve, etc."""

from __future__ import annotations

import json
from typing import Any

from src.agent.tools import BaseTool


class MarketSentimentTool(BaseTool):
    """Fetch market sentiment indicators (VIX, DXY, Fear & Greed, etc.)."""

    name = "market_sentiment"
    description = (
        "Fetch market sentiment and macro indicators. Available indicators: "
        "vix (S&P 500 volatility/fear gauge), vxn (NASDAQ volatility), "
        "gvz (gold volatility), dxy (US Dollar Index), "
        "yield_curve (10Y-2Y spread, recession signal), "
        "fear_greed (crypto Fear & Greed Index 0-100), "
        "put_call (VIX term structure proxy for options sentiment), "
        "all (all indicators above). "
        "Use this to assess overall market risk appetite, fear levels, "
        "and macro conditions."
    )
    parameters = {
        "type": "object",
        "properties": {
            "indicator": {
                "type": "string",
                "description": "Which indicator to fetch: vix, vxn, gvz, dxy, yield_curve, fear_greed, put_call, or all (default: all)",
                "enum": ["vix", "vxn", "gvz", "dxy", "yield_curve", "fear_greed", "put_call", "all"],
                "default": "all",
            },
        },
        "required": [],
    }
    repeatable = True
    is_readonly = True

    @classmethod
    def check_available(cls) -> bool:
        try:
            import yfinance  # noqa: F401
            return True
        except ImportError:
            return False

    def execute(self, **kwargs: Any) -> str:
        indicator = kwargs.get("indicator", "all")

        try:
            from backtest.loaders.sentiment import SentimentFetcher
            fetcher = SentimentFetcher()

            if indicator == "vix":
                result = {"vix": fetcher.fetch_vix()}
            elif indicator == "vxn":
                result = {"vxn": fetcher.fetch_vxn()}
            elif indicator == "gvz":
                result = {"gvz": fetcher.fetch_gvz()}
            elif indicator == "dxy":
                result = {"dxy": fetcher.fetch_dxy()}
            elif indicator == "yield_curve":
                result = {"yield_curve": fetcher.fetch_yield_curve()}
            elif indicator == "fear_greed":
                result = {"fear_greed": fetcher.fetch_fear_greed()}
            elif indicator == "put_call":
                result = {"put_call_proxy": fetcher.fetch_put_call_proxy()}
            else:
                result = fetcher.fetch_all()

            return json.dumps({"status": "ok", "data": result}, ensure_ascii=False, default=str)
        except Exception as exc:
            return json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False)
