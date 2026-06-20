"""GNews — Google News RSS source.

Free, no API key. Uses the `gnews` Python package which scrapes Google News RSS.
Supports language/country filtering, top headlines, and topic-based queries.

Install: pip install gnews
"""

from __future__ import annotations

import logging

from .base import BaseNewsSource, normalize_article

logger = logging.getLogger(__name__)

# Business/finance keywords in Chinese and English
_MARKET_QUERIES = [
    "中国股市 A股",
    "China stock market",
    "Asia financial markets",
    "global markets finance",
]


class GNewsSource(BaseNewsSource):
    """Google News RSS — free international news."""

    name = "gnews"
    label = "GNews"
    category = "international"

    def fetch_market(self, limit: int = 20) -> list[dict]:
        raw: list[dict] = []
        for q in _MARKET_QUERIES:
            lang = "zh" if any('一' <= c <= '鿿' for c in q) else "en"
            country = "CN" if lang == "zh" else "US"
            raw += self._search(q, max_results=min(limit // len(_MARKET_QUERIES) + 1, 10), language=lang, country=country)
        return self._normalize(raw)[:limit]

    def fetch_stock(self, symbol: str, limit: int = 10) -> list[dict]:
        # Search for stock symbol in both languages
        raw = self._search(f"{symbol} stock", max_results=min(limit, 10), language="en", country="US")
        if any(c.isalpha() and not c.isascii() for c in symbol) or symbol.endswith((".SZ", ".SH")):
            raw += self._search(f"{symbol} 股票", max_results=min(limit, 10), language="zh", country="CN")
        return self._normalize(raw)[:limit]

    def is_available(self) -> bool:
        try:
            from gnews import GNews  # noqa: F401
            return True
        except ImportError:
            return False

    # -- internal ----------------------------------------------------------

    @staticmethod
    def _search(query: str, max_results: int = 10, language: str = "en", country: str = "US") -> list[dict]:
        """Raw Google News RSS search."""
        try:
            from gnews import GNews

            gn = GNews(
                language=language,
                country=country,
                max_results=min(max_results, 20),
                period="7d",
            )
            articles = gn.get_news(query)
            return [
                {
                    "title": a.get("title", ""),
                    "url": a.get("url", ""),
                    "description": a.get("description", ""),
                    "publishedAt": a.get("published date", ""),
                    "publisher": a.get("publisher", {}).get("title", "") if isinstance(a.get("publisher"), dict) else "",
                }
                for a in (articles or [])
            ]
        except ImportError:
            logger.debug("GNews not available (gnews not installed)")
            return []
        except Exception as e:
            logger.debug("GNews search failed for '%s': %s", query, e)
            return []

    def _normalize(self, raw_list: list[dict]) -> list[dict]:
        articles: list[dict] = []
        for r in raw_list:
            a = normalize_article(r, self.name)
            if a:
                publisher = r.get("publisher", "")
                if publisher and a.get("summary"):
                    a["summary"] = f"[{publisher}] {a['summary']}"[:200]
                articles.append(a)
        return articles
