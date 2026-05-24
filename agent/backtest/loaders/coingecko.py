"""CoinGecko crypto market data loader.

Free, no-auth crypto market data including:
  - OHLCV klines (via CCXT under the hood, plus CoinGecko for market cap/rankings)
  - Top coins by market cap
  - Trending coins
  - Global crypto market stats

Rate limit: ~10-30 req/min for free tier.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import pandas as pd
import requests

from backtest.loaders.registry import register

logger = logging.getLogger(__name__)

_COINGECKO_BASE = "https://api.coingecko.com/api/v3"
_CACHE: Dict[str, Dict[str, Any]] = {}
_CACHE_TTL = 300  # 5 minutes


@register
class DataLoader:
    """CoinGecko crypto market data loader (free, no auth)."""

    name = "coingecko"
    markets = {"crypto"}
    requires_auth = False

    def is_available(self) -> bool:
        try:
            import requests  # noqa: F401
            return True
        except ImportError:
            return False

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; AStockPursue/1.0)",
            "Accept": "application/json",
        })

    def fetch(
        self,
        codes: List[str],
        start_date: str,
        end_date: str,
        *,
        interval: str = "1D",
        fields: Optional[List[str]] = None,
    ) -> Dict[str, pd.DataFrame]:
        """CoinGecko does not provide direct OHLCV. Use CCXT for klines, CoinGecko for metadata."""
        logger.warning("CoinGecko does not provide OHLCV klines. Use ccxt or okx loader for crypto OHLCV.")
        return {}

    # ------------------------------------------------------------------
    # Top coins by market cap
    # ------------------------------------------------------------------

    def fetch_top_coins(self, limit: int = 50, currency: str = "usd") -> List[Dict[str, Any]]:
        """Fetch top coins by market cap from CoinGecko."""
        try:
            url = f"{_COINGECKO_BASE}/coins/markets"
            params = {
                "vs_currency": currency,
                "order": "market_cap_desc",
                "per_page": min(limit, 250),
                "page": 1,
                "sparkline": "false",
            }
            resp = self._session.get(url, params=params, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            return [
                {
                    "id": c["id"],
                    "symbol": c["symbol"].upper(),
                    "name": c["name"],
                    "current_price": c.get("current_price"),
                    "market_cap": c.get("market_cap"),
                    "market_cap_rank": c.get("market_cap_rank"),
                    "total_volume": c.get("total_volume"),
                    "price_change_percentage_24h": c.get("price_change_percentage_24h"),
                    "price_change_percentage_7d": c.get("price_change_percentage_7d_in_currency"),
                    "circulating_supply": c.get("circulating_supply"),
                    "total_supply": c.get("total_supply"),
                    "ath": c.get("ath"),
                    "ath_change_percentage": c.get("ath_change_percentage"),
                    "image": c.get("image"),
                }
                for c in (data or [])
            ]
        except Exception as e:
            logger.warning("CoinGecko top coins failed: %s", e)
            return []

    # ------------------------------------------------------------------
    # Trending coins
    # ------------------------------------------------------------------

    def fetch_trending(self) -> List[Dict[str, Any]]:
        """Fetch trending coins from CoinGecko search trends."""
        try:
            url = f"{_COINGECKO_BASE}/search/trending"
            resp = self._session.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            coins = []
            for item in (data.get("coins") or []):
                c = item.get("item", {})
                coins.append({
                    "id": c.get("id"),
                    "symbol": (c.get("symbol") or "").upper(),
                    "name": c.get("name"),
                    "market_cap_rank": c.get("market_cap_rank"),
                    "price_btc": c.get("price_btc"),
                    "score": c.get("score"),
                })
            return coins
        except Exception as e:
            logger.warning("CoinGecko trending failed: %s", e)
            return []

    # ------------------------------------------------------------------
    # Global crypto market stats
    # ------------------------------------------------------------------

    def fetch_global_stats(self) -> Dict[str, Any]:
        """Fetch global cryptocurrency market statistics."""
        try:
            url = f"{_COINGECKO_BASE}/global"
            resp = self._session.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json().get("data", {})
            return {
                "active_cryptocurrencies": data.get("active_cryptocurrencies"),
                "total_market_cap": data.get("total_market_cap", {}),
                "total_volume": data.get("total_volume", {}),
                "market_cap_percentage": data.get("market_cap_percentage", {}),
                "market_cap_change_percentage_24h_usd": data.get("market_cap_change_percentage_24h_usd"),
                "btc_dominance": (data.get("market_cap_percentage", {}) or {}).get("btc"),
                "eth_dominance": (data.get("market_cap_percentage", {}) or {}).get("eth"),
            }
        except Exception as e:
            logger.warning("CoinGecko global stats failed: %s", e)
            return {}

    # ------------------------------------------------------------------
    # Exchange volume data
    # ------------------------------------------------------------------

    def fetch_exchanges(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Fetch top exchanges by volume."""
        try:
            url = f"{_COINGECKO_BASE}/exchanges"
            params = {"per_page": min(limit, 250), "page": 1}
            resp = self._session.get(url, params=params, timeout=20)
            resp.raise_for_status()
            return [
                {
                    "id": e["id"],
                    "name": e["name"],
                    "country": e.get("country"),
                    "trade_volume_24h_btc": e.get("trade_volume_24h_btc"),
                    "trust_score": e.get("trust_score"),
                    "trust_score_rank": e.get("trust_score_rank"),
                    "year_established": e.get("year_established"),
                    "url": e.get("url"),
                }
                for e in (resp.json() or [])
            ]
        except Exception as e:
            logger.warning("CoinGecko exchanges failed: %s", e)
            return []
