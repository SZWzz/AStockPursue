"""DuckDuckGo web search news source.

Migrated from backtest.loaders.news — search financial news via DuckDuckGo.
Free, no API key required. Best effort, may return empty results.
"""

from __future__ import annotations

import logging
from typing import Any

from .base import BaseNewsSource, normalize_article

logger = logging.getLogger(__name__)


class DuckDuckGoSource(BaseNewsSource):
    """Fetch financial news from DuckDuckGo web search."""

    name = "web_search"
    label = "网页搜索"
    category = "market"

    def fetch_stock(self, symbol: str, limit: int = 5) -> list[dict]:
        """Search for stock-specific news."""
        query = f"{symbol} 股票 新闻"
        raw = self._search(query, max_results=min(limit + 2, 10))
        return self._normalize(raw)

    def fetch_market(self, limit: int = 5) -> list[dict]:
        """Search for general market news."""
        queries = ["A股 市场 行情 今日", "stock market news today"]
        results: list[dict] = []
        per_q = max(limit // len(queries) + 1, 3)
        for q in queries:
            lang = "zh" if any('一' <= c <= '鿿' for c in q) else "en"
            results.extend(self._search(q, max_results=per_q, language=lang))
        return self._normalize(results)[:limit]

    def is_available(self) -> bool:
        try:
            from ddgs import DDGS  # noqa: F401
            return True
        except ImportError:
            try:
                from duckduckgo_search import DDGS  # noqa: F401
                return True
            except ImportError:
                return False

    # -- internal ----------------------------------------------------------

    def _search(
        self,
        query: str,
        max_results: int = 5,
        language: str = "zh",
        region: str = "cn",
    ) -> list[dict[str, str]]:
        """Raw DuckDuckGo search."""
        try:
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS

            full_query = f"财经 {query}" if language == "zh" else f"finance {query}"
            with DDGS() as ddgs:
                raw = list(ddgs.text(
                    full_query,
                    max_results=min(max_results, 20),
                    region=region,
                ))

            return [
                {
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                }
                for r in raw
            ]
        except ImportError:
            logger.debug("DuckDuckGo not available (ddgs not installed)")
            return []
        except Exception as e:
            logger.debug("DuckDuckGo search failed for '%s': %s", query, e)
            return []

    def _normalize(self, raw_list: list[dict]) -> list[dict]:
        articles: list[dict] = []
        for r in raw_list:
            r["source"] = self.name
            a = normalize_article(r, self.name)
            if a:
                articles.append(a)
        return articles
